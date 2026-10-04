"""
Unit tests for the put_in_order question type (docs/design-put-in-order.md).

Pure functions only — scoring, authoring validation, reveal parity and CSV rounding —
so no Docker stack is required.

Run with (from the repo root, so the root pytest.ini puts backend/ on the path):
    pytest -c pytest.ini tests/unit/test_put_in_order.py -v
"""

from __future__ import annotations

import csv
import io
import itertools
from decimal import ROUND_HALF_UP, Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from pydantic import ValidationError

from app.models.course import Course
from app.models.session import GameSession
from app.schemas.admin import QuestionCreate, validate_put_in_order
from app.services import export_service, game_service, report_service
from app.websocket import gateway


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _question(n: int, pv: float = 1.0, grading: str = "ACCURACY", correct=None):
    q = MagicMock()
    q.type = "put_in_order"
    q.grading_type = grading
    q.points_value = pv
    q.config = {"items": [f"item{i}" for i in range(n)]}
    q.answer_data = {"correct_order": list(range(n)) if correct is None else correct}
    return q


def _concordant(sub: list[int], correct: list[int]) -> int:
    rank = {item: pos for pos, item in enumerate(correct)}
    return sum(
        1
        for i in range(len(sub))
        for j in range(i + 1, len(sub))
        if rank[sub[i]] < rank[sub[j]]
    )


def _order_with(n: int, c: int) -> list[int]:
    """A permutation of 0..n-1 with exactly c concordant pairs against the identity."""
    for perm in itertools.permutations(range(n)):
        if _concordant(list(perm), list(range(n))) == c:
            return list(perm)
    raise AssertionError(f"no permutation of {n} with c={c}")


def _score(q, ordered) -> tuple[float, bool]:
    r = game_service.calculate_score(q, {"orderedIndices": ordered})
    return r.points_awarded, r.is_correct


