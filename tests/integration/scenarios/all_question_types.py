"""
Core coverage scenarios: every question type × grading combination, with
players that answer correctly, incorrectly, and not at all.

Adding a new question type:
  1. Add a QuestionSpec for it here.
  2. Add a corresponding case to engine/scoring.py:compute_question_score().
  3. The test_game_flow parametrize picks it up automatically.
"""
from __future__ import annotations

from ..engine.scoring import GameScenario, PlayerScript, QuestionSpec

# ---------------------------------------------------------------------------
# Reusable question specs — multiple_choice and true_false
# ---------------------------------------------------------------------------

# Multiple-choice ACCURACY — correct answer is index 1 (Mercury, 1000 pts)
MC_ACCURACY = QuestionSpec(
    type="multiple_choice",
    grading_type="ACCURACY",
    prompt="Which planet is closest to the Sun?",
    config={"options": ["Venus", "Mercury", "Mars", "Earth"]},
    answer_data={"answer_points": [0, 1000, 0, 0]},
    points_value=1000,
)

# Multiple-choice COMPLETENESS — any answer earns full points
MC_COMPLETENESS = QuestionSpec(
    type="multiple_choice",
    grading_type="COMPLETENESS",
    prompt="Which of these is your favourite colour?",
    config={"options": ["Red", "Blue", "Green"]},
    answer_data={"answer_points": [1000, 1000, 1000]},
    points_value=1000,
)

# True/False ACCURACY — correct answer is True (1000 pts)
TF_ACCURACY_TRUE = QuestionSpec(
    type="true_false",
    grading_type="ACCURACY",
    prompt="Water boils at 100 °C at sea level.",
    config={},
    answer_data={"answer_points": {"true": 1000, "false": 0}},
    points_value=1000,
)

# True/False ACCURACY — correct answer is False (1000 pts)
TF_ACCURACY_FALSE = QuestionSpec(
    type="true_false",
    grading_type="ACCURACY",
    prompt="The Great Wall of China is visible from space with the naked eye.",
    config={},
    answer_data={"answer_points": {"true": 0, "false": 1000}},
    points_value=1000,
)

# True/False COMPLETENESS — any answer earns full points
TF_COMPLETENESS = QuestionSpec(
    type="true_false",
    grading_type="COMPLETENESS",
    prompt="Would you visit Mars if given the chance?",
    config={},
    answer_data={"answer_points": {"true": 1000, "false": 1000}},
    points_value=1000,
)

# MC ACCURACY with many options — tests 10-option questions
MC_MANY_OPTIONS = QuestionSpec(
    type="multiple_choice",
    grading_type="ACCURACY",
    prompt="Which country has the largest land area?",
    config={"options": [
        "Canada", "Russia", "China", "USA",
        "Brazil", "Australia", "India", "Argentina",
        "Kazakhstan", "Algeria",
    ]},
    # Russia (index 1) is correct
    answer_data={"answer_points": [0, 1000, 0, 0, 0, 0, 0, 0, 0, 0]},
    points_value=1000,
)

# ---------------------------------------------------------------------------
# Reusable question specs — fill_in_the_blank
# ---------------------------------------------------------------------------

# FITB ACCURACY, editDistance=0: only exact (case-insensitive, whitespace-normalised)
# matches are accepted.
FITB_ACCURACY_EXACT = QuestionSpec(
    type="fill_in_the_blank",
    grading_type="ACCURACY",
    prompt="What chess piece can only move diagonally?",
    config={"maxLength": 30},
    answer_data={"acceptedAnswers": ["bishop"], "answerPoints": [1000], "editDistance": 0},
    points_value=1000,
)

# FITB ACCURACY, editDistance=1: one-character typos are forgiven.
# "Nill" (edit distance 1 from "nile") should earn full points.
FITB_ACCURACY_FUZZY = QuestionSpec(
    type="fill_in_the_blank",
    grading_type="ACCURACY",
    prompt="What is the name of the longest river in Africa?",
    config={"maxLength": 30},
    answer_data={"acceptedAnswers": ["Nile", "the Nile"], "answerPoints": [1000, 1000], "editDistance": 1},
    points_value=1000,
)

