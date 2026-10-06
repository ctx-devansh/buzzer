"""
Every sample_games/*.json imports through the host route and survives the round trip.

Covers the T6 games and the 12 starter files (docs/design-t6-sample-games.md §5.5). Each file
is imported into one shared course, read back via export, compared field by field and then
deleted. If a file you didn't write fails here, report it to its owner; don't edit it.
"""

from __future__ import annotations

import json
import uuid
from pathlib import Path

import pytest

from .test_host_admin_restructure import Api, Cleanup

SAMPLE_GAMES = sorted((Path(__file__).resolve().parents[2] / "sample_games").glob("*.json"))

GAME_KEYS = ("title", "description", "max_players")
QUESTION_KEYS = (
    "type",
    "grading_type",
    "prompt",
    "config",
    "answer_data",
    "time_limit_seconds",
    "points_value",
)


@pytest.fixture(scope="module")
def api(base_url: str) -> Api:
    return Api(base_url)


@pytest.fixture(scope="module")
def course_id(api: Api, admin_token: str) -> int:
    # Left behind afterwards: there is no course DELETE route.
    r = api.post(
        "/admin/courses",
        admin_token,
        json={"name": f"T6 sample games {uuid.uuid4().hex[:6]}", "semester": "Test"},
    )
    assert r.status_code == 201, r.text
    return r.json()["id"]


def test_sample_games_found():
    assert SAMPLE_GAMES, "no sample_games/*.json files found"


@pytest.mark.parametrize("path", SAMPLE_GAMES, ids=[p.name for p in SAMPLE_GAMES])
def test_sample_game_imports_and_round_trips(
    path: Path, api: Api, admin_token: str, course_id: int
):
    raw = path.read_bytes()
    bundle = json.loads(raw)
    cleanup = Cleanup(api, admin_token)
    try:
        r = api.post(
            "/host/games/import",
            admin_token,
            files={"file": (path.name, raw, "application/json")},
            data={"course_id": str(course_id)},
        )
        assert r.status_code == 201, f"{path.name}: {r.status_code} {r.text[:500]}"
        game_id = r.json()["game_id"]
        cleanup.games.append(game_id)

        r = api.get(f"/host/games/{game_id}/questions", admin_token)
        assert r.status_code == 200, r.text
        assert [q["type"] for q in r.json()] == [q["type"] for q in bundle["questions"]]

        r = api.get(f"/host/games/{game_id}/export", admin_token)
        assert r.status_code == 200, r.text
        exported = r.json()
        for key in GAME_KEYS:
            assert exported["game"][key] == bundle["game"][key], f"game.{key}"
        assert len(exported["questions"]) == len(bundle["questions"])
        for n, (got, want) in enumerate(zip(exported["questions"], bundle["questions"]), 1):
            for key in QUESTION_KEYS:
                assert got[key] == want[key], f"{path.name} Q{n} {key}"
    finally:
        cleanup.run()
