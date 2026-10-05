"""
Unit tests for the pin_the_spot question type (docs/design-pin-the-spot.md).

Pure functions only — scoring, authoring validation, submission checks and reveal
parity — so no Docker stack is required.

Run with (from the repo root, so the root pytest.ini puts backend/ on the path):
    pytest -c pytest.ini tests/unit/test_pin_the_spot.py -v
"""

from __future__ import annotations

import math
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from app.schemas.admin import QuestionCreate, validate_pin_the_spot
from app.services import game_service, pin_the_spot, report_service
from app.websocket import gateway
from pydantic import ValidationError

DATA_URL = "data:image/png;base64,iVBORw0KGgo="
SQUARE = {"image_url": DATA_URL, "image_width": 800, "image_height": 800}
WIDE = {"image_url": DATA_URL, "image_width": 1000, "image_height": 500}  # aspect 0.5
ANSWER = {"target": {"x": 0.5, "y": 0.5}, "r_full": 0.05, "r_zero": 0.20}


def _question(
    config=SQUARE, answer=ANSWER, pv: float = 1000, grading: str = "ACCURACY"
):
    q = MagicMock()
    q.type = "pin_the_spot"
    q.grading_type = grading
    q.points_value = pv
    q.config = dict(config)
    q.answer_data = answer
    return q


def _score(q, x, y) -> tuple[float, bool]:
    r = game_service.calculate_score(q, {"x": x, "y": y})
    return r.points_awarded, r.is_correct


# ---------------------------------------------------------------------------
# calculate_score — the worked table in section 5
# ---------------------------------------------------------------------------


class TestScoringTable:
    @pytest.mark.parametrize(
        "d,expected,correct",
        [
            (0.0, 1000, True),
            (0.03, 1000, True),
            (0.05, 1000, True),  # on the full-credit edge
            (0.125, 500, False),  # halfway between the circles
            (0.20, 0, False),  # on the zero-credit edge
            (0.40, 0, False),
        ],
    )
    def test_horizontal_distance(self, d, expected, correct):
        points, is_correct = _score(_question(), 0.5 + d, 0.5)
        assert points == pytest.approx(expected)
        assert is_correct is correct

    def test_diagonal_distance_uses_euclid(self):
        # 3-4-5 triangle scaled to d = 0.125 → half credit.
        points, _ = _score(_question(), 0.5 + 0.075, 0.5 + 0.1)
        assert points == pytest.approx(500)

    def test_partial_rounds_half_up_to_2dp(self):
        # pv = 1: d = 0.1 → (0.2 - 0.1) / 0.15 = 0.6666… → 0.67
        points, correct = _score(_question(pv=1), 0.6, 0.5)
        assert points == 0.67
        assert correct is False

    def test_partial_never_exceeds_points_value(self):
        points, _ = _score(_question(pv=1), 0.5 + 0.0500001, 0.5)
        assert points <= 1

    def test_float32_points_value_noise_is_stripped(self):
        points, _ = _score(_question(pv=0.8299999833106995), 0.5 + 0.125, 0.5)
        assert points == 0.42  # 0.83 / 2 = 0.415 → 0.42 half-up

    def test_zero_points_value(self):
        assert _score(_question(pv=0), 0.5, 0.5) == (0, True)


class TestAspectRatio:
    def test_vertical_distance_is_scaled_by_aspect(self):
        # On a 2:1 image (aspect 0.5), 0.25 of the height is 0.125 image widths.
        q = _question(config=WIDE)
        assert _score(q, 0.5, 0.75)[0] == pytest.approx(500)

    def test_same_visual_distance_scores_the_same(self):
        q = _question(config=WIDE)
        horizontal = _score(q, 0.5 + 0.1, 0.5)[0]
        vertical = _score(q, 0.5, 0.5 + 0.2)[0]  # 0.2 of the height = 0.1 widths
        assert horizontal == vertical
        assert 0 < horizontal < 1000


class TestCompletenessAndInvalid:
    def test_completeness_any_valid_tap_is_full(self):
        q = _question(grading="COMPLETENESS", answer={})
        assert _score(q, 0.0, 1.0) == (1000, True)

    def test_completeness_ignores_target(self):
        q = _question(grading="COMPLETENESS")
        assert _score(q, 1.0, 1.0) == (1000, True)

    @pytest.mark.parametrize("grading", ["ACCURACY", "COMPLETENESS"])
    @pytest.mark.parametrize(
        "answer",
        [
            {},
            {"x": 0.5},
            {"x": "0.5", "y": 0.5},
            {"x": True, "y": 0.5},
            {"x": math.nan, "y": 0.5},
            {"x": math.inf, "y": 0.5},
            {"x": -0.01, "y": 0.5},
            {"x": 0.5, "y": 1.01},
            {"x": 0.5, "y": 0.5, "extra": 1},
        ],
        ids=[
            "empty",
            "missing_y",
            "string",
            "bool",
            "nan",
            "inf",
            "neg",
            "over",
            "extra",
        ],
    )
    def test_invalid_tap_scores_zero(self, grading, answer):
        q = _question(grading=grading)
        r = game_service.calculate_score(q, answer)
        assert (r.points_awarded, r.is_correct) == (0, False)

    def test_malformed_stored_config_scores_zero(self):
        q = _question(config={"image_url": DATA_URL})
        assert _score(q, 0.5, 0.5) == (0, False)


