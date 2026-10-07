"""
Every sample_games/*.json imports through the host route and survives the round trip.

Covers the T6 games and the 12 starter files (docs/design-t6-sample-games.md §5.5). Each file
is imported into one shared course, read back via export, compared field by field and then
deleted. If a file you didn't write fails here, report it to its owner; don't edit it.

A version 2 file with images is compared by image content, not id: import gives each image
the course's id, so ids never match a fresh course's (docs/plans/cell-biology-pin-the-spot.md).
"""

from __future__ import annotations

import base64
import hashlib
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


def _image_digests(bundle: dict) -> dict[str, str]:
    """Image id → sha256 of its decoded bytes (the file's own sha256 field isn't trusted)."""
    return {
        img["id"]: hashlib.sha256(base64.b64decode(img["data_base64"])).hexdigest()
        for img in bundle.get("images", [])
    }


def _by_content(q: dict, digests: dict[str, str]) -> dict:
    """The compared fields of a version 2 question, every image id replaced by its digest."""

    def resolve(image_id: str | None) -> str | None:
        if image_id is None:
            return None
        assert image_id in digests, f"image id {image_id!r} is not in the bundle's images"
        return digests[image_id]

    out = {key: q[key] for key in QUESTION_KEYS}
    config = dict(out["config"])
    if "image_id" in config:
        config["image_id"] = resolve(config["image_id"])
    if "option_image_ids" in config:
        config["option_image_ids"] = [resolve(i) for i in config["option_image_ids"]]
    out["config"] = config
    assert "prompt_image_id" in q, "version 2 question without prompt_image_id"
    out["prompt_image_id"] = resolve(q["prompt_image_id"])
    return out


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
        assert exported["version"] == bundle["version"], f"{path.name} version"
        assert len(exported["questions"]) == len(bundle["questions"])
        pairs = enumerate(zip(exported["questions"], bundle["questions"]), 1)
        if bundle.get("images"):
            # Never fall back to the id comparison below: a file with images must export them.
            assert exported.get("images"), f"{path.name}: file has images, export has none"
            got_digests, want_digests = _image_digests(exported), _image_digests(bundle)
            for n, (got, want) in pairs:
                got_c, want_c = _by_content(got, got_digests), _by_content(want, want_digests)
                for key in got_c:
                    assert got_c[key] == want_c[key], f"{path.name} Q{n} {key}"
        else:
            for n, (got, want) in pairs:
                for key in QUESTION_KEYS:
                    assert got[key] == want[key], f"{path.name} Q{n} {key}"
    finally:
        cleanup.run()
