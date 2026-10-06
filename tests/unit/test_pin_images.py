"""
Unit tests for scripts/make_pin_images.py (docs/design-t6-sample-games.md §5.4, §5.8).

The committed Pin the Spot images and targets in sample_games/ must match a fresh render, and
each target must sit where the drawing puts it. On copies in tmp_path: a re-run on clean files
writes nothing, and a plan mismatch (reordered question, missing or invalid file) writes
nothing and exits 2. Skipped without Pillow (not a declared
dependency; see the script's docstring).

Run with (from the repo root):
    pytest -c pytest.ini tests/unit/test_pin_images.py -v
"""

from __future__ import annotations

import importlib.util
import json
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


# --- write() and the plan guard, on copies (design §5.8) ---------------------


@pytest.fixture
def games_copy(pin_images, tmp_path, monkeypatch) -> dict[str, bytes]:
    """The PLAN files copied into tmp_path, which the script then reads and writes."""
    originals = {}
    for file in {row.file for row in pin_images.PLAN}:
        data = (pin_images.GAMES_DIR / file).read_bytes()
        (tmp_path / file).write_bytes(data)
        originals[file] = data
    monkeypatch.setattr(pin_images, "GAMES_DIR", tmp_path)
    return originals


def _bytes_now(tmp_path: Path, originals: dict[str, bytes]) -> dict[str, bytes]:
    return {file: (tmp_path / file).read_bytes() for file in originals}


def test_write_on_clean_files_changes_nothing(pin_images, games_copy, tmp_path):
    results = pin_images.write()
    assert [updated for _, updated in results] == [False] * len(pin_images.PLAN)
    assert _bytes_now(tmp_path, games_copy) == games_copy


def test_reordered_question_is_refused_and_nothing_written(
    pin_images, games_copy, tmp_path
):
    party = tmp_path / pin_images.PARTY
    bundle = json.loads(party.read_text(encoding="utf-8"))
    qs = bundle["questions"]
    qs[2], qs[3] = qs[3], qs[2]  # Q3 (rainbow pin) and Q4 swap places
    party.write_text(json.dumps(bundle, indent=2, ensure_ascii=False) + "\n")
    before = _bytes_now(tmp_path, games_copy)

    with pytest.raises(pin_images.PlanError, match=r"Q3 \(rainbow\)"):
        pin_images.check()
    with pytest.raises(pin_images.PlanError):
        pin_images.write()
    assert _bytes_now(tmp_path, games_copy) == before


def test_missing_or_invalid_file_is_a_plan_error(pin_images, games_copy, tmp_path):
    classroom = tmp_path / pin_images.CLASSROOM
    classroom.write_text("{not json", encoding="utf-8")
    with pytest.raises(pin_images.PlanError, match="not valid JSON"):
        pin_images.check()
    classroom.unlink()
    with pytest.raises(pin_images.PlanError, match="not found"):
        pin_images.check()


def test_cli_exits_2_on_plan_mismatch(pin_images, games_copy, tmp_path, monkeypatch):
    (tmp_path / pin_images.CLASSROOM).unlink()
    for argv in (["make_pin_images.py"], ["make_pin_images.py", "--check"]):
        monkeypatch.setattr(sys, "argv", argv)
        assert pin_images.main() == 2
    assert (tmp_path / pin_images.PARTY).read_bytes() == games_copy[pin_images.PARTY]