class TestTapHelpers:
    def test_ints_are_valid(self):
        assert pin_the_spot.is_valid_tap({"x": 0, "y": 1})

    def test_tap_key_rounds_to_4dp(self):
        assert pin_the_spot.tap_key({"x": 0.123456, "y": 1}) == "0.1235,1.0000"


# ---------------------------------------------------------------------------
# Authoring validation — QuestionCreate and the helper update_question calls
# ---------------------------------------------------------------------------


def _body(config=SQUARE, answer=ANSWER, grading="ACCURACY") -> dict:
    return {
        "type": "pin_the_spot",
        "grading_type": grading,
        "prompt": "Tap the spot",
        "config": config,
        "answer_data": answer,
        "points_value": 1000,
    }


def _with(base: dict, **changes) -> dict:
    out = dict(base)
    out.update(changes)
    return out


INVALID_CASES = [
    (
        "missing image_url",
        {"config": {"image_width": 10, "image_height": 10}},
        "exactly",
    ),
    ("extra config key", {"config": _with(SQUARE, image_id=3)}, "exactly"),
    (
        "javascript url",
        {"config": _with(SQUARE, image_url="javascript:alert(1)")},
        "http(s) URL",
    ),
    (
        "svg data url",
        {"config": _with(SQUARE, image_url="data:image/svg+xml;base64,PHN2Zz4=")},
        "http(s) URL",
    ),
    ("url not a string", {"config": _with(SQUARE, image_url=7)}, "http(s) URL"),
    (
        "url too long",
        {"config": _with(SQUARE, image_url="https://x/" + "a" * 1_500_000)},
        "too large",
    ),
    ("zero width", {"config": _with(SQUARE, image_width=0)}, "whole numbers"),
    ("float height", {"config": _with(SQUARE, image_height=10.5)}, "whole numbers"),
    ("bool width", {"config": _with(SQUARE, image_width=True)}, "whole numbers"),
    ("accuracy without target", {"answer": {}}, "needs a target"),
    (
        "missing r_zero",
        {"answer": {"target": {"x": 0.5, "y": 0.5}, "r_full": 0.1}},
        "exactly",
    ),
    (
        "target x over 1",
        {"answer": _with(ANSWER, target={"x": 1.2, "y": 0.5})},
        "Target",
    ),
    (
        "target negative",
        {"answer": _with(ANSWER, target={"x": 0.5, "y": -0.1})},
        "Target",
    ),
    (
        "target extra key",
        {"answer": _with(ANSWER, target={"x": 0.5, "y": 0.5, "z": 0})},
        "Target",
    ),
    ("target bool", {"answer": _with(ANSWER, target={"x": True, "y": 0.5})}, "Target"),
    ("radius string", {"answer": _with(ANSWER, r_full="0.1")}, "Radii must be numbers"),
    ("r_full zero", {"answer": _with(ANSWER, r_full=0)}, "0 < full-credit"),
    ("negative radius", {"answer": _with(ANSWER, r_full=-0.1)}, "0 < full-credit"),
    ("r_full equals r_zero", {"answer": _with(ANSWER, r_full=0.2)}, "0 < full-credit"),
    ("r_full above r_zero", {"answer": _with(ANSWER, r_full=0.3)}, "0 < full-credit"),
    # Square diagonal is √2 ≈ 1.414.
    ("r_zero beyond diagonal", {"answer": _with(ANSWER, r_zero=1.5)}, "diagonal"),
    (
        "completeness partial answer",
        {"grading": "COMPLETENESS", "answer": {"target": {"x": 0, "y": 0}}},
        "exactly",
    ),
]

VALID_CASES = [
    ("accuracy data url", {}),
    ("https url", {"config": _with(SQUARE, image_url="https://example.com/map.png")}),
    (
        "jpeg data url",
        {"config": _with(SQUARE, image_url="data:image/jpeg;base64,/9j/")},
    ),
    ("target on corner", {"answer": _with(ANSWER, target={"x": 0, "y": 1})}),
    ("r_zero at diagonal", {"answer": _with(ANSWER, r_zero=math.sqrt(2))}),
    # Tall image: diagonal = √(1 + 9) ≈ 3.16, so r_zero 2 is allowed.
    (
        "tall image big radius",
        {
            "config": _with(SQUARE, image_width=100, image_height=300),
            "answer": _with(ANSWER, r_zero=2.0),
        },
    ),
    ("completeness without target", {"grading": "COMPLETENESS", "answer": {}}),
    ("completeness with target", {"grading": "COMPLETENESS"}),
]


