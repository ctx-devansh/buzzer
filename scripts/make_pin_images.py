#!/usr/bin/env python3
"""
make_pin_images.py — render the Pin the Spot images in sample_games/ and write their targets.

The images and their targets come only from here (docs/design-t6-sample-games.md §5.3): each
target is computed from the drawing's own coordinates, never typed in by hand. The script
touches only the questions in PLAN, and only their `config` and `answer_data`.

Prerequisites:
    pip install "pillow>=10.1"

Usage:
    # Re-render; rewrite only the rows whose stored image/target differs from the render
    python scripts/make_pin_images.py

    # Write nothing; print every difference and exit 1 if there is any
    python scripts/make_pin_images.py --check

Exit codes: 0 clean/written, 1 differences found (--check), 2 a PLAN row no longer matches its
file (questions reordered or edited) — nothing is written.
"""

from __future__ import annotations

import argparse
import base64
import binascii
import colorsys
import io
import json
import math
import sys
from dataclasses import dataclass
from functools import cache
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFont, ImageStat

ROOT = Path(__file__).resolve().parents[1]
GAMES_DIR = ROOT / "sample_games"

BG = "#1e293b"
LIGHT = "#f8fafc"
DARK = "#0f172a"
LINE = "#94a3b8"
HOST_FILL = "#cbd5e1"

DATA_URL_PREFIX = "data:image/png;base64,"
# Mean absolute difference over all RGB channels (0–255) above which a stored image counts as
# a different drawing. Absorbs antialiasing/text-rendering drift across Pillow versions.
PIXEL_TOLERANCE = 2.0


class PlanError(ValueError):
    """A PLAN row no longer matches the question at its index."""


@dataclass(frozen=True)
class Row:
    file: str  # file name under sample_games/
    index: int  # 1-based question number
    prefix: str  # the prompt must start with this
    key: str  # image key passed to render()
    grading: str  # "ACCURACY" or "COMPLETENESS"
    r_full: float | None = None
    r_zero: float | None = None

    def label(self) -> str:
        return f"{self.file} Q{self.index} ({self.key})"


PARTY = "party_night_point_pick_rank.json"
CLASSROOM = "intro_networking_classroom.json"

PLAN: tuple[Row, ...] = (
    Row(PARTY, 3, "Pin the colour", "rainbow", "ACCURACY", 0.03, 0.10),
    Row(PARTY, 7, "The hands fell off", "clock", "ACCURACY", 0.05, 0.20),
    Row(PARTY, 8, "Eyeball it", "number_line", "ACCURACY", 0.02, 0.12),
    Row(PARTY, 11, "No wrong answers", "rainbow", "COMPLETENESS"),
    Row(CLASSROOM, 8, "Host 10.0.1.10", "topology", "ACCURACY", 0.07, 0.13),
)


# ---------------------------------------------------------------------------
# Drawings — each returns the image and its target in pixels
# ---------------------------------------------------------------------------


def _rainbow() -> tuple[Image.Image, tuple[float, float]]:
    w, h = 720, 180
    x0, x1, y0, y1 = 36, 684, 76, 104
    img = Image.new("RGB", (w, h), BG)
    draw = ImageDraw.Draw(img)
    for x in range(x0, x1 + 1):
        hue = 360 * (x - x0) / (x1 - x0)  # wraps: x1 is red again
        rgb = tuple(round(c * 255) for c in colorsys.hsv_to_rgb(hue / 360, 1, 1))
        draw.line([(x, y0), (x, y1)], fill=rgb)
    yellow_x = x0 + (x1 - x0) * 60 / 360
    return img, (yellow_x, (y0 + y1) / 2)


def _clock() -> tuple[Image.Image, tuple[float, float]]:
    size, c, radius = 480, 240, 216
    img = Image.new("RGB", (size, size), BG)
    draw = ImageDraw.Draw(img)
    draw.ellipse(
        [c - radius, c - radius, c + radius, c + radius],
        fill=LIGHT,
        outline=DARK,
        width=4,
    )

    def tick_point(hour: int, r: float) -> tuple[float, float]:
        angle = math.radians(hour * 30)  # clockwise from 12
        return c + r * math.sin(angle), c - r * math.cos(angle)

    for hour in range(12):
        major = hour % 3 == 0
        r_in, width = (158, 10) if major else (176, 5)
        draw.line(
            [tick_point(hour, r_in), tick_point(hour, 202)], fill=DARK, width=width
        )
    draw.ellipse([c - 8, c - 8, c + 8, c + 8], fill=DARK)
    return img, tick_point(3, (158 + 202) / 2)  # the minute hand at quarter past


