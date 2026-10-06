"""
pin_the_spot integration tests that scenarios can't express
(docs/design-pin-the-spot.md §12 → Integration). Scoring across players lives in the
PIN_THE_SPOT scenario (scenarios/all_question_types.py).

  * Rejected socket submissions, live reveal, and both game-over summaries — driven with
    TestSocketClient directly (a rejected answer emits only `error`).
  * Authoring REST rules: create/update validation (422, symmetric), the played-image
    guard (409), type change on an unplayed question, access (403).
  * Export → import round trip, the HTML report board, and delete_game's Redis clean-up.

Runs against the Docker stack on :8000. Redis is read with `docker compose exec redis`
(the test is skipped if that is unavailable).
"""

from __future__ import annotations

import json
import math
import subprocess
import uuid
from collections.abc import Iterator

import pytest

from .conftest import create_guest_tokens, create_questions, create_room
from .engine.scoring import GameScenario, QuestionSpec
from .engine.socket_client import TestSocketClient as SocketClient
from .scenarios.all_question_types import (
    MC_ACCURACY,
    PIN_ACCURACY,
    PIN_COMPLETENESS,
    PIN_IMAGE,
)
from .test_host_admin_restructure import Api, Cleanup, T4Env, _jwt_sub, t4_env  # noqa: F401

