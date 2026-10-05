"""
Pure helpers for the pin_the_spot question type (docs/design-pin-the-spot.md).

Shared by game_service (scoring, distribution, summary reveals), websocket/gateway.py
(submission check, live reveal) and report_service (HTML report), so the type's rules
live in one place instead of four copies. No DB, Redis or I/O here.

Coordinates are fractions of the image (0..1, origin top-left). Radii are fractions of
the image width; vertical distance is scaled by aspect = height / width so circles stay
round on non-square images.
"""

from __future__ import annotations

import math
from decimal import ROUND_HALF_UP, Decimal

# Float subtraction puts a tap "exactly on" a circle a hair outside it (0.55 - 0.5 is
# 0.05000000000000004), so both edges are compared with this tolerance.
EDGE_EPSILON = 1e-9


def is_valid_tap(answer: object) -> bool:
    """A submission is exactly {x, y}: finite real numbers (not bools) from 0 to 1."""
    if not isinstance(answer, dict) or set(answer) != {"x", "y"}:
        return False
    return all(
        type(v) in (int, float) and math.isfinite(v) and 0 <= v <= 1
        for v in (answer["x"], answer["y"])
    )


def tap_key(answer: dict) -> str:
    """Distribution key for a valid tap: "x,y", each rounded to 4 decimal places."""
    return f"{answer['x']:.4f},{answer['y']:.4f}"


def tap_distance(tap: dict, target: dict, aspect: float) -> float:
    """Distance in image-width units, with the vertical difference scaled by aspect."""
    return math.hypot(tap["x"] - target["x"], (tap["y"] - target["y"]) * aspect)


def score(
    tap: dict, answer_data: dict, aspect: float, points_value: float
) -> tuple[float, bool]:
    """
    (points, is_correct) for a valid tap under ACCURACY grading.

    Full points within r_full (inclusive), 0 at or beyond r_zero, linear in between,
    rounded half-up to 2 dp and clamped to points_value. Correct = inside r_full.
    """
    d = tap_distance(tap, answer_data["target"], aspect)
    r_full, r_zero = answer_data["r_full"], answer_data["r_zero"]
    if d <= r_full + EDGE_EPSILON:
        return points_value, True
    if d >= r_zero - EDGE_EPSILON:
        return 0.0, False
    # round(pv, 6) strips float32 read-back noise before the half-up step, as put_in_order does.
    fraction = Decimal(repr((r_zero - d) / (r_zero - r_full)))
    raw = (Decimal(str(round(points_value, 6))) * fraction).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )
    return min(float(raw), points_value), False


def reveal(grading_type: str, answer_data: dict | None) -> dict:
    """
    Client-safe reveal. ACCURACY → {type: "pin_the_spot", target, rFull, rZero};
    COMPLETENESS → {type: "completeness"}, plus target/rFull/rZero when a target is set.
    """
    answer_data = answer_data or {}
    target_fields = (
        {
            "target": answer_data["target"],
            "rFull": answer_data["r_full"],
            "rZero": answer_data["r_zero"],
        }
        if "target" in answer_data
        else {}
    )
    if grading_type == "COMPLETENESS":
        return {"type": "completeness", **target_fields}
    return {"type": "pin_the_spot", **target_fields}