# FITB COMPLETENESS: any non-empty answer earns full points; no correct answer.
FITB_COMPLETENESS = QuestionSpec(
    type="fill_in_the_blank",
    grading_type="COMPLETENESS",
    prompt="Name your favourite season.",
    config={"maxLength": 30},
    answer_data={},
    points_value=1000,
)

# ---------------------------------------------------------------------------
# Player answer helpers
# ---------------------------------------------------------------------------

def _correct(q: QuestionSpec) -> dict:
    """Return the first correct answer for a question."""
    if q.type == "multiple_choice":
        pts = q.answer_data["answer_points"]
        idx = next(i for i, p in enumerate(pts) if p == q.points_value)
        return {"selectedIndex": idx}
    if q.type == "true_false":
        pts = q.answer_data["answer_points"]
        correct_val = pts.get("true", 0) >= q.points_value
        return {"selectedValue": correct_val}
    if q.type == "fill_in_the_blank":
        return {"text": q.answer_data["acceptedAnswers"][0]}
    raise NotImplementedError(f"No _correct helper for type {q.type!r}")


def _wrong(q: QuestionSpec) -> dict:
    """Return a wrong answer for a question."""
    if q.type == "multiple_choice":
        pts = q.answer_data["answer_points"]
        idx = next(i for i, p in enumerate(pts) if p < q.points_value)
        return {"selectedIndex": idx}
    if q.type == "true_false":
        pts = q.answer_data["answer_points"]
        correct_val = pts.get("true", 0) >= q.points_value
        return {"selectedValue": not correct_val}
    if q.type == "fill_in_the_blank":
        # "xxxxxxxx" has high edit distance from any realistic answer
        return {"text": "xxxxxxxx"}
    raise NotImplementedError(f"No _wrong helper for type {q.type!r}")


def _any(q: QuestionSpec) -> dict:
    """Return any valid answer (used for COMPLETENESS questions)."""
    if q.type == "multiple_choice":
        return {"selectedIndex": 0}
    if q.type == "true_false":
        return {"selectedValue": True}
    if q.type == "fill_in_the_blank":
        return {"text": "anything"}
    raise NotImplementedError(f"No _any helper for type {q.type!r}")


# ---------------------------------------------------------------------------
# Scenarios — multiple_choice / true_false (existing)
# ---------------------------------------------------------------------------

ALL_TYPES = GameScenario(
    name="all_types_and_grading",
    description=(
        "One question of every type×grading combination. "
        "Four players: all-correct, all-wrong, all-skip, mixed."
    ),
    questions=[
        MC_ACCURACY,
        MC_COMPLETENESS,
        TF_ACCURACY_TRUE,
        TF_ACCURACY_FALSE,
        TF_COMPLETENESS,
        MC_MANY_OPTIONS,
    ],
    player_scripts=[
        # Player 0 — answers every question correctly / with any valid answer
        PlayerScript(responses=[
            _correct(MC_ACCURACY),
            _any(MC_COMPLETENESS),
            _correct(TF_ACCURACY_TRUE),
            _correct(TF_ACCURACY_FALSE),
            _any(TF_COMPLETENESS),
            _correct(MC_MANY_OPTIONS),
        ]),
        # Player 1 — answers every question wrong (COMPLETENESS still earns pts)
        PlayerScript(responses=[
            _wrong(MC_ACCURACY),
            _any(MC_COMPLETENESS),    # wrong answer still earns on COMPLETENESS
            _wrong(TF_ACCURACY_TRUE),
            _wrong(TF_ACCURACY_FALSE),
            _any(TF_COMPLETENESS),
            _wrong(MC_MANY_OPTIONS),
        ]),
        # Player 2 — skips every question
        PlayerScript(responses=[None, None, None, None, None, None]),
        # Player 3 — mixed: some correct, some wrong, some skipped
        PlayerScript(responses=[
            _correct(MC_ACCURACY),      # correct
            None,                        # skip COMPLETENESS
            _wrong(TF_ACCURACY_TRUE),   # wrong
            None,                        # skip ACCURACY
            _any(TF_COMPLETENESS),      # answered
            _correct(MC_MANY_OPTIONS),  # correct
        ]),
    ],
)


