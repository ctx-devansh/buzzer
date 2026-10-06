#!/usr/bin/env python3
"""
make_pin_images.py — draw the Pin the Spot images for the T6 sample games and keep the
game files in sync with them.

Prerequisites:
    pip install "pillow>=10.1"

Usage:
    python scripts/make_pin_images.py           # render, rewrite only the rows that differ
    python scripts/make_pin_images.py --check   # report differences, write nothing

Each image is drawn from code, so its target is computed from the drawing's own coordinates
(docs/design-t6-sample-games.md §5.4). Questions are found by file, 1-based index and prompt
prefix (PLAN): the game JSON can't carry an id, because QuestionCreate forbids extra keys.

Exit codes: 0 = in sync (or written), 1 = --check found differences, 2 = the plan doesn't
match the game files (nothing is written). A usage error (bad argument) also exits 2.

Images are compared pixel for pixel. Font rendering can change between Pillow versions, so
after upgrading Pillow, re-run this script and set GENERATED_WITH_PILLOW to the new version.
"""

from __future__ import annotations

import argparse
import base64
import binascii
import io
import json
import sys
from dataclasses import dataclass
from pathlib import Path

import PIL
from PIL import Image, ImageChops, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
GAMES_DIR = ROOT / "sample_games"

DATA_URL_PREFIX = "data:image/png;base64,"
# The Pillow version the committed images were rendered with. Pixels are compared exactly
# (no tolerance can tell font drift from an answer-changing edit), so a different version
# may report commit_graph as changed: re-run the script and update this.
GENERATED_WITH_PILLOW = "12.3.0"

BACKGROUND = "#1e293b"
LIGHT = "#f8fafc"
DARK = "#0f172a"
LINE_GREY = "#94a3b8"


class PlanError(ValueError):
    """The plan table doesn't match the game files; nothing is written."""


@dataclass(frozen=True)
class PlanRow:
    file: str
    index: int  # 1-based
    prefix: str
    key: str
    grading: str
    r_full: float | None
    r_zero: float | None


PLAN: tuple[PlanRow, ...] = (
    PlanRow(
        "git_version_control_classroom.json",
        8,
        "The branches main and feature",
        "commit_graph",
        "ACCURACY",
        0.04,
        0.12,
    ),
    PlanRow(
        "game_night_mixed_bag_party.json",
        3,
        "Spot the odd one out",
        "odd_face",
        "ACCURACY",
        0.09,
        0.15,
    ),
    PlanRow(
        "game_night_mixed_bag_party.json",
        9,
        "No wrong answers",
        "party_room",
        "COMPLETENESS",
        None,
        None,
    ),
)


# --------------------------------------------------------------------------- drawings
# Each returns (image, target in pixels or None). Shapes are drawn in the order listed in
# the spec, so later shapes cover earlier ones.


def _commit_graph() -> tuple[Image.Image, tuple[int, int] | None]:
    img = Image.new("RGB", (800, 400), BACKGROUND)
    d = ImageDraw.Draw(img)
    main_y, feature_y = 260, 140
    main_x = [100, 220, 340, 460, 580]
    feature_x = [340, 460, 580]
    d.line([(100, main_y), (580, main_y)], fill=LINE_GREY, width=6)
    d.line([(220, main_y), (340, feature_y)], fill=LINE_GREY, width=6)
    d.line([(340, feature_y), (580, feature_y)], fill=LINE_GREY, width=6)
    for cx, cy in [(x, main_y) for x in main_x] + [(x, feature_y) for x in feature_x]:
        d.ellipse(
            (cx - 16, cy - 16, cx + 16, cy + 16), fill=LIGHT, outline=DARK, width=3
        )
    font = ImageFont.load_default(size=22)
    d.text((610, main_y), "main", fill=LIGHT, font=font, anchor="lm")
    d.text((610, feature_y), "feature", fill=LIGHT, font=font, anchor="lm")
    return img, (220, main_y)


