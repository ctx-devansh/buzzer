"""
Pin the Spot rules: the single source of truth for validating, keying, scoring and
revealing a tap (docs/design-pin-the-spot.md, section 6).

Pure functions only (no DB, no Redis), so calculate_score, record_answer and all four
reveal builders share one implementation.

Coordinates are fractions of the image ([0, 1], origin top-left); radii are fractions of the
image *width*; the vertical difference is scaled by aspect (height / width) so circles stay
round on non-square images.
"""

from __future__ import annotations

import math
from decimal import ROUND_HALF_UP, Decimal

# 0.55 - 0.5 == 0.05000000000000004: a tap drawn exactly on a circle must count as on it.
EDGE_EPSILON = 1e-9


def _is_real_number(value: object) -> bool:
    """A finite int/float that is not a bool (True is an int; json accepts NaN)."""
    return type(value) in (int, float) and math.isfinite(value)  # type: ignore[arg-type]


def half_up_points(
    points_value: float, numerator: Decimal | int, denominator: int = 1
) -> float:
    """points_value * numerator / denominator, rounded half-up to 2 dp, clamped to points_value.

    round(pv, 6) strips float32 read-back noise before the half-up step; the min() clamp keeps
    a >2dp points_value from being exceeded. Shared with put_in_order's partial credit.
    """
    raw = (Decimal(str(round(points_value, 6))) * numerator / denominator).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )
    return min(float(raw), points_value)


def is_valid_tap(submission: object) -> bool:
    """Exactly {x, y}, each a finite non-bool number in [0, 1]."""
    return (
        isinstance(submission, dict)
        and set(submission) == {"x", "y"}
        and all(
            _is_real_number(submission[k]) and 0 <= submission[k] <= 1
            for k in ("x", "y")
        )
    )


def tap_key(submission: dict) -> str:
    """Distribution-hash key for a valid tap, e.g. "0.4000,0.6300"."""
    return f"{submission['x']:.4f},{submission['y']:.4f}"


def parse_tap_key(key: str) -> tuple[float, float] | None:
    """Inverse of tap_key, for readers of a distribution (None if malformed)."""
    parts = key.split(",")
    if len(parts) != 2:
        return None
    try:
        x, y = float(parts[0]), float(parts[1])
    except ValueError:
        return None
    if not (math.isfinite(x) and math.isfinite(y)):
        return None
    return x, y


def aspect(config: dict | None) -> float | None:
    """height / width from config, or None if the stored size is unusable."""
    config = config or {}
    width, height = config.get("image_width"), config.get("image_height")
    if type(width) is not int or type(height) is not int or width <= 0 or height <= 0:
        return None
    return height / width


def answer_key(answer_data: dict | None) -> tuple[dict, float, float] | None:
    """(target, r_full, r_zero) if the stored answer key is well formed, else None."""
    answer_data = answer_data or {}
    target = answer_data.get("target")
    r_full, r_zero = answer_data.get("r_full"), answer_data.get("r_zero")
    if not is_valid_tap(target):
        return None
    if not (_is_real_number(r_full) and _is_real_number(r_zero)):
        return None
    if not (0 < r_full < r_zero):
        return None
    return target, float(r_full), float(r_zero)


def tap_distance(tap: dict, target: dict, aspect_ratio: float) -> float:
    """Distance in image-width units, vertical difference scaled by aspect."""
    dx = tap["x"] - target["x"]
    dy = (tap["y"] - target["y"]) * aspect_ratio
    return math.sqrt(dx * dx + dy * dy)


def score(
    grading_type: str,
    points_value: float,
    config: dict | None,
    answer_data: dict | None,
    submission: object,
) -> tuple[float, bool]:
    """(points_awarded, is_correct) for one tap. Never raises.

    Validity is checked before the COMPLETENESS short-circuit, so an invalid tap scores 0.
    A malformed stored ACCURACY question scores 0 rather than raising.
    """
    if not is_valid_tap(submission):
        return 0, False
    if grading_type == "COMPLETENESS":
        return points_value, True
    key = answer_key(answer_data)
    aspect_ratio = aspect(config)
    if key is None or aspect_ratio is None:
        return 0, False
    target, r_full, r_zero = key
    d = tap_distance(submission, target, aspect_ratio)  # type: ignore[arg-type]
    if d <= r_full + EDGE_EPSILON:
        return points_value, True
    if d >= r_zero - EDGE_EPSILON:
        return 0, False
    fraction = (r_zero - d) / (r_zero - r_full)
    return half_up_points(points_value, Decimal(str(fraction))), False


def reveal(grading_type: str, answer_data: dict | None) -> dict:
    """The reveal payload, identical in all four builders.

    ACCURACY: {type: "pin_the_spot", target, rFull, rZero}.
    COMPLETENESS: {type: "completeness"} plus target/rFull/rZero when a target is set.
    A malformed answer key omits target/radii; clients then draw taps only.
    """
    payload: dict = {
        "type": "pin_the_spot" if grading_type == "ACCURACY" else "completeness"
    }
    key = answer_key(answer_data)
    if key is not None:
        target, r_full, r_zero = key
        payload.update(
            {
                "target": {"x": target["x"], "y": target["y"]},
                "rFull": r_full,
                "rZero": r_zero,
            }
        )
    return payload
