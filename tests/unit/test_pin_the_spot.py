"""
Unit tests for the pin_the_spot question type (docs/design-pin-the-spot.md).

Pure functions only — scoring, validation, submission checks, reveal parity and the report
board — so no Docker stack is required.

Run with (from the repo root, so the root pytest.ini puts backend/ on the path):
    pytest -c pytest.ini tests/unit/test_pin_the_spot.py -v
"""

from __future__ import annotations

import base64
import math
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from app.schemas.admin import QuestionCreate, validate_pin_the_spot
from app.services import game_service, pin_the_spot, report_service
from app.websocket import gateway

PNG = "data:image/png;base64," + base64.b64encode(b"\x89PNG fake bytes").decode()
SQUARE = {"image_url": PNG, "image_width": 100, "image_height": 100}
WIDE = {"image_url": PNG, "image_width": 200, "image_height": 100}  # aspect 0.5
KEY = {"target": {"x": 0.5, "y": 0.5}, "r_full": 0.05, "r_zero": 0.20}


def _q(grading="ACCURACY", pv=1000.0, config=None, answer_data=None):
    return SimpleNamespace(
        type="pin_the_spot",
        grading_type=grading,
        points_value=pv,
        config=SQUARE if config is None else config,
        answer_data=KEY if answer_data is None else answer_data,
    )


def _score(q, tap):
    r = game_service.calculate_score(q, tap)
    return r.points_awarded, r.is_correct


# ---------------------------------------------------------------------------
# Scoring (section 6 table)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "d, expected",
    [(0.0, 1000), (0.03, 1000), (0.05, 1000), (0.125, 500), (0.20, 0), (0.40, 0)],
)
def test_scoring_table_square(d, expected):
    points, _ = _score(_q(), {"x": 0.5 + d, "y": 0.5})
    assert points == expected


def test_edges_survive_float_noise():
    # 0.55 - 0.5 == 0.05000000000000004: still on the full-credit circle.
    assert _score(_q(), {"x": 0.55, "y": 0.5}) == (1000, True)
    # 0.7 - 0.5 == 0.19999999999999996: still on the zero circle.
    assert _score(_q(), {"x": 0.7, "y": 0.5})[0] == 0


def test_is_correct_only_inside_r_full():
    assert _score(_q(), {"x": 0.53, "y": 0.5})[1] is True
    assert _score(_q(), {"x": 0.6, "y": 0.5}) == (pytest.approx(666.67), False)


def test_aspect_scales_vertical_distance():
    # 2:1 image, aspect 0.5: a vertical miss of 0.25 (height units) is 0.125 width units.
    q = _q(config=WIDE)
    assert _score(q, {"x": 0.5, "y": 0.75})[0] == 500
    assert _score(q, {"x": 0.625, "y": 0.5})[0] == 500  # same distance horizontally


def test_rounds_half_up_to_two_dp():
    # pv 1: fraction (0.2 - 0.1)/0.15 = 0.6667 -> 0.67
    assert _score(_q(pv=1.0), {"x": 0.6, "y": 0.5})[0] == 0.67


def test_float32_points_value_noise():
    pv = 0.30000001192092896  # FLOAT read-back of 0.3
    points, _ = _score(_q(pv=pv), {"x": 0.625, "y": 0.5})  # fraction 0.5
    assert points == 0.15


def test_points_never_exceed_points_value():
    points, _ = _score(_q(pv=0.005), {"x": 0.56, "y": 0.5})
    assert points <= 0.005


def test_completeness_any_valid_tap_full_points():
    q = _q(grading="COMPLETENESS", answer_data={})
    assert _score(q, {"x": 0.0, "y": 1.0}) == (1000, True)


@pytest.mark.parametrize("grading", ["ACCURACY", "COMPLETENESS"])
def test_invalid_tap_scores_zero_under_both(grading):
    q = _q(grading=grading)
    assert _score(q, {"x": 2, "y": 0.5}) == (0, False)
    assert _score(q, {"x": True, "y": 0.5}) == (0, False)


@pytest.mark.parametrize(
    "config, answer_data",
    [
        (SQUARE, {}),
        (SQUARE, {"target": {"x": 0.5}, "r_full": 0.05, "r_zero": 0.2}),
        (SQUARE, {"target": {"x": 0.5, "y": 0.5}, "r_full": 0.3, "r_zero": 0.2}),
        ({"image_url": PNG}, KEY),
        ({"image_url": PNG, "image_width": 0, "image_height": 10}, KEY),
    ],
)
def test_malformed_stored_question_scores_zero(config, answer_data):
    assert _score(_q(config=config, answer_data=answer_data), {"x": 0.5, "y": 0.5}) == (
        0,
        False,
    )


# ---------------------------------------------------------------------------
# Submission checks
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "tap",
    [
        {"y": 0.5},
        {"x": "0.5", "y": 0.5},
        {"x": float("nan"), "y": 0.5},
        {"x": float("inf"), "y": 0.5},
        {"x": -0.01, "y": 0.5},
        {"x": 0.5, "y": 1.01},
        {"x": 0.5, "y": 0.5, "z": 0},
        {"x": True, "y": 0.5},
        [0.5, 0.5],
        None,
    ],
)
def test_invalid_taps(tap):
    assert not pin_the_spot.is_valid_tap(tap)


@pytest.mark.parametrize("tap", [{"x": 0, "y": 1}, {"x": 0.25, "y": 0.75}])
def test_valid_taps(tap):
    assert pin_the_spot.is_valid_tap(tap)


def test_tap_key_format_and_round_trip():
    assert pin_the_spot.tap_key({"x": 0.4, "y": 0.63}) == "0.4000,0.6300"
    assert pin_the_spot.parse_tap_key("0.4000,0.6300") == (0.4, 0.63)
    assert pin_the_spot.parse_tap_key("nonsense") is None


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