SINGLE_PLAYER = GameScenario(
    name="single_player_all_correct",
    description="One player answers every question correctly. Simplest smoke test.",
    questions=[MC_ACCURACY, TF_ACCURACY_TRUE, TF_ACCURACY_FALSE, MC_COMPLETENESS],
    player_scripts=[
        PlayerScript(responses=[
            _correct(MC_ACCURACY),
            _correct(TF_ACCURACY_TRUE),
            _correct(TF_ACCURACY_FALSE),
            _any(MC_COMPLETENESS),
        ]),
    ],
)


# ---------------------------------------------------------------------------
# Scenario — fill_in_the_blank (all variations)
# ---------------------------------------------------------------------------

FITB_TYPES = GameScenario(
    name="fill_in_the_blank_variations",
    description=(
        "Three FITB questions (exact-match ACCURACY, fuzzy ACCURACY, COMPLETENESS). "
        "Four players exercise: exact match, case-insensitive match, whitespace "
        "normalisation, within-edit-distance match, wrong answer, and skip."
    ),
    questions=[FITB_ACCURACY_EXACT, FITB_ACCURACY_FUZZY, FITB_COMPLETENESS],
    player_scripts=[
        # Player 0 — exact correct answers on every question
        #   Q1: "bishop"  → exact match → 1000 pts
        #   Q2: "Nile"    → exact match → 1000 pts
        #   Q3: "summer"  → COMPLETENESS → 1000 pts
        PlayerScript(responses=[
            {"text": "bishop"},
            {"text": "Nile"},
            {"text": "summer"},
        ]),

        # Player 1 — case-insensitive and within-edit-distance variations
        #   Q1: "BISHOP"  → case-normalised to "bishop" → exact match → 1000 pts
        #   Q2: "Nill"    → normalised "nill"; levenshtein("nill","nile")=1 ≤ 1 → 1000 pts
        #   Q3: "WINTER"  → COMPLETENESS, any text → 1000 pts
        PlayerScript(responses=[
            {"text": "BISHOP"},
            {"text": "Nill"},
            {"text": "WINTER"},
        ]),

        # Player 2 — whitespace-normalised correct, wrong on fuzzy, correct on completeness
        #   Q1: "  bishop  " → stripped to "bishop" → exact match → 1000 pts
        #   Q2: "Amazon"     → "amazon"; levenshtein("amazon","nile")=5 > 1 → 0 pts
        #   Q3: "pizza"      → COMPLETENESS → 1000 pts
        PlayerScript(responses=[
            {"text": "  bishop  "},
            {"text": "Amazon"},
            {"text": "pizza"},
        ]),

        # Player 3 — wrong answer on exact, skip on fuzzy, skip on completeness
        #   Q1: "rook"  → "rook"; levenshtein("rook","bishop")=5 > 0 → 0 pts
        #   Q2: None    → skip → 0 pts
        #   Q3: None    → skip → 0 pts (even COMPLETENESS scores 0 for no answer)
        PlayerScript(responses=[
            {"text": "rook"},
            None,
            None,
        ]),
    ],
)


# ---------------------------------------------------------------------------
# Scenario — put_in_order (pairwise partial credit)
# ---------------------------------------------------------------------------

# Display order [C, A, D, B]; correct order A, B, C, D → correct_order [1, 3, 0, 2].
# 4 items → t = 6 pairs; one adjacent swap leaves c = 5 → round_half_up(5/6) = 0.83.
PIO_ACCURACY = QuestionSpec(
    type="put_in_order",
    grading_type="ACCURACY",
    prompt="Put the letters in alphabetical order.",
    config={"items": ["C", "A", "D", "B"]},
    answer_data={"correct_order": [1, 3, 0, 2]},
    points_value=1,
)

PIO_COMPLETENESS = QuestionSpec(
    type="put_in_order",
    grading_type="COMPLETENESS",
    prompt="Put the letters in the order you like best.",
    config={"items": ["C", "A", "D", "B"]},
    answer_data={"correct_order": [1, 3, 0, 2]},
    points_value=1,
)

