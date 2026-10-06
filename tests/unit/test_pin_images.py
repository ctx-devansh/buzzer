"""
scripts/make_pin_images.py: the committed sample games match fresh renders, targets match
the drawings, and a plan mismatch writes nothing (docs/design-t6-sample-games.md §5.4–5.5).
"""

from __future__ import annotations

import importlib.util
import json
import shutil
import sys
from pathlib import Path

import pytest

PIL = pytest.importorskip("PIL")
from PIL import ImageDraw  # noqa: E402

_SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "make_pin_images.py"
_spec = importlib.util.spec_from_file_location("make_pin_images", _SCRIPT)
mpi = importlib.util.module_from_spec(_spec)
sys.modules["make_pin_images"] = mpi  # @dataclass looks its module up here
_spec.loader.exec_module(mpi)

PARTY = "game_night_mixed_bag_party.json"


@pytest.fixture
def games(tmp_path, monkeypatch) -> Path:
    """Copies of the plan files in tmp_path, with GAMES_DIR pointed at them."""
    for name in {row.file for row in mpi.PLAN}:
        shutil.copy(mpi.ROOT / "sample_games" / name, tmp_path / name)
    monkeypatch.setattr(mpi, "GAMES_DIR", tmp_path)
    return tmp_path


def _snapshot(d: Path) -> dict[str, bytes]:
    return {p.name: p.read_bytes() for p in sorted(d.glob("*.json"))}


def _swap_party_q3_q4(d: Path) -> None:
    path = d / PARTY
    bundle = json.loads(path.read_text())
    qs = bundle["questions"]
    qs[2], qs[3] = qs[3], qs[2]
    path.write_text(json.dumps(bundle, indent=2, ensure_ascii=False) + "\n")


def _with_placeholder_url(d: Path) -> None:
    path = d / PARTY
    bundle = json.loads(path.read_text())
    bundle["questions"][2]["config"]["image_url"] = "<filled by the generator>"
    path.write_text(json.dumps(bundle, indent=2, ensure_ascii=False) + "\n")


def _edit_party_question(d: Path, index: int, **changes) -> None:
    path = d / PARTY
    bundle = json.loads(path.read_text())
    bundle["questions"][index - 1].update(changes)
    path.write_text(json.dumps(bundle, indent=2, ensure_ascii=False) + "\n")


def test_committed_games_match_structure_and_targets():
    assert mpi.check(pixels=False) == []


@pytest.mark.skipif(
    PIL.__version__ != mpi.GENERATED_WITH_PILLOW,
    reason=f"images were generated with Pillow {mpi.GENERATED_WITH_PILLOW}; "
    "re-run scripts/make_pin_images.py and update GENERATED_WITH_PILLOW",
)
def test_committed_games_match_pixels():
    assert mpi.check() == []


@pytest.mark.parametrize(
    "key, size, target",
    [
        ("commit_graph", (800, 400), (0.275, 0.65)),
        ("odd_face", (800, 600), (0.625, 0.5)),
        ("party_room", (800, 500), None),
    ],
)
def test_render_sizes_and_targets(key, size, target):
    img, got = mpi.render(key)
    assert img.size == size
    assert got == target


def test_write_leaves_in_sync_files_untouched(games):
    before = _snapshot(games)
    assert [updated for _row, updated in mpi.write()] == [False] * len(mpi.PLAN)
    assert _snapshot(games) == before


def test_plan_mismatch_raises_and_writes_nothing(games):
    _swap_party_q3_q4(games)
    before = _snapshot(games)
    with pytest.raises(mpi.PlanError):
        mpi.check()
    with pytest.raises(mpi.PlanError):
        mpi.write()
    assert _snapshot(games) == before


def test_cli_exits_2_on_plan_mismatch(games):
    _swap_party_q3_q4(games)
    before = _snapshot(games)
    assert mpi.main([]) == 2
    assert mpi.main(["--check"]) == 2
    assert _snapshot(games) == before


def test_non_json_plan_file_is_a_plan_error(games):
    (games / PARTY).write_text("not json")
    with pytest.raises(mpi.PlanError):
        mpi.check()


def test_missing_plan_file_is_a_plan_error(games):
    (games / PARTY).unlink()
    with pytest.raises(mpi.PlanError):
        mpi.check()


def test_check_reports_and_writes_nothing(games):
    _with_placeholder_url(games)
    before = _snapshot(games)
    assert mpi.main(["--check"]) == 1
    assert len(mpi.check()) == 1
    assert _snapshot(games) == before


@pytest.mark.parametrize(
    "index, changes",
    [
        (15, None),  # past the end of the party game's 14 questions
        (3, {"grading_type": "COMPLETENESS", "answer_data": {}}),
    ],
    ids=["index-out-of-range", "wrong-grading"],
)
def test_plan_mismatch_cases(games, monkeypatch, index, changes):
    if changes is None:
        row = mpi.PLAN[1]
        bad = mpi.PlanRow(
            row.file, index, row.prefix, row.key, row.grading, row.r_full, row.r_zero
        )
        monkeypatch.setattr(mpi, "PLAN", (mpi.PLAN[0], bad, mpi.PLAN[2]))
    else:
        _edit_party_question(games, index, **changes)
    with pytest.raises(mpi.PlanError):
        mpi.check()


def test_drawing_edit_that_keeps_the_target_is_caught(games, monkeypatch):
    """The odd face redrawn as a smile: same target, no odd face. Must not pass as in sync."""
    original = mpi._DRAWINGS["odd_face"]

    def all_smiles():
        img, target = original()
        d = ImageDraw.Draw(img)
        cx, cy = 500, 300
        d.ellipse(
            (cx - 70, cy - 70, cx + 70, cy + 70),
            fill="#facc15",
            outline=mpi.DARK,
            width=3,
        )
        for ex in (cx - 25, cx + 25):
            d.ellipse((ex - 8, cy - 28, ex + 8, cy - 12), fill=mpi.DARK)
        d.arc((cx - 35, cy - 15, cx + 35, cy + 35), 20, 160, fill=mpi.DARK, width=6)
        return img, target

    monkeypatch.setitem(mpi._DRAWINGS, "odd_face", all_smiles)
    diffs = mpi.check()
    assert [d.split(":")[0] for d in diffs] == [f"{PARTY} Q3 (odd_face)"]
    assert "pixels differ" in diffs[0]
    assert [updated for _row, updated in mpi.write()] == [False, True, False]
    assert mpi.check() == []


def test_write_resets_completeness_answer_data(games):
    path = games / PARTY
    bundle = json.loads(path.read_text())
    bundle["questions"][8]["answer_data"] = {"x": 1}
    path.write_text(json.dumps(bundle, indent=2, ensure_ascii=False) + "\n")
    mpi.write()
    assert mpi.check() == []
    assert json.loads(path.read_text())["questions"][8]["answer_data"] == {}