_EVENT_TIMEOUT = 15.0
_TAP_ERROR = "pin_the_spot answer must be exactly {x, y} with numbers from 0 to 1"
_CONFLICT_MESSAGE = (
    "This question has recorded answers from a past session, so its image "
    "cannot be changed. Create a new question instead."
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _new_course_and_game(api: Api, admin: str, cleanup: Cleanup, label: str) -> tuple[int, int]:
    tag = uuid.uuid4().hex[:8]
    r = api.post("/admin/courses", admin, json={"name": f"PTS {label} {tag}", "semester": "Test"})
    assert r.status_code == 201, r.text
    course_id = r.json()["id"]
    r = api.post("/admin/games", admin, json={"title": f"PTS {label} {tag}", "description": ""})
    assert r.status_code == 201, r.text
    game_id = r.json()["id"]
    cleanup.games.append(game_id)
    return course_id, game_id


def _body(spec: QuestionSpec = PIN_ACCURACY, **overrides) -> dict:
    body = {
        "type": spec.type,
        "grading_type": spec.grading_type,
        "prompt": spec.prompt,
        "config": dict(spec.config),
        "answer_data": dict(spec.answer_data),
        "points_value": spec.points_value,
        "time_limit_seconds": spec.time_limit_seconds,
    }
    body.update(overrides)
    return body


def _get_question(api: Api, admin: str, game_id: int, question_id: int) -> dict:
    r = api.get(f"/host/games/{game_id}/questions", admin)
    assert r.status_code == 200, r.text
    matches = [q for q in r.json() if q["id"] == question_id]
    assert matches, f"question {question_id} not in game {game_id}"
    return matches[0]


def _session_id(api: Api, admin: str, room_code: str) -> str:
    r = api.get(f"/game/rooms/{room_code}", admin)
    assert r.status_code == 200, r.text
    return r.json()["session_id"]


def _redis_keys(pattern: str) -> list[str]:
    try:
        out = subprocess.run(
            ["docker", "compose", "exec", "-T", "redis", "redis-cli", "--scan", "--pattern", pattern],
            capture_output=True,
            text=True,
            timeout=20,
            check=True,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        pytest.skip(f"Redis not reachable through docker compose: {exc}")
    return [line for line in out.stdout.splitlines() if line.strip()]


async def _play(
    base_url: str,
    admin: str,
    cleanup: Cleanup,
    course_id: int,
    game_id: int,
    taps: list[dict],
    *,
    bad_taps: list[object] = (),
) -> dict:
    """
    One host + one guest through every question: emit each of `bad_taps` first (expecting
    `error`), then the real tap. Returns the captured payloads.
    """
    room_code = create_room(base_url, admin, course_id, game_id)
    (guest,) = create_guest_tokens(base_url, room_code, 1)
    cleanup.users.append(_jwt_sub(guest))
    host = SocketClient(base_url, admin, "host")
    player = SocketClient(base_url, guest, "player")
    captured: dict = {"room_code": room_code, "received": [], "results": [], "host_results": []}
    try:
        await host.connect()
        await player.connect()
        await host.emit("join_room", {"room_code": room_code, "role": "HOST"})
        await player.emit("join_room", {"room_code": room_code, "role": "PLAYER"})
        await host.wait_for("sync_state", _EVENT_TIMEOUT)
        await player.wait_for("sync_state", _EVENT_TIMEOUT)
        for i, tap in enumerate(taps):
            await host.emit("host_advance", {})
            question = await player.wait_for("new_question", _EVENT_TIMEOUT)
            await host.wait_for("new_question", _EVENT_TIMEOUT)
            if i == 0:
                captured["new_question"] = question
            qid = question["questionId"]
            for bad in bad_taps if i == 0 else ():
                await player.emit(
                    "submit_answer",
                    {"question_id": qid, "answer_data": bad, "answer_time_ms": 100},
                )
                err = await player.wait_for("error", _EVENT_TIMEOUT)
                assert err["message"] == _TAP_ERROR, (bad, err)
            await player.emit(
                "submit_answer", {"question_id": qid, "answer_data": tap, "answer_time_ms": 100}
            )
            captured["received"].append(await player.wait_for("answer_received", _EVENT_TIMEOUT))
            await host.emit("host_advance", {})
            captured["host_results"].append(await host.wait_for("question_results", _EVENT_TIMEOUT))
            captured["results"].append(await player.wait_for("question_results", _EVENT_TIMEOUT))
        await host.emit("host_advance", {})
        captured["player_game_over"] = await player.wait_for("game_over", _EVENT_TIMEOUT)
        captured["host_game_over"] = await host.wait_for("game_over", _EVENT_TIMEOUT)
    finally:
        await host.disconnect()
        await player.disconnect()
    return captured


@pytest.fixture(scope="module")
def api(base_url: str) -> Api:
    return Api(base_url)


@pytest.fixture()
def fn_cleanup(api: Api, admin_token: str) -> Iterator[Cleanup]:
    cleanup = Cleanup(api, admin_token)
    yield cleanup
    cleanup.run()


# ---------------------------------------------------------------------------
# Socket: rejected submissions, reveal, summaries
# ---------------------------------------------------------------------------


async def test_invalid_taps_rejected_then_valid_accepted(
    base_url: str, admin_token: str, api: Api
):
    cleanup = Cleanup(api, admin_token)
    try:
        course_id, game_id = _new_course_and_game(api, admin_token, cleanup, "reject")
        scenario = GameScenario(name="pts_reject", questions=[PIN_ACCURACY], player_scripts=[])
        create_questions(base_url, admin_token, game_id, scenario, False)

        bad_taps = [
            {"y": 0.5},  # missing x
            {"x": "0.5", "y": 0.5},  # string
            {"x": 1.5, "y": 0.5},  # out of range
            {"x": 0.5, "y": 0.5, "z": 0},  # extra key
            {"x": True, "y": 0.5},  # JSON true is an int in Python
        ]
        got = await _play(
            base_url, admin_token, cleanup, course_id, game_id, [{"x": 0.625, "y": 0.5}],
            bad_taps=bad_taps,
        )

        # The phone gets the prompt and the image (§3 player 1).
        assert got["new_question"]["prompt"] == PIN_ACCURACY.prompt
        assert got["new_question"]["config"]["image_url"] == PIN_IMAGE

        (received,) = got["received"]
        assert "alreadyAnswered" not in received, received  # nothing rejected was recorded
        assert received["pointsAwarded"] == 500
        assert received["isCorrect"] is False

        reveal = {"type": "pin_the_spot", "target": {"x": 0.5, "y": 0.5}, "rFull": 0.05, "rZero": 0.2}
        (host_results,) = got["host_results"]
        assert host_results["answerReveal"] == reveal
        assert host_results["answerDistribution"] == {"0.6250,0.5000": 1}
        (player_results,) = got["results"]
        assert player_results["answerReveal"] == reveal
        # yourPoints/yourIsCorrect are read from MySQL, and submit_answer emits
        # answer_received before its commit; advancing straight away can race it
        # (pre-existing, all types). yourScore comes from Redis. The scenario checks both.
        assert player_results["yourScore"] == 500

        (player_q,) = got["player_game_over"]["questionSummary"]
        assert "image_url" not in player_q["config"]
        assert player_q["config"] == {"image_width": 100, "image_height": 100}
        assert player_q["playerAnswer"] == {"x": 0.625, "y": 0.5}
        (host_q,) = got["host_game_over"]["questionSummary"]
        assert host_q["config"]["image_url"] == PIN_IMAGE
        assert host_q["answerDistribution"] == {"0.6250,0.5000": 1}
        assert host_q["answerReveal"] == reveal
    finally:
        cleanup.run()


async def test_nan_tap_is_rejected(base_url: str, admin_token: str, api: Api):
    """Python's json accepts NaN; socket.io's JS-free test client sends it as a float."""
    cleanup = Cleanup(api, admin_token)
    try:
        course_id, game_id = _new_course_and_game(api, admin_token, cleanup, "nan")
        scenario = GameScenario(name="pts_nan", questions=[PIN_COMPLETENESS], player_scripts=[])
        create_questions(base_url, admin_token, game_id, scenario, False)
        got = await _play(
            base_url, admin_token, cleanup, course_id, game_id, [{"x": 0.1, "y": 0.2}],
            bad_taps=[{"x": math.nan, "y": 0.5}],
        )
        assert got["received"][0]["pointsAwarded"] == 1000
    finally:
        cleanup.run()


# ---------------------------------------------------------------------------
# Shared played game
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def played_game(base_url: str, admin_token: str, api: Api) -> Iterator[dict]:
    """PIN_ACCURACY and an MC question played in one session; an unplayed PIN added after."""
    import asyncio

    cleanup = Cleanup(api, admin_token)
    try:
        course_id, game_id = _new_course_and_game(api, admin_token, cleanup, "played")
        scenario = GameScenario(name="pts_played", questions=[PIN_ACCURACY, MC_ACCURACY], player_scripts=[])
        pin_id, mc_id = create_questions(base_url, admin_token, game_id, scenario, False)
        got = asyncio.run(
            _play(
                base_url, admin_token, cleanup, course_id, game_id,
                [{"x": 0.5, "y": 0.5}, {"selectedIndex": 1}],
            )
        )
        unplayed = GameScenario(name="pts_unplayed", questions=[PIN_ACCURACY], player_scripts=[])
        (unplayed_pin_id,) = create_questions(base_url, admin_token, game_id, unplayed, False)
        yield {
            "course_id": course_id,
            "game_id": game_id,
            "pin_id": pin_id,
            "mc_id": mc_id,
            "unplayed_pin_id": unplayed_pin_id,
            "session_id": _session_id(api, admin_token, got["room_code"]),
        }
    finally:
        cleanup.run()


# ---------------------------------------------------------------------------
# Create / update validation (422), create/update symmetry
# ---------------------------------------------------------------------------

_SQUARE = PIN_ACCURACY.config
_KEY = PIN_ACCURACY.answer_data
INVALID = {
    "missing_image": {"config": {"image_width": 100, "image_height": 100}},
    "javascript_url": {"config": {**_SQUARE, "image_url": "javascript:alert(1)"}},
    "http_url": {"config": {**_SQUARE, "image_url": "http://example.com/a.png"}},
    "bad_base64": {"config": {**_SQUARE, "image_url": "data:image/png;base64,@@@"}},
    "zero_width": {"config": {**_SQUARE, "image_width": 0}},
    "accuracy_without_target": {"answer_data": {}},
    "target_out_of_range": {"answer_data": {**_KEY, "target": {"x": 1.2, "y": 0.5}}},
    "r_full_ge_r_zero": {"answer_data": {**_KEY, "r_full": 0.2, "r_zero": 0.2}},
    "negative_radius": {"answer_data": {**_KEY, "r_full": -0.1}},
    "r_zero_past_diagonal": {"answer_data": {**_KEY, "r_zero": 1.5}},
}


@pytest.mark.parametrize("name", list(INVALID))
def test_create_rejects_invalid(api: Api, admin_token: str, played_game: dict, name):
    r = api.post(
        f"/host/games/{played_game['game_id']}/questions",
        admin_token,
        json=_body(**INVALID[name]),
    )
    assert r.status_code == 422, r.text


@pytest.mark.parametrize("name", list(INVALID))
def test_update_rejects_the_same_payloads(api: Api, admin_token: str, played_game: dict, name):
    game_id, qid = played_game["game_id"], played_game["unplayed_pin_id"]
    before = _get_question(api, admin_token, game_id, qid)
    r = api.put(f"/host/games/{game_id}/questions/{qid}", admin_token, json=INVALID[name])
    assert r.status_code == 422, r.text
    assert _get_question(api, admin_token, game_id, qid) == before


# ---------------------------------------------------------------------------
# Played-image guard (409)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "body",
    [
        {"config": {**_SQUARE, "image_width": 101}},
        {"config": {**_SQUARE, "image_url": "https://example.com/other.png"}},
        {"type": "multiple_choice", "config": {"options": ["a", "b"]}, "answer_data": {"answer_points": [1, 0]}},
    ],
    ids=["size", "image", "type"],
)
def test_changing_played_image_or_type_is_409(api: Api, admin_token: str, played_game: dict, body):
    game_id, qid = played_game["game_id"], played_game["pin_id"]
    before = _get_question(api, admin_token, game_id, qid)
    r = api.put(f"/host/games/{game_id}/questions/{qid}", admin_token, json=body)
    assert r.status_code == 409, r.text
    assert r.json()["message"] == _CONFLICT_MESSAGE
    assert _get_question(api, admin_token, game_id, qid) == before


def test_played_question_allows_resend_prompt_target_radii_and_grading(
    api: Api, admin_token: str, played_game: dict
):
    game_id, qid = played_game["game_id"], played_game["pin_id"]
    url = f"/host/games/{game_id}/questions/{qid}"
    # Identical config resent with a prompt edit (what the editor does).
    r = api.put(url, admin_token, json={"prompt": "Tap the centre (edited).", "config": dict(_SQUARE)})
    assert r.status_code == 200, r.text
    # Target and radii.
    new_key = {"target": {"x": 0.4, "y": 0.6}, "r_full": 0.1, "r_zero": 0.3}
    r = api.put(url, admin_token, json={"answer_data": new_key})
    assert r.status_code == 200, r.text
    # Grading type (D7), then back.
    r = api.put(url, admin_token, json={"grading_type": "COMPLETENESS"})
    assert r.status_code == 200, r.text
    r = api.put(url, admin_token, json={"grading_type": "ACCURACY", "answer_data": dict(_KEY)})
    assert r.status_code == 200, r.text
    q = _get_question(api, admin_token, game_id, qid)
    assert q["prompt"] == "Tap the centre (edited)."
    assert q["config"] == _SQUARE


def test_played_mc_cannot_become_pin_the_spot(api: Api, admin_token: str, played_game: dict):
    game_id = played_game["game_id"]
    r = api.put(
        f"/host/games/{game_id}/questions/{played_game['mc_id']}",
        admin_token,
        json={"type": "pin_the_spot", "config": dict(_SQUARE), "answer_data": dict(_KEY)},
    )
    assert r.status_code == 409, r.text


def test_unplayed_pin_can_become_multiple_choice(
    api: Api, admin_token: str, played_game: dict
):
    game_id = played_game["game_id"]
    r = api.post(f"/host/games/{game_id}/questions", admin_token, json=_body())
    assert r.status_code == 201, r.text
    qid = r.json()["id"]
    try:
        r = api.put(
            f"/host/games/{game_id}/questions/{qid}",
            admin_token,
            json={
                "type": "multiple_choice",
                "config": {"options": ["a", "b"]},
                "answer_data": {"answer_points": [1, 0]},
            },
        )
        assert r.status_code == 200, r.text
        assert r.json()["type"] == "multiple_choice"
    finally:
        api.delete(f"/host/games/{game_id}/questions/{qid}", admin_token)


# ---------------------------------------------------------------------------
# Access
# ---------------------------------------------------------------------------


def test_other_courses_host_gets_403_and_admin_routes_work(
    api: Api, t4_env: T4Env  # noqa: F811
):
    game_a = t4_env.game_a["id"]
    r = api.post(f"/host/games/{game_a}/questions", t4_env.host_b.token, json=_body())
    assert r.status_code == 403, r.text

    r = api.post(f"/host/games/{game_a}/questions", t4_env.host_a.token, json=_body())
    assert r.status_code == 201, r.text
    qid = r.json()["id"]
    try:
        r = api.put(
            f"/host/games/{game_a}/questions/{qid}",
            t4_env.host_b.token,
            json={"prompt": "hijack"},
        )
        assert r.status_code == 403, r.text
        r = api.put(
            f"/admin/games/{game_a}/questions/{qid}",
            t4_env.admin,
            json={"answer_data": {**_KEY, "r_zero": 0.3}},
        )
        assert r.status_code == 200, r.text
    finally:
        api.delete(f"/host/games/{game_a}/questions/{qid}", t4_env.admin)


# ---------------------------------------------------------------------------
# Export / import, report
# ---------------------------------------------------------------------------


def test_export_import_round_trip(api: Api, admin_token: str, played_game: dict, fn_cleanup):
    game_id = played_game["game_id"]
    r = api.get(f"/host/games/{game_id}/export", admin_token)
    assert r.status_code == 200, r.text
    bundle = r.json()
    pins = [q for q in bundle["questions"] if q["type"] == "pin_the_spot"]
    assert pins and pins[0]["config"]["image_url"] == PIN_IMAGE

    r = api.post(
        "/host/games/import",
        admin_token,
        files={"file": ("g.json", json.dumps(bundle), "application/json")},
        data={"course_id": str(played_game["course_id"])},
    )
    assert r.status_code == 201, r.text
    new_game = r.json()["game_id"]
    fn_cleanup.games.append(new_game)
    r = api.get(f"/host/games/{new_game}/questions", admin_token)
    imported = [q for q in r.json() if q["type"] == "pin_the_spot"]
    assert [(q["config"], q["answer_data"]) for q in imported] == [
        (q["config"], q["answer_data"]) for q in pins
    ]


def test_import_with_missing_image_is_422(api: Api, admin_token: str, played_game: dict, fn_cleanup):
    bundle = {
        "format": "buzzer/game",
        "version": 1,
        "game": {"title": f"PTS import {uuid.uuid4().hex[:6]}", "description": "", "max_players": 10},
        "questions": [_body(), _body(config={"image_width": 100, "image_height": 100})],
    }
    r = api.post(
        "/host/games/import",
        admin_token,
        files={"file": ("g.json", json.dumps(bundle), "application/json")},
        data={"course_id": str(played_game["course_id"])},
    )
    if r.status_code == 201:
        fn_cleanup.games.append(r.json()["game_id"])
    assert r.status_code == 422, r.text
    assert "Question 2" in r.text


def test_report_contains_board(api: Api, admin_token: str, played_game: dict):
    r = api.get(f"/host/sessions/{played_game['session_id']}/report", admin_token)
    assert r.status_code == 200, r.text
    assert 'class="pin-board"' in r.text
    assert "Pin the Spot" in r.text
    assert PIN_IMAGE in r.text


# ---------------------------------------------------------------------------
# delete_game clean-up
# ---------------------------------------------------------------------------


async def test_delete_game_removes_redis_keys(base_url: str, admin_token: str, api: Api):
    cleanup = Cleanup(api, admin_token)
    try:
        course_id, game_id = _new_course_and_game(api, admin_token, cleanup, "delete")
        scenario = GameScenario(name="pts_delete", questions=[PIN_COMPLETENESS], player_scripts=[])
        create_questions(base_url, admin_token, game_id, scenario, False)
        got = await _play(base_url, admin_token, cleanup, course_id, game_id, [{"x": 0.2, "y": 0.3}])
        session_id = _session_id(api, admin_token, got["room_code"])
        assert _redis_keys(f"session:{session_id}:*"), "expected Redis keys before delete"

        r = api.delete(f"/admin/games/{game_id}", admin_token)
        assert r.status_code == 204, r.text
        assert api.get(f"/game/rooms/{got['room_code']}", admin_token).status_code == 404
        assert _redis_keys(f"session:{session_id}:*") == []
        assert _redis_keys(f"room:{got['room_code']}") == []
    finally:
        cleanup.run()