def _number_line() -> tuple[Image.Image, tuple[float, float]]:
    w, h = 800, 160
    img = Image.new("RGB", (w, h), BG)
    draw = ImageDraw.Draw(img)
    draw.rectangle([38, 77, 762, 83], fill=LIGHT)
    for x in (40, 400, 760):
        draw.rectangle([x - 2, 52, x + 2, 108], fill=LIGHT)
    return img, (40 + 7.2 * 73, 80)


def _box(cx: float, cy: float, w: int, h: int) -> list[float]:
    return [cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2]


def _topology() -> tuple[Image.Image, tuple[float, float]]:
    w, h = 800, 450
    img = Image.new("RGB", (w, h), BG)
    draw = ImageDraw.Draw(img)
    s1, router, s2 = (220, 225), (400, 225), (580, 225)
    hosts = {
        (70, 130): (s1, "10.0.1.10"),
        (70, 320): (s1, "10.0.1.11"),
        (730, 130): (s2, "10.0.2.20"),
        (730, 320): (s2, "10.0.2.21"),
    }

    for a, b in [(s1, router), (router, s2)] + [
        (hc, sw) for hc, (sw, _) in hosts.items()
    ]:
        draw.line([a, b], fill=LINE, width=4)
    for centre in (s1, router, s2):  # identical and unlabelled on purpose (design A4)
        draw.rounded_rectangle(
            _box(*centre, 90, 60), radius=8, fill=LIGHT, outline=DARK, width=3
        )
    for centre in hosts:
        draw.rounded_rectangle(
            _box(*centre, 70, 46), radius=8, fill=HOST_FILL, outline=DARK, width=2
        )

    font = ImageFont.load_default(size=18)
    labels = [((hx, hy + 38), text) for (hx, hy), (_, text) in hosts.items()]
    labels += [
        ((310, 200), "10.0.1.1"),
        ((490, 200), "10.0.2.1"),
        ((145, 415), "10.0.1.0/24"),
        ((655, 415), "10.0.2.0/24"),
    ]
    for xy, text in labels:
        draw.text(xy, text, fill=LIGHT, font=font, anchor="mm")
    return img, router


_DRAWINGS = {
    "rainbow": _rainbow,
    "clock": _clock,
    "number_line": _number_line,
    "topology": _topology,
}


@cache
def _render_cached(key: str) -> tuple[Image.Image, tuple[float, float]]:
    img, (px, py) = _DRAWINGS[key]()
    w, h = img.size
    return img, (round(px / w, 4), round(py / h, 4))


def render(key: str) -> tuple[Image.Image, tuple[float, float]]:
    """The image for `key` and its target as fractions of width/height, rounded to 4 dp."""
    img, target = _render_cached(key)
    return img.copy(), target


# ---------------------------------------------------------------------------
# Plan verification, comparison and writing
# ---------------------------------------------------------------------------


def _load(file: str) -> dict:
    """A PLAN file's bundle; PlanError if it is missing or isn't a game bundle."""
    path = GAMES_DIR / file
    try:
        bundle = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise PlanError(f"{file}: not found in {GAMES_DIR}") from None
    except json.JSONDecodeError as exc:
        raise PlanError(f"{file}: not valid JSON ({exc})") from None
    if not isinstance(bundle, dict) or not isinstance(bundle.get("questions"), list):
        raise PlanError(f"{file}: no top-level 'questions' list")
    return bundle


def verify_plan(bundles: dict[str, dict]) -> None:
    """Raise PlanError if any PLAN row doesn't match the question at its index."""
    for row in PLAN:
        questions = bundles[row.file]["questions"]
        if not 1 <= row.index <= len(questions):
            raise PlanError(
                f"{row.label()}: no question {row.index} (file has {len(questions)})"
            )
        q = questions[row.index - 1]
        if q.get("type") != "pin_the_spot":
            raise PlanError(
                f"{row.label()}: type is {q.get('type')!r}, expected 'pin_the_spot'"
            )
        if q.get("grading_type") != row.grading:
            raise PlanError(
                f"{row.label()}: grading_type is {q.get('grading_type')!r}, expected {row.grading!r}"
            )
        if not str(q.get("prompt", "")).startswith(row.prefix):
            raise PlanError(f"{row.label()}: prompt doesn't start with {row.prefix!r}")