def _create(**kw):
    body = {
        "type": "pin_the_spot",
        "grading_type": "ACCURACY",
        "prompt": "Tap Bascom Hall",
        "config": dict(SQUARE),
        "answer_data": dict(KEY),
    }
    body.update(kw)
    return QuestionCreate(**body)


def test_valid_create():
    _create()
    _create(grading_type="COMPLETENESS", answer_data={})
    _create(config={**SQUARE, "image_url": "https://example.com/map.png"})
    _create(config={**SQUARE, "image_url": "HTTPS://example.com/map.png"})
    _create(config={**SQUARE, "image_url": "DATA:IMAGE/JPEG;BASE64,AAAA"})


BAD_CONFIGS = [
    {},
    {"image_width": 10, "image_height": 10},
    {**SQUARE, "extra": 1},
    {**SQUARE, "image_width": 0},
    {**SQUARE, "image_width": 20_001},
    {**SQUARE, "image_width": 10.0},
    {**SQUARE, "image_width": True},
    {**SQUARE, "image_url": "http://example.com/map.png"},
    {**SQUARE, "image_url": "https://"},
    {**SQUARE, "image_url": "https://exa mple.com/x.png"},
    {**SQUARE, "image_url": "javascript:alert(1)"},
    {**SQUARE, "image_url": "data:image/svg+xml;base64,PHN2Zz4="},
    {**SQUARE, "image_url": "data:image/png;base64,"},
    {**SQUARE, "image_url": "data:image/png;base64,not base64!"},
    {**SQUARE, "image_url": "https://x.com/" + "a" * 1_500_000},
    {**SQUARE, "image_url": 5},
]


@pytest.mark.parametrize("config", BAD_CONFIGS)
def test_rejects_bad_config(config):
    with pytest.raises(ValidationError):
        _create(config=config)


BAD_ANSWERS = [
    {"target": {"x": 0.5, "y": 0.5}, "r_full": 0.05},
    {**KEY, "extra": 1},
    {**KEY, "target": {"x": 1.5, "y": 0.5}},
    {**KEY, "target": {"x": 0.5}},
    {**KEY, "target": {"x": 0.5, "y": 0.5, "z": 0}},
    {**KEY, "target": {"x": True, "y": 0.5}},
    {**KEY, "r_full": 0.2, "r_zero": 0.2},
    {**KEY, "r_full": 0.3},
    {**KEY, "r_full": -0.05},
    {**KEY, "r_full": 0},
    {**KEY, "r_zero": math.sqrt(2) + 0.01},
    {**KEY, "r_zero": float("nan")},
    {**KEY, "r_zero": True},
]


@pytest.mark.parametrize("answer_data", BAD_ANSWERS)
def test_rejects_bad_answer_data(answer_data):
    with pytest.raises(ValidationError):
        _create(answer_data=answer_data)


def test_accuracy_needs_target():
    with pytest.raises(ValidationError):
        _create(answer_data={})


def test_r_zero_up_to_diagonal_allowed():
    _create(answer_data={**KEY, "r_zero": math.sqrt(2)})
    # Wide image: diagonal sqrt(1 + 0.25)
    validate_pin_the_spot("ACCURACY", WIDE, {**KEY, "r_zero": math.sqrt(1.25)})
    with pytest.raises(ValueError):
        validate_pin_the_spot("ACCURACY", WIDE, {**KEY, "r_zero": 1.2})


# ---------------------------------------------------------------------------
# Reveal parity across the four copies
# ---------------------------------------------------------------------------

FULL = {"target": {"x": 0.5, "y": 0.5}, "rFull": 0.05, "rZero": 0.2}
PARITY = {
    "accuracy": (_q(), {"type": "pin_the_spot", **FULL}),
    "completeness_with_target": (_q(grading="COMPLETENESS"), {"type": "completeness", **FULL}),
    "completeness_without_target": (
        _q(grading="COMPLETENESS", answer_data={}),
        {"type": "completeness"},
    ),
    "malformed_accuracy": (
        _q(answer_data={"target": {"x": 0.5}, "r_full": 0.05, "r_zero": 0.2}),
        {"type": "pin_the_spot"},
    ),
}


@pytest.mark.parametrize("name", list(PARITY))
def test_reveal_parity(name):
    q, expected = PARITY[name]
    args = (q.type, q.grading_type, q.answer_data, q.points_value)
    reveals = {
        "gateway": gateway._answer_reveal(q),
        "report": report_service._answer_reveal(q),
        "player_summary": game_service._player_summary_reveal(*args),
        "host_summary": game_service._host_summary_reveal(*args),
    }
    for source, reveal in reveals.items():
        assert reveal == expected, source


# ---------------------------------------------------------------------------
# Report board
# ---------------------------------------------------------------------------


def test_report_board_draws_taps_and_circles():
    q = _q()
    svg = report_service._render_pin_board(
        q, {"0.5000,0.5000": 4, "0.9000,0.1000": 1, "bad": 3}, report_service._answer_reveal(q)
    )
    assert svg.startswith("<svg") and "<image" in svg
    assert 'stroke-dasharray="12 8"' in svg  # zero-credit circle
    assert svg.count('fill="#818cf8"') == 2  # two valid tap keys


def test_report_board_escapes_image_url():
    q = _q(config={**SQUARE, "image_url": 'https://x.com/a"onload="alert(1)'})
    svg = report_service._render_pin_board(q, {}, report_service._answer_reveal(q))
    assert '"onload="' not in svg
    assert "&quot;onload=&quot;" in svg