def _odd_face() -> tuple[Image.Image, tuple[int, int] | None]:
    img = Image.new("RGB", (800, 600), BACKGROUND)
    d = ImageDraw.Draw(img)
    odd = (500, 300)
    for cy in (100, 300, 500):
        for cx in (100, 300, 500, 700):
            d.ellipse(
                (cx - 70, cy - 70, cx + 70, cy + 70),
                fill="#facc15",
                outline=DARK,
                width=3,
            )
            for ex in (cx - 25, cx + 25):
                d.ellipse((ex - 8, cy - 20 - 8, ex + 8, cy - 20 + 8), fill=DARK)
            if (cx, cy) == odd:
                d.arc(
                    (cx - 35, cy + 15, cx + 35, cy + 65), 200, 340, fill=DARK, width=6
                )
            else:
                d.arc((cx - 35, cy - 15, cx + 35, cy + 35), 20, 160, fill=DARK, width=6)
    return img, odd


def _party_room() -> tuple[Image.Image, tuple[int, int] | None]:
    img = Image.new("RGB", (800, 500), BACKGROUND)
    d = ImageDraw.Draw(img)
    d.rectangle((0, 0, 800, 330), fill="#334155")  # wall
    d.rectangle((0, 330, 800, 500), fill="#a16207")  # floor
    d.rectangle((80, 60, 260, 200), fill="#7dd3fc", outline=LIGHT, width=4)  # window
    d.line([(170, 60), (170, 200)], fill=LIGHT, width=4)
    d.line([(80, 130), (260, 130)], fill=LIGHT, width=4)
    d.rectangle((520, 90, 720, 210), fill="#0f172a", outline="#94a3b8", width=6)  # TV
    d.rectangle((605, 210, 635, 250), fill="#94a3b8")  # TV stand
    d.rounded_rectangle(
        (90, 250, 370, 310), radius=20, fill="#6d28d9"
    )  # couch backrest
    d.rounded_rectangle((90, 300, 370, 400), radius=20, fill="#7c3aed")  # couch seat
    d.rectangle((470, 360, 690, 380), fill="#d97706")  # table top
    d.rectangle((490, 380, 505, 450), fill="#d97706")  # legs
    d.rectangle((655, 380, 670, 450), fill="#d97706")
    d.ellipse((500, 330, 570, 362), fill="#f97316")  # bowls
    d.ellipse((590, 330, 660, 362), fill="#facc15")
    return img, None


_DRAWINGS = {
    "commit_graph": _commit_graph,
    "odd_face": _odd_face,
    "party_room": _party_room,
}


def render(key: str) -> tuple[Image.Image, tuple[float, float] | None]:
    """The image for `key` and its target as fractions of width/height (4 dp), or None."""
    img, target = _DRAWINGS[key]()
    if target is None:
        return img, None
    w, h = img.size
    return img, (round(target[0] / w, 4), round(target[1] / h, 4))


# --------------------------------------------------------------------------- plan + files


def _load(name: str) -> dict:
    path = GAMES_DIR / name
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise PlanError(f"{name}: plan file not found in {GAMES_DIR}") from None
    except (json.JSONDecodeError, UnicodeDecodeError) as e:
        raise PlanError(f"{name}: not valid JSON ({e})") from None
    if not isinstance(data, dict) or not isinstance(data.get("questions"), list):
        raise PlanError(f"{name}: no top-level 'questions' list")
    return data


def verify_plan() -> dict[str, dict]:
    """Load every plan file and check each row's question; raises PlanError on any mismatch."""
    bundles = {name: _load(name) for name in sorted({row.file for row in PLAN})}
    for row in PLAN:
        label = f"{row.file} Q{row.index} ({row.key})"
        questions = bundles[row.file]["questions"]
        if not 1 <= row.index <= len(questions):
            raise PlanError(f"{label}: no question at that index")
        q = questions[row.index - 1]
        if not isinstance(q, dict) or q.get("type") != "pin_the_spot":
            raise PlanError(f"{label}: not a pin_the_spot question")
        if q.get("grading_type") != row.grading:
            raise PlanError(f"{label}: grading_type is not {row.grading}")
        prompt = q.get("prompt")
        if not isinstance(prompt, str) or not prompt.startswith(row.prefix):
            raise PlanError(f"{label}: prompt does not start with {row.prefix!r}")
    return bundles