def _half_up(x: float) -> float:
    return float(Decimal(str(x)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def _has_at_most_2dp(x: float) -> bool:
    return round(x, 2) == x


# ---------------------------------------------------------------------------
# calculate_score
# ---------------------------------------------------------------------------


class TestCalculateScore:
    @pytest.mark.parametrize("n", [3, 4, 5, 6])
    def test_identity_order_is_full_points(self, n):
        q = _question(n, pv=1.0)
        assert _score(q, list(range(n))) == (1.0, True)

    @pytest.mark.parametrize("n", [3, 4, 5, 6])
    def test_reversed_order_is_zero(self, n):
        q = _question(n)
        assert _score(q, list(reversed(range(n)))) == (0, False)

    @pytest.mark.parametrize("n", [3, 4, 5, 6])
    def test_one_adjacent_swap(self, n):
        t = n * (n - 1) // 2
        q = _question(n, pv=1.0)
        ordered = [1, 0] + list(range(2, n))
        pts, ok = _score(q, ordered)
        assert pts == _half_up(1.0 * (t - 1) / t)
        assert ok is False

    def test_one_adjacent_swap_n4_is_083(self):
        assert _score(_question(4), [1, 0, 2, 3]) == (0.83, False)

    def test_scrambled_correct_order_is_respected(self):
        # Display order [C, A, D, B], correct A, B, C, D → correct_order [1, 3, 0, 2]
        q = _question(4, correct=[1, 3, 0, 2])
        assert _score(q, [1, 3, 0, 2]) == (1.0, True)
        assert _score(q, [3, 1, 0, 2]) == (0.83, False)
        assert _score(q, [2, 0, 3, 1]) == (0, False)

    def test_n6_c1(self):
        assert _score(_question(6), _order_with(6, 1)) == (0.07, False)

    def test_n3_c1_and_c2(self):
        assert _score(_question(3), _order_with(3, 1)) == (0.33, False)
        assert _score(_question(3), _order_with(3, 2)) == (0.67, False)

    def test_half_up_rounding(self):
        # round(0.15 * 1 / 6, 2) == 0.02 with banker's/binary rounding; half-up gives 0.03
        assert _score(_question(4, pv=0.15), _order_with(4, 1)) == (0.03, False)

    def test_float32_points_value_noise_is_stripped(self):
        # float32 read-back of 0.03; the exact 0.005 rounds half-up to 0.01
        pv = 0.029999999329447746
        assert _score(_question(4, pv=pv), _order_with(4, 1)) == (0.01, False)

    def test_perfect_order_keeps_unrounded_points_value(self):
        assert _score(_question(4, pv=0.125), [0, 1, 2, 3]) == (0.125, True)

    def test_clamped_to_points_value_without_being_correct(self):
        # raw 0.059 * 14/15 = 0.05507 → 0.06 > pv, clamped back to pv
        assert _score(_question(6, pv=0.059), _order_with(6, 14)) == (0.059, False)

    def test_zero_points_value(self):
        assert _score(_question(4, pv=0), [1, 0, 2, 3]) == (0, False)
        assert _score(_question(4, pv=0), [0, 1, 2, 3]) == (0, True)

    def test_large_points_value(self):
        assert _score(_question(4, pv=1000), _order_with(4, 5)) == (833.33, False)

    @pytest.mark.parametrize("pv", [1.0, 0.15, 0.125, 0.059, 7.0, 1000.0])
    @pytest.mark.parametrize("n", [3, 4, 5, 6])
    def test_result_is_float_with_at_most_2dp_or_pv(self, n, pv):
        q = _question(n, pv=pv)
        for perm in itertools.permutations(range(n)):
            pts, ok = _score(q, list(perm))
            assert isinstance(pts, float) or pts == 0
            assert 0 <= pts <= pv
            assert pts == pv or _has_at_most_2dp(pts)
            assert ok == (list(perm) == list(range(n)))

    @pytest.mark.parametrize(
        "ordered", [[0, 1, 2, 3], [3, 2, 1, 0], [1, 0, 2, 3], [2, 3, 0, 1]]
    )
    def test_completeness_any_permutation_full_points(self, ordered):
        q = _question(4, pv=1.0, grading="COMPLETENESS")
        assert _score(q, ordered) == (1.0, True)

    def test_empty_answer_is_zero(self):
        r = game_service.calculate_score(_question(4), {})
        assert (r.points_awarded, r.is_correct) == (0, False)

    @pytest.mark.parametrize(
        "ordered",
        [[0, 0, 1, 2], [0, 1, 2], [0, 1, 2, 9], "0123", None, [0, 1, 2, 3, 4]],
    )
    def test_non_permutation_is_zero(self, ordered):
        assert _score(_question(4), ordered) == (0, False)

    def test_bool_posing_as_int_is_zero(self):
        # sorted([True, 0, 2]) == [0, 1, 2], so only the type(x) is int rule rejects it
        assert _score(_question(3), [True, 0, 2]) == (0, False)


# ---------------------------------------------------------------------------
# Authoring validation
# ---------------------------------------------------------------------------


def _create(items, correct_order="auto", grading="ACCURACY", extra_config=None):
    config = {"items": items}
    if extra_config:
        config.update(extra_config)
    answer_data = {}
    if correct_order == "auto":
        n = len(items) if isinstance(items, list) else 0
        answer_data["correct_order"] = list(reversed(range(n)))
    elif correct_order is not None:
        answer_data["correct_order"] = correct_order
    return dict(
        type="put_in_order",
        grading_type=grading,
        prompt="Order these",
        config=config,
        answer_data=answer_data,
    )


ITEMS4 = ["A", "B", "C", "D"]

# (description, kwargs for _create, expected ValueError text)
INVALID_CASES = [
    ("2 items", dict(items=["A", "B"]), "Put in Order needs between 3 and 6 items"),
    (
        "7 items",
        dict(items=list("ABCDEFG")),
        "Put in Order needs between 3 and 6 items",
    ),
    (
        "items not a list",
        dict(items="ABC", correct_order=[2, 1, 0]),
        "Put in Order needs between 3 and 6 items",
    ),
    ("non-string item", dict(items=["A", "B", 3]), "Every item must be text"),
    ("blank item", dict(items=["A", "  ", "C"]), "Every item needs text"),
    (
        "201-char item",
        dict(items=["A", "B", "x" * 201]),
        "Each item must be at most 200 characters",
    ),
    ("exact duplicate", dict(items=["A", "B", "A"]), "Items must be different"),
    (
        "case/whitespace duplicate",
        dict(items=["Prophase", "B", "  prophase "]),
        "Items must be different",
    ),
    (
        "extra config key",
        dict(items=ITEMS4, extra_config={"answer": [0, 1, 2, 3]}),
        'Put in Order config may only contain "items"',
    ),
    (
        "missing correct_order (ACCURACY)",
        dict(items=ITEMS4, correct_order=None),
        "Correct order is missing or invalid: it must list each item index exactly once",
    ),
    (
        "correct_order wrong length",
        dict(items=ITEMS4, correct_order=[2, 1, 0]),
        "Correct order is missing or invalid: it must list each item index exactly once",
    ),
    (
        "correct_order repeats",
        dict(items=ITEMS4, correct_order=[1, 1, 0, 2]),
        "Correct order is missing or invalid: it must list each item index exactly once",
    ),
    (
        "correct_order out of range",
        dict(items=ITEMS4, correct_order=[1, 0, 2, 4]),
        "Correct order is missing or invalid: it must list each item index exactly once",
    ),
    (
        "correct_order non-ints",
        dict(items=ITEMS4, correct_order=["1", "0", "2", "3"]),
        "Correct order is missing or invalid: it must list each item index exactly once",
    ),
    (
        "correct_order floats",
        dict(items=ITEMS4, correct_order=[1.0, 0.0, 2.0, 3.0]),
        "Correct order is missing or invalid: it must list each item index exactly once",
    ),
    (
        "correct_order with bool",
        dict(items=["A", "B", "C"], correct_order=[True, 0, 2]),
        "Correct order is missing or invalid: it must list each item index exactly once",
    ),
    (
        "identity correct_order (ACCURACY)",
        dict(items=ITEMS4, correct_order=[0, 1, 2, 3]),
        "Display order must differ from the correct order",
    ),
    (
        "COMPLETENESS with an invalid correct_order",
        dict(items=ITEMS4, correct_order=[0, 0, 1, 2], grading="COMPLETENESS"),
        "Correct order is missing or invalid: it must list each item index exactly once",
    ),
]

VALID_CASES = [
    ("3 items", dict(items=["A", "B", "C"])),
    ("6 items", dict(items=list("ABCDEF"))),
    ("200-char item", dict(items=["A", "B", "x" * 200])),
    ("200 chars padded with spaces", dict(items=["A", "B", "  " + "x" * 200 + "  "])),
    (
        "COMPLETENESS without correct_order",
        dict(items=ITEMS4, correct_order=None, grading="COMPLETENESS"),
    ),
    (
        "COMPLETENESS with identity correct_order",
        dict(items=ITEMS4, correct_order=[0, 1, 2, 3], grading="COMPLETENESS"),
    ),
]


class TestQuestionCreate:
    @pytest.mark.parametrize(
        "kwargs,message",
        [(k, m) for _, k, m in INVALID_CASES],
        ids=[d for d, _, _ in INVALID_CASES],
    )
    def test_rejects(self, kwargs, message):
        with pytest.raises(ValidationError) as exc_info:
            QuestionCreate(**_create(**kwargs))
        assert message in str(exc_info.value)

    @pytest.mark.parametrize(
        "kwargs", [k for _, k in VALID_CASES], ids=[d for d, _ in VALID_CASES]
    )
    def test_accepts(self, kwargs):
        q = QuestionCreate(**_create(**kwargs))
        assert q.type == "put_in_order"

    def test_items_are_stored_unstripped(self):
        q = QuestionCreate(**_create(items=[" A ", "B", "C"]))
        assert q.config["items"] == [" A ", "B", "C"]


class TestValidatePutInOrderHelper:
    """The helper the update path calls directly gives the same verdicts."""

    @pytest.mark.parametrize(
        "kwargs,message",
        [(k, m) for _, k, m in INVALID_CASES],
        ids=[d for d, _, _ in INVALID_CASES],
    )
    def test_rejects(self, kwargs, message):
        body = _create(**kwargs)
        with pytest.raises(ValueError) as exc_info:
            validate_put_in_order(
                body["grading_type"], body["config"], body["answer_data"]
            )
        assert str(exc_info.value) == message

    @pytest.mark.parametrize(
        "kwargs", [k for _, k in VALID_CASES], ids=[d for d, _ in VALID_CASES]
    )
    def test_accepts(self, kwargs):
        body = _create(**kwargs)
        validate_put_in_order(body["grading_type"], body["config"], body["answer_data"])


# ---------------------------------------------------------------------------
# Reveal parity across the four copies
# ---------------------------------------------------------------------------

PARITY_QUESTIONS = {
    "accuracy": (
        SimpleNamespace(
            type="put_in_order",
            grading_type="ACCURACY",
            answer_data={"correct_order": [1, 3, 0, 2]},
            points_value=1.0,
        ),
        {"type": "put_in_order", "correctOrder": [1, 3, 0, 2]},
    ),
    "completeness_with_order": (
        SimpleNamespace(
            type="put_in_order",
            grading_type="COMPLETENESS",
            answer_data={"correct_order": [1, 3, 0, 2]},
            points_value=1.0,
        ),
        {"type": "completeness", "correctOrder": [1, 3, 0, 2]},
    ),
    "completeness_without_order": (
        SimpleNamespace(
            type="put_in_order",
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


# ---------------------------------------------------------------------------
# CSV rounding
# ---------------------------------------------------------------------------

NOISY = [0.8299999833106995, 0.6700000166893005, 0.125]


def _result(items):
    r = MagicMock()
    r.scalars.return_value.all.return_value = items
    return r


def _csv_db():
    questions = [
        SimpleNamespace(id=i + 1, prompt=f"Q{i + 1}", points_value=pv)
        for i, pv in enumerate(NOISY)
    ]
    scores = [
        SimpleNamespace(user_id=uid, question_id=q.id, points_awarded=q.points_value)
        for uid in ("u1", "u2")
        for q in questions
    ]
    users = [
        SimpleNamespace(
            id=uid, display_name=uid, username=uid, netid=f"net_{uid}", role="USER"
        )
        for uid in ("u1", "u2")
    ]
    session = SimpleNamespace(id="sess-12345678", game_id=1, course_id=1)
    course = SimpleNamespace(name="CS", semester="Fall")

    db = AsyncMock()

    async def get(model, _id):
        return {GameSession: session, Course: course}.get(model)

    db.get.side_effect = get
    # build_session_csv: questions, scores, users. build_canvas_csv adds roster.
    db.execute.side_effect = [
        _result(questions),
        _result(scores),
        _result(users),
        _result([]),
    ]
    return db


def _numeric_cells(content: bytes) -> list[str]:
    cells = []
    for row in csv.reader(io.StringIO(content.decode())):
        for cell in row:
            try:
                float(cell)
            except ValueError:
                continue
            cells.append(cell)
    return cells


def _decimals(cell: str) -> int:
    return len(cell.split(".")[1]) if "." in cell else 0


async def test_session_csv_rounds_points():
    _, content = await export_service.build_session_csv(_csv_db(), "sess-12345678")
    cells = _numeric_cells(content)
    assert cells, content
    assert all(_decimals(c) <= 4 for c in cells), cells
    assert "0.125" in cells
    assert "1.625" in cells  # per-player total


@pytest.mark.parametrize("per_question", [False, True])
async def test_canvas_csv_rounds_points(per_question):
    _, content = await export_service.build_canvas_csv(
        _csv_db(), "sess-12345678", per_question=per_question
    )
    cells = _numeric_cells(content)
    assert cells, content
    assert all(_decimals(c) <= 4 for c in cells), cells
    if per_question:
        assert "0.125" in cells
    else:
        assert "1.625" in cells  # "Points Possible" and each total