def _expected_answer_data(row: Row) -> dict:
    if row.grading == "COMPLETENESS":
        return {}
    tx, ty = render(row.key)[1]
    return {"target": {"x": tx, "y": ty}, "r_full": row.r_full, "r_zero": row.r_zero}


def _decode(image_url: object) -> Image.Image | None:
    if not isinstance(image_url, str) or not image_url.startswith(DATA_URL_PREFIX):
        return None
    try:
        raw = base64.b64decode(image_url[len(DATA_URL_PREFIX) :], validate=True)
        img = Image.open(io.BytesIO(raw))
        img.load()
    except (binascii.Error, OSError, ValueError):
        return None
    return img if img.format == "PNG" else None


def _difference(row: Row, q: dict) -> str | None:
    """The first reason this row's stored data differs from the render, or None."""
    img, _ = _render_cached(row.key)
    config = q.get("config")
    if not isinstance(config, dict) or set(config) != {
        "image_url",
        "image_width",
        "image_height",
    }:
        return "config keys aren't exactly image_url/image_width/image_height"
    stored = _decode(config["image_url"])
    if stored is None:
        return "image_url isn't a data:image/png;base64 URL that decodes to a PNG"
    if (
        config["image_width"],
        config["image_height"],
    ) != img.size or stored.size != img.size:
        return (
            f"size mismatch: stored {config['image_width']}x{config['image_height']}, "
            f"PNG {stored.size[0]}x{stored.size[1]}, render {img.size[0]}x{img.size[1]}"
        )
    expected = _expected_answer_data(row)
    if q.get("answer_data") != expected:
        return f"answer_data is {q.get('answer_data')!r}, expected {expected!r}"
    diff = ImageChops.difference(stored.convert("RGB"), img)
    mean = sum(ImageStat.Stat(diff).mean) / 3
    if mean > PIXEL_TOLERANCE:
        return f"pixels differ (mean abs difference {mean:.2f} > {PIXEL_TOLERANCE})"
    return None


def _differences(bundles: dict[str, dict]) -> list[tuple[Row, str]]:
    verify_plan(bundles)
    found = []
    for row in PLAN:
        reason = _difference(row, bundles[row.file]["questions"][row.index - 1])
        if reason is not None:
            found.append((row, reason))
    return found


def check() -> list[str]:
    """Every difference between sample_games/ and a fresh render; empty means clean.

    Raises PlanError if a PLAN row no longer matches its file.
    """
    bundles = {file: _load(file) for file in {row.file for row in PLAN}}
    return [f"{row.label()}: {reason}" for row, reason in _differences(bundles)]


def _data_url(img: Image.Image) -> str:
    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return DATA_URL_PREFIX + base64.b64encode(buf.getvalue()).decode("ascii")


def write() -> list[tuple[Row, bool]]:
    """Rewrite the rows that differ; return (row, updated) for every PLAN row."""
    bundles = {file: _load(file) for file in {row.file for row in PLAN}}
    to_update = {row for row, _ in _differences(bundles)}
    for row in to_update:
        q = bundles[row.file]["questions"][row.index - 1]
        img, _ = _render_cached(row.key)
        q["config"] = {
            "image_url": _data_url(img),
            "image_width": img.size[0],
            "image_height": img.size[1],
        }
        if row.grading == "ACCURACY":
            q["answer_data"] = _expected_answer_data(row)
    for file in {row.file for row in to_update}:
        text = json.dumps(bundles[file], indent=2, ensure_ascii=False) + "\n"
        (GAMES_DIR / file).write_text(text, encoding="utf-8")
    return [(row, row in to_update) for row in PLAN]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0].strip())
    ap.add_argument(
        "--check", action="store_true", help="write nothing; exit 1 on any difference"
    )
    args = ap.parse_args()
    try:
        if args.check:
            diffs = check()
            for line in diffs:
                print(line)
            return 1 if diffs else 0
        for row, updated in write():
            print(f"{row.label()}: {'updated' if updated else 'unchanged'}")
        return 0
    except PlanError as exc:
        print(f"plan mismatch, nothing written: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