def _expected(row: PlanRow, img: Image.Image, target) -> tuple[dict, dict]:
    buf = io.BytesIO()
    img.save(buf, "PNG", optimize=True)
    w, h = img.size
    config = {
        "image_url": DATA_URL_PREFIX + base64.b64encode(buf.getvalue()).decode("ascii"),
        "image_width": w,
        "image_height": h,
    }
    if row.grading == "ACCURACY":
        answer_data = {
            "target": {"x": target[0], "y": target[1]},
            "r_full": row.r_full,
            "r_zero": row.r_zero,
        }
    else:
        answer_data = {}
    return config, answer_data


def _difference(
    row: PlanRow, q: dict, img: Image.Image, answer_data: dict, pixels: bool = True
) -> str | None:
    """The first --check difference for this row, or None."""
    config = q.get("config")
    if not isinstance(config, dict) or set(config) != {
        "image_url",
        "image_width",
        "image_height",
    }:
        return "config keys are not exactly image_url/image_width/image_height"
    url = config["image_url"]
    if not isinstance(url, str) or not url.startswith(DATA_URL_PREFIX):
        return "image_url is not a data:image/png;base64, URL"
    try:
        stored = Image.open(
            io.BytesIO(base64.b64decode(url[len(DATA_URL_PREFIX) :], validate=True))
        )
        stored.load()
    except (binascii.Error, ValueError, OSError, Image.DecompressionBombError):
        return "image_url does not decode to an image"
    if stored.format != "PNG":
        return "image_url does not decode to a PNG"
    if (
        config["image_width"],
        config["image_height"],
    ) != img.size or stored.size != img.size:
        return f"size differs from the render {img.size}"
    if q.get("answer_data") != answer_data:
        return "answer_data differs" if answer_data else "answer_data is not {}"
    if not pixels:
        return None
    diff = ImageChops.difference(stored.convert("RGB"), img.convert("RGB"))
    if diff.getbbox() is not None:
        reason = "pixels differ from the render"
        if PIL.__version__ != GENERATED_WITH_PILLOW:
            reason += (
                f" (generated with Pillow {GENERATED_WITH_PILLOW}, running {PIL.__version__}:"
                " re-run the generator and update GENERATED_WITH_PILLOW)"
            )
        return reason
    return None


def _rows(bundles: dict[str, dict]):
    for row in PLAN:
        q = bundles[row.file]["questions"][row.index - 1]
        img, target = render(row.key)
        config, answer_data = _expected(row, img, target)
        yield row, q, img, config, answer_data


def _label(row: PlanRow) -> str:
    return f"{row.file} Q{row.index} ({row.key})"


def check(pixels: bool = True) -> list[str]:
    """Every difference between the game files and fresh renders; raises PlanError.

    pixels=False skips the pixel comparison (structure, size and answer_data only).
    """
    out = []
    for row, q, img, _config, answer_data in _rows(verify_plan()):
        reason = _difference(row, q, img, answer_data, pixels)
        if reason:
            out.append(f"{_label(row)}: {reason}")
    return out


def write() -> list[tuple[PlanRow, bool]]:
    """Rewrite the rows --check would flag; returns (row, updated) per row. Raises PlanError."""
    bundles = verify_plan()
    results, dirty = [], set()
    for row, q, img, config, answer_data in _rows(bundles):
        updated = _difference(row, q, img, answer_data) is not None
        if updated:
            q["config"] = config
            q["answer_data"] = answer_data
            dirty.add(row.file)
        results.append((row, updated))
    for name in sorted(dirty):
        text = json.dumps(bundles[name], indent=2, ensure_ascii=False) + "\n"
        (GAMES_DIR / name).write_text(text, encoding="utf-8")
    return results


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0].strip())
    ap.add_argument(
        "--check", action="store_true", help="report differences, write nothing"
    )
    args = ap.parse_args(sys.argv[1:] if argv is None else argv)
    try:
        if args.check:
            diffs = check()
            for line in diffs:
                print(line)
            return 1 if diffs else 0
        for row, updated in write():
            print(f"{_label(row)}: {'updated' if updated else 'unchanged'}")
        return 0
    except PlanError as e:
        print(f"plan error: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
