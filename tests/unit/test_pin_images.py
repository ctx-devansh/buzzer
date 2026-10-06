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

pytest.importorskip("PIL")

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


def test_committed_games_are_in_sync():
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


def test_write_resets_completeness_answer_data(games):
    path = games / PARTY
    bundle = json.loads(path.read_text())
    bundle["questions"][8]["answer_data"] = {"x": 1}
    path.write_text(json.dumps(bundle, indent=2, ensure_ascii=False) + "\n")
    mpi.write()
    assert mpi.check() == []
    assert json.loads(path.read_text())["questions"][8]["answer_data"] == {}
