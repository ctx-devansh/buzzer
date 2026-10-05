"""
Every committed sample game imports cleanly (T6; docs/design-t6-sample-games.md §5.4).

Each sample_games/*.json is imported through the host route (POST /host/games/import, the
Host app's Import JSON) into one throwaway course, and must come back with the same question
types in the same order. Each imported game is deleted afterwards; the course is left behind
as an inert record (there is no course DELETE endpoint), named "T6 sample games <tag>".

Runs against the Docker stack on :8000.
"""

from __future__ import annotations

import json
import uuid
from pathlib import Path

import pytest

from .test_host_admin_restructure import Api, Cleanup

_SAMPLE_GAMES = sorted(
    (Path(__file__).resolve().parents[2] / "sample_games").glob("*.json")
)


@pytest.fixture(scope="module")
def api(base_url: str) -> Api:
    return Api(base_url)


@pytest.fixture(scope="module")
def course_id(api: Api, admin_token: str) -> int:
    r = api.post(
        "/admin/courses",
        admin_token,
        json={"name": f"T6 sample games {uuid.uuid4().hex[:6]}", "semester": "Test"},
    )
    assert r.status_code == 201, r.text
    return r.json()["id"]


def test_sample_games_exist():
    assert _SAMPLE_GAMES, "sample_games/ has no *.json files"


@pytest.mark.parametrize("path", _SAMPLE_GAMES, ids=[p.name for p in _SAMPLE_GAMES])
def test_sample_game_imports_cleanly(
    api: Api, admin_token: str, course_id: int, path: Path
):
    bundle = json.loads(path.read_text(encoding="utf-8"))
    cleanup = Cleanup(api, admin_token)
    try:
        r = api.post(
            "/host/games/import",
            admin_token,
            files={"file": (path.name, path.read_bytes(), "application/json")},
            data={"course_id": str(course_id)},
        )
        assert r.status_code == 201, r.text
        game_id = r.json()["game_id"]
        cleanup.games.append(game_id)

        r = api.get(f"/host/games/{game_id}/questions", admin_token)
        assert r.status_code == 200, r.text
        assert [q["type"] for q in r.json()] == [q["type"] for q in bundle["questions"]]
    finally:
        cleanup.run()