PUT_IN_ORDER = GameScenario(
    name="put_in_order_scoring",
    description=(
        "put_in_order under ACCURACY (pairwise partial credit) and COMPLETENESS. "
        "Players: perfect order, one adjacent swap, reversed, no answer."
    ),
    questions=[PIO_ACCURACY, PIO_COMPLETENESS],
    player_scripts=[
        # Perfect — ACCURACY 1 (isCorrect), COMPLETENESS 1 → total 2
        PlayerScript(responses=[{"orderedIndices": [1, 3, 0, 2]}] * 2),
        # One adjacent swap (B, A, C, D) — ACCURACY 0.83, COMPLETENESS 1 → 1.83
        PlayerScript(responses=[{"orderedIndices": [3, 1, 0, 2]}] * 2),
        # Reversed (D, C, B, A) — ACCURACY 0, COMPLETENESS 1 → 1
        PlayerScript(responses=[{"orderedIndices": [2, 0, 3, 1]}] * 2),
        # No answer — 0 and 0
        PlayerScript(responses=[None, None]),
    ],
)


# ---------------------------------------------------------------------------
# Scenario — pin_the_spot (distance scoring with linear falloff)
# ---------------------------------------------------------------------------

# A 1x1 PNG; scoring never looks at the image, only at the stored width/height.
PIN_IMAGE = (
    "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk"
    "+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
)

# Square image, target centre, r_full 0.05, r_zero 0.20, points 1000 (the §6 table).
PIN_ACCURACY = QuestionSpec(
    type="pin_the_spot",
    grading_type="ACCURACY",
    prompt="Tap the centre.",
    config={"image_url": PIN_IMAGE, "image_width": 100, "image_height": 100},
    answer_data={"target": {"x": 0.5, "y": 0.5}, "r_full": 0.05, "r_zero": 0.2},
    points_value=1000,
)

# 2:1 image (aspect 0.5): a vertical miss of 0.25 is 0.125 width units → half credit.
PIN_WIDE = QuestionSpec(
    type="pin_the_spot",
    grading_type="ACCURACY",
    prompt="Tap the centre of the wide image.",
    config={"image_url": PIN_IMAGE, "image_width": 200, "image_height": 100},
    answer_data={"target": {"x": 0.5, "y": 0.5}, "r_full": 0.05, "r_zero": 0.2},
    points_value=1000,
)

PIN_COMPLETENESS = QuestionSpec(
    type="pin_the_spot",
    grading_type="COMPLETENESS",
    prompt="Tap anywhere you like.",
    config={"image_url": PIN_IMAGE, "image_width": 100, "image_height": 100},
    answer_data={},
    points_value=1000,
)

PIN_THE_SPOT = GameScenario(
    name="pin_the_spot_scoring",
    description=(
        "pin_the_spot ACCURACY (square and 2:1), COMPLETENESS. Players: inside r_full, "
        "halfway, on the r_full edge, beyond r_zero, no answer."
    ),
    questions=[PIN_ACCURACY, PIN_WIDE, PIN_COMPLETENESS],
    player_scripts=[
        # Inside r_full → 1000 (isCorrect); wide, vertical 0.25 → 500; COMPLETENESS 1000
        PlayerScript(responses=[{"x": 0.53, "y": 0.5}, {"x": 0.5, "y": 0.75}, {"x": 0.1, "y": 0.9}]),
        # Halfway (d 0.125) → 500; wide, horizontal 0.125 → 500; COMPLETENESS 1000
        PlayerScript(responses=[{"x": 0.625, "y": 0.5}, {"x": 0.625, "y": 0.5}, {"x": 0, "y": 0}]),
        # On the r_full edge (float noise) → 1000; same tap as player 1 (shared key); 1000
        PlayerScript(responses=[{"x": 0.55, "y": 0.5}, {"x": 0.5, "y": 0.75}, {"x": 1, "y": 1}]),
        # Beyond r_zero → 0; on the r_zero edge → 0; no answer
        PlayerScript(responses=[{"x": 0.95, "y": 0.95}, {"x": 0.7, "y": 0.5}, None]),
    ],
)


SCENARIOS: list[GameScenario] = [ALL_TYPES, SINGLE_PLAYER, FITB_TYPES, PUT_IN_ORDER, PIN_THE_SPOT]