class TestQuestionCreate:
    @pytest.mark.parametrize(
        "kwargs,message",
        [(k, m) for _, k, m in INVALID_CASES],
        ids=[d for d, _, _ in INVALID_CASES],
    )
    def test_rejects(self, kwargs, message):
        with pytest.raises(ValidationError) as exc_info:
            QuestionCreate(**_body(**kwargs))
        assert message in str(exc_info.value)

    @pytest.mark.parametrize(
        "kwargs", [k for _, k in VALID_CASES], ids=[d for d, _ in VALID_CASES]
    )
    def test_accepts(self, kwargs):
        assert QuestionCreate(**_body(**kwargs)).type == "pin_the_spot"


class TestValidatePinTheSpotHelper:
    """The helper the update path calls directly gives the same verdicts."""

    @pytest.mark.parametrize(
        "kwargs,message",
        [(k, m) for _, k, m in INVALID_CASES],
        ids=[d for d, _, _ in INVALID_CASES],
    )
    def test_rejects(self, kwargs, message):
        body = _body(**kwargs)
        with pytest.raises(ValueError) as exc_info:
            validate_pin_the_spot(
                body["grading_type"], body["config"], body["answer_data"]
            )
        assert message in str(exc_info.value)

    @pytest.mark.parametrize(
        "kwargs", [k for _, k in VALID_CASES], ids=[d for d, _ in VALID_CASES]
    )
    def test_accepts(self, kwargs):
        body = _body(**kwargs)
        validate_pin_the_spot(body["grading_type"], body["config"], body["answer_data"])


# ---------------------------------------------------------------------------
# Reveal parity across the four copies
# ---------------------------------------------------------------------------

PARITY_QUESTIONS = {
    "accuracy": (
        SimpleNamespace(
            type="pin_the_spot",
            grading_type="ACCURACY",
            answer_data=ANSWER,
            points_value=1.0,
        ),
        {
            "type": "pin_the_spot",
            "target": {"x": 0.5, "y": 0.5},
            "rFull": 0.05,
            "rZero": 0.20,
        },
    ),
    "completeness_with_target": (
        SimpleNamespace(
            type="pin_the_spot",
            grading_type="COMPLETENESS",
            answer_data=ANSWER,
            points_value=1.0,
        ),
        {
            "type": "completeness",
            "target": {"x": 0.5, "y": 0.5},
            "rFull": 0.05,
            "rZero": 0.20,
        },
    ),
    "completeness_without_target": (
        SimpleNamespace(
            type="pin_the_spot",
            grading_type="COMPLETENESS",
            answer_data={},
            points_value=1.0,
        ),
        {"type": "completeness"},
    ),
}


@pytest.mark.parametrize("name", list(PARITY_QUESTIONS))
def test_reveal_parity(name):
    q, expected = PARITY_QUESTIONS[name]
    args = (q.type, q.grading_type, q.answer_data, q.points_value)
    reveals = {
        "gateway": gateway._answer_reveal(q),
        "report": report_service._answer_reveal(q),
        "player_summary": game_service._player_summary_reveal(*args),
        "host_summary": game_service._host_summary_reveal(*args),
    }
    for source, reveal in reveals.items():
        assert reveal == expected, source


def test_reveal_never_leaks_snake_case_answer_data():
    reveal = pin_the_spot.reveal("ACCURACY", ANSWER)
    assert "r_full" not in reveal and "r_zero" not in reveal


# ---------------------------------------------------------------------------
# HTML report chart
# ---------------------------------------------------------------------------


def test_report_svg_draws_taps_and_circles():
    q = _question(config=WIDE)
    reveal = report_service._answer_reveal(q)
    svg = report_service._render_pin_the_spot(q, {"0.5000,0.5000": 2, "bad": 1}, reveal)
    assert 'viewBox="0 0 1000 500.0"' in svg
    assert svg.count('class="pin-tap"') == 1  # the malformed key is skipped
    assert 'r="200.0" class="pin-zero"' in svg  # r_zero 0.2 × 1000
    assert "2 taps" in svg


def test_report_svg_escapes_image_url():
    q = _question(config=_with(SQUARE, image_url='https://x/a.png?"><script>'))
    svg = report_service._render_pin_the_spot(q, {}, {"type": "completeness"})
    assert "<script>" not in svg
