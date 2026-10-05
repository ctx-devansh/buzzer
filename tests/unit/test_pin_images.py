"""
Unit tests for scripts/make_pin_images.py (docs/design-t6-sample-games.md §5.4).

The committed Pin the Spot images and targets in sample_games/ must match a fresh render, and
each target must sit where the drawing puts it. Skipped without Pillow (not a declared
dependency; see the script's docstring).

Run with (from the repo root):
    pytest -c pytest.ini tests/unit/test_pin_images.py -v
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

pytest.importorskip("PIL")

_SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "make_pin_images.py"


@pytest.fixture(scope="module")
def pin_images():
    spec = importlib.util.spec_from_file_location("make_pin_images", _SCRIPT)
    module = importlib.util.module_from_spec(spec)
    # Registered before exec: @dataclass resolves its module through sys.modules.
    sys.modules[spec.name] = module
    try:
        spec.loader.exec_module(module)
        yield module
    finally:
        sys.modules.pop(spec.name, None)


def test_sample_games_match_a_fresh_render(pin_images):
    assert pin_images.check() == []


@pytest.mark.parametrize(
    ("key", "size", "target"),
    [
        ("rainbow", (720, 180), (0.2, 0.5)),
        ("clock", (480, 480), (0.875, 0.5)),
        ("number_line", (800, 160), (0.707, 0.5)),
        ("topology", (800, 450), (0.5, 0.5)),
    ],
)
def test_render_size_and_target(pin_images, key, size, target):
    img, rendered_target = pin_images.render(key)
    assert img.size == size
    # Exact: render() rounds to 4 dp once, and answer_data stores that same value.
    assert rendered_target == target
