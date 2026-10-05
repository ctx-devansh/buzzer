"""
pin_the_spot integration tests that scenarios can't express
(docs/design-pin-the-spot.md → section 11). Scoring across players, the aspect ratio
and COMPLETENESS run as the `pin_the_spot_scoring` scenario in test_game_flow.py.

  * Rejected socket submissions (a rejected answer emits only `error`, so run_game
    would hang on answer_received) — driven with TestSocketClient directly.
  * Authoring REST rules: create/update/import validation (422), the played-question
    guard (409), and host access across courses (403).
  * Export → import round trip and the HTML session report.

Runs against the Docker stack on :8000.
"""

from __future__ import annotations

import asyncio
import json
import math
import uuid
from collections.abc import Iterator

import pytest

from .conftest import create_guest_tokens, create_questions, create_room
from .engine.orchestrator import run_game
from .engine.scoring import GameScenario, PlayerScript, QuestionSpec
from .engine.socket_client import TestSocketClient as SocketClient
from .scenarios.all_question_types import MC_ACCURACY, PIN_ACCURACY, PIN_CONFIG
from .test_host_admin_restructure import (
    Api,
    Cleanup,
    _admin_game,
    _grant_course,
    _grant_game,
    _jwt_sub,
    _make_user,
)

_EVENT_TIMEOUT = 15.0
_TAP_ERROR = "pin_the_spot answer must be {x, y} with numbers from 0 to 1"
_CONFLICT_MESSAGE = (
    "This question has recorded answers from a past session, so its image "
    "cannot be changed. Create a new question instead."
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _new_course_and_game(
    api: Api, admin: str, cleanup: Cleanup, label: str
) -> tuple[int, int]:
    """An admin-created course plus an unattached game (admin may run it, like game_setup)."""
    tag = uuid.uuid4().hex[:8]
    r = api.post(
        "/admin/courses", admin, json={"name": f"PTS {label} {tag}", "semester": "Test"}
    )
    assert r.status_code == 201, r.text
    course_id = r.json()["id"]
    r = api.post(
        "/admin/games", admin, json={"title": f"PTS {label} {tag}", "description": ""}
    )
    assert r.status_code == 201, r.text
    game_id = r.json()["id"]
    cleanup.games.append(game_id)
    return course_id, game_id


def _question_body(spec: QuestionSpec, **overrides) -> dict:
    body = {
        "type": spec.type,
        "grading_type": spec.grading_type,
        "prompt": spec.prompt,
        "config": spec.config,
        "answer_data": spec.answer_data,
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


def _bundle(questions: list[dict]) -> dict:
    return {
        "format": "buzzer/game",
        "version": 1,
        "game": {
            "title": f"PTS import {uuid.uuid4().hex[:6]}",
            "description": "",
            "max_players": 10,
        },
        "questions": questions,
    }


def _files(bundle: dict) -> dict:
    return {"file": ("g.json", json.dumps(bundle), "application/json")}


@pytest.fixture(scope="module")
def api(base_url: str) -> Api:
    return Api(base_url)


# ---------------------------------------------------------------------------
# Rejected submissions
# ---------------------------------------------------------------------------


async def test_invalid_taps_are_rejected_then_valid_accepted(
    base_url: str, admin_token: str, api: Api
):
    cleanup = Cleanup(api, admin_token)
    try:
        course_id, game_id = _new_course_and_game(api, admin_token, cleanup, "reject")
        scenario = GameScenario(
            name="pts_reject", questions=[PIN_ACCURACY], player_scripts=[]
        )
        create_questions(base_url, admin_token, game_id, scenario, False)
        room_code = create_room(base_url, admin_token, course_id, game_id)
        (guest_token,) = create_guest_tokens(base_url, room_code, 1)
        cleanup.users.append(_jwt_sub(guest_token))

        host = SocketClient(base_url, admin_token, "host")
        player = SocketClient(base_url, guest_token, "player")
        try:
            await host.connect()
            await player.connect()
            await host.emit("join_room", {"room_code": room_code, "role": "HOST"})
            await player.emit("join_room", {"room_code": room_code, "role": "PLAYER"})
            await host.wait_for("sync_state", _EVENT_TIMEOUT)
            await player.wait_for("sync_state", _EVENT_TIMEOUT)

            await host.emit("host_advance", {})
            question = await player.wait_for("new_question", _EVENT_TIMEOUT)
            await host.wait_for("new_question", _EVENT_TIMEOUT)
            question_id = question["questionId"]
            # The player gets the image config, never the target.
            assert question["config"] == PIN_CONFIG
            assert "answer_data" not in question and "target" not in json.dumps(
                question
            )

            bad_payloads = [
                {"x": 0.5},  # missing y
                {"x": "0.5", "y": 0.5},  # string
                {"x": True, "y": 0.5},  # bool posing as a number
                {"x": -0.1, "y": 0.5},  # below 0
                {"x": 0.5, "y": 1.2},  # above 1
                {"x": 0.5, "y": 0.5, "z": 0},  # extra key
                {"x": None, "y": 0.5},
            ]
            for bad in bad_payloads:
                await player.emit(
                    "submit_answer",
                    {
                        "question_id": question_id,
                        "answer_data": bad,
                        "answer_time_ms": 100,
                    },
                )
                err = await player.wait_for("error", _EVENT_TIMEOUT)
                assert err["message"] == _TAP_ERROR, (bad, err)

            # d = 0.125 on the 2:1 image (0.25 of the height × aspect 0.5) → half credit.
            await player.emit(
                "submit_answer",
                {
                    "question_id": question_id,
                    "answer_data": {"x": 0.5, "y": 0.75},
                    "answer_time_ms": 100,
                },
            )
            received = await player.wait_for("answer_received", _EVENT_TIMEOUT)
            # Not alreadyAnswered → none of the rejected payloads was recorded.
            assert "alreadyAnswered" not in received, received
            assert received["pointsAwarded"] == pytest.approx(500)
            assert received["isCorrect"] is False

            await host.emit("host_advance", {})  # → results
            results = await host.wait_for("question_results", _EVENT_TIMEOUT)
            assert results["answerDistribution"] == {"0.5000,0.7500": 1}
            assert results["answerReveal"] == {
                "type": "pin_the_spot",
                "target": {"x": 0.5, "y": 0.5},
                "rFull": 0.05,
                "rZero": 0.2,
            }
            await player.wait_for("question_results", _EVENT_TIMEOUT)
            await host.emit("host_advance", {})  # → game over
            game_over = await player.wait_for("game_over", _EVENT_TIMEOUT)
            host_over = await host.wait_for("game_over", _EVENT_TIMEOUT)
            (summary,) = game_over["questionSummary"]
            assert summary["playerAnswer"] == {"x": 0.5, "y": 0.75}
            (host_summary,) = host_over["questionSummary"]
            assert host_summary["answerDistribution"] == {"0.5000,0.7500": 1}
        finally:
            await host.disconnect()
            await player.disconnect()
    finally:
        cleanup.run()


# ---------------------------------------------------------------------------
# Shared played game
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def played_game(base_url: str, admin_token: str, api: Api) -> Iterator[dict]:
    """PIN_ACCURACY played once in a COMPLETED session (one tap at the target)."""
    cleanup = Cleanup(api, admin_token)
    try:
        course_id, game_id = _new_course_and_game(api, admin_token, cleanup, "played")
        scenario = GameScenario(
            name="pts_played",
            questions=[PIN_ACCURACY],
            player_scripts=[PlayerScript(responses=[{"x": 0.5, "y": 0.5}])],
        )
        (pin_id,) = create_questions(base_url, admin_token, game_id, scenario, False)
        room_code = create_room(base_url, admin_token, course_id, game_id)
        tokens = create_guest_tokens(base_url, room_code, 1)
        cleanup.users.append(_jwt_sub(tokens[0]))
        asyncio.run(
            run_game(
                base_url=base_url,
                host_token=admin_token,
                player_tokens=tokens,
                room_code=room_code,
                scenario=scenario,
            )
        )
        r = api.get(f"/game/rooms/{room_code}", admin_token)
        assert r.status_code == 200, r.text
        yield {
            "course_id": course_id,
            "game_id": game_id,
            "pin_id": pin_id,
            "session_id": r.json()["session_id"],
        }
    finally:
        cleanup.run()


# ---------------------------------------------------------------------------
# Create validation (422)
# ---------------------------------------------------------------------------

_DIAGONAL_2_TO_1 = math.hypot(1, 0.5)  # ≈ 1.118


@pytest.mark.parametrize(
    "overrides",
    [
        {"config": {"image_width": 1000, "image_height": 500}},
        {"config": {**PIN_CONFIG, "image_url": "javascript:alert(1)"}},
        {"config": {**PIN_CONFIG, "image_width": 0}},
        {"answer_data": {}},
        {
            "answer_data": {
                "target": {"x": 1.5, "y": 0.5},
                "r_full": 0.05,
                "r_zero": 0.2,
            }
        },
        {"answer_data": {"target": {"x": 0.5, "y": 0.5}, "r_full": 0.2, "r_zero": 0.2}},
        {
            "answer_data": {
                "target": {"x": 0.5, "y": 0.5},
                "r_full": -0.05,
                "r_zero": 0.2,
            }
        },
        {
            "answer_data": {
                "target": {"x": 0.5, "y": 0.5},
                "r_full": 0.05,
                "r_zero": _DIAGONAL_2_TO_1 + 0.01,
            }
        },
    ],
    ids=[
        "missing_image",
        "javascript_url",
        "zero_width",
        "accuracy_without_target",
        "target_outside_image",
        "r_full_equals_r_zero",
        "negative_radius",
        "r_zero_beyond_diagonal",
    ],
)
def test_create_rejects_invalid(
    api: Api, admin_token: str, played_game: dict, overrides
):
    r = api.post(
        f"/host/games/{played_game['game_id']}/questions",
        admin_token,
        json=_question_body(PIN_ACCURACY, **overrides),
    )
    assert r.status_code == 422, r.text


def test_create_accepts_completeness_without_target(
    api: Api, admin_token: str, played_game: dict
):
    game_id = played_game["game_id"]
    r = api.post(
        f"/host/games/{game_id}/questions",
        admin_token,
        json=_question_body(PIN_ACCURACY, grading_type="COMPLETENESS", answer_data={}),
    )
    assert r.status_code == 201, r.text
    api.delete(f"/host/games/{game_id}/questions/{r.json()['id']}", admin_token)


# ---------------------------------------------------------------------------
# Update validation (422) — the create/update asymmetry T7 warns about
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "update,message",
    [
        (
            {
                "answer_data": {
                    "target": {"x": 0.5, "y": 0.5},
                    "r_full": 0.3,
                    "r_zero": 0.2,
                }
            },
            "0 < full-credit radius < zero-credit radius",
        ),
        (
            {
                "answer_data": {
                    "target": {"x": 0.5, "y": 2},
                    "r_full": 0.05,
                    "r_zero": 0.2,
                }
            },
            "Target must be {x, y}",
        ),
        # Control: a valid config-only update is accepted (None = expect 200).
        ({"config": {**PIN_CONFIG, "image_width": 1000, "image_height": 10}}, None),
        ({"config": {"image_url": PIN_CONFIG["image_url"]}}, "exactly"),
        ({"grading_type": "ACCURACY", "answer_data": {}}, "needs a target"),
    ],
    ids=[
        "radii_swapped",
        "target_outside",
        "config_ok",
        "config_missing_size",
        "accuracy_target_removed",
    ],
)
def test_update_making_question_invalid_is_422(
    api: Api, admin_token: str, played_game: dict, update: dict, message: str | None
):
    game_id = played_game["game_id"]
    r = api.post(
        f"/host/games/{game_id}/questions",
        admin_token,
        json=_question_body(PIN_ACCURACY),
    )
    assert r.status_code == 201, r.text
    qid = r.json()["id"]
    try:
        before = _get_question(api, admin_token, game_id, qid)
        r = api.put(f"/host/games/{game_id}/questions/{qid}", admin_token, json=update)
        if message is None:
            assert r.status_code == 200, r.text  # a valid partial update still works
            return
        assert r.status_code == 422, r.text
        assert r.json()["error"] == "VALIDATION_ERROR"
        assert message in r.json()["message"]
        assert _get_question(api, admin_token, game_id, qid) == before
    finally:
        api.delete(f"/host/games/{game_id}/questions/{qid}", admin_token)


def test_update_config_alone_is_checked_against_stored_radii(
    api: Api, admin_token: str, played_game: dict
):
    """A config-only PUT is validated together with the stored answer_data."""
    game_id = played_game["game_id"]
    answer = {
        "target": {"x": 0.5, "y": 0.5},
        "r_full": 0.05,
        "r_zero": 1.1,
    }  # < 2:1 diagonal
    r = api.post(
        f"/host/games/{game_id}/questions",
        admin_token,
        json=_question_body(PIN_ACCURACY, answer_data=answer),
    )
    assert r.status_code == 201, r.text
    qid = r.json()["id"]
    try:
        # 100:1 image → diagonal ≈ 1.00005, below the stored r_zero 1.1.
        r = api.put(
            f"/host/games/{game_id}/questions/{qid}",
            admin_token,
            json={"config": {**PIN_CONFIG, "image_width": 1000, "image_height": 10}},
        )
        assert r.status_code == 422, r.text
        assert "diagonal" in r.json()["message"]
    finally:
        api.delete(f"/host/games/{game_id}/questions/{qid}", admin_token)


def test_update_type_to_pin_without_config_is_422(
    api: Api, admin_token: str, played_game: dict
):
    game_id = played_game["game_id"]
    r = api.post(
        f"/host/games/{game_id}/questions",
        admin_token,
        json=_question_body(MC_ACCURACY),
    )
    assert r.status_code == 201, r.text
    qid = r.json()["id"]
    try:
        r = api.put(
            f"/host/games/{game_id}/questions/{qid}",
            admin_token,
            json={"type": "pin_the_spot"},
        )
        assert r.status_code == 422, r.text
        assert (
            _get_question(api, admin_token, game_id, qid)["type"] == "multiple_choice"
        )
    finally:
        api.delete(f"/host/games/{game_id}/questions/{qid}", admin_token)


# ---------------------------------------------------------------------------
# Played-question guard (409)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "update",
    [
        {"config": {**PIN_CONFIG, "image_url": "https://example.com/other.png"}},
        {"config": {**PIN_CONFIG, "image_height": 600}},
        {"type": "multiple_choice"},
    ],
    ids=["new_image", "new_size", "type_change"],
)
def test_played_question_image_and_type_are_frozen(
    api: Api, admin_token: str, played_game: dict, update: dict
):
    game_id, qid = played_game["game_id"], played_game["pin_id"]
    before = _get_question(api, admin_token, game_id, qid)
    r = api.put(f"/host/games/{game_id}/questions/{qid}", admin_token, json=update)
    assert r.status_code == 409, r.text
    assert r.json()["message"] == _CONFLICT_MESSAGE
    assert _get_question(api, admin_token, game_id, qid) == before


def test_played_question_target_and_prompt_can_change(
    api: Api, admin_token: str, played_game: dict
):
    game_id, qid = played_game["game_id"], played_game["pin_id"]
    before = _get_question(api, admin_token, game_id, qid)
    new_answer = {"target": {"x": 0.25, "y": 0.25}, "r_full": 0.1, "r_zero": 0.3}
    try:
        r = api.put(
            f"/host/games/{game_id}/questions/{qid}",
            admin_token,
            json={"answer_data": new_answer, "prompt": "Moved", "config": PIN_CONFIG},
        )
        assert r.status_code == 200, r.text  # resending the same config is not a change
        assert r.json()["answer_data"] == new_answer
    finally:
        api.put(
            f"/host/games/{game_id}/questions/{qid}",
            admin_token,
            json={"answer_data": before["answer_data"], "prompt": before["prompt"]},
        )


# ---------------------------------------------------------------------------
# Access across courses (403)
# ---------------------------------------------------------------------------


def test_host_of_other_course_cannot_create_or_edit(api: Api, admin_token: str):
    cleanup = Cleanup(api, admin_token)
    try:
        tag = uuid.uuid4().hex[:6]
        courses = []
        for label in ("A", "B"):
            r = api.post(
                "/admin/courses",
                admin_token,
                json={"name": f"PTS {label} {tag}", "semester": "Test"},
            )
            assert r.status_code == 201, r.text
            courses.append(r.json()["id"])
        host_a = _make_user(api, admin_token, cleanup, "pts_host_a")
        host_b = _make_user(api, admin_token, cleanup, "pts_host_b")
        _grant_course(api, admin_token, host_a, courses[0], "HOST")
        _grant_course(api, admin_token, host_b, courses[1], "HOST")
        game_b = _admin_game(api, admin_token, cleanup, f"PTS B {tag}", courses[1])
        _grant_game(api, admin_token, host_b, game_b["id"])
        gid = game_b["id"]

        body = _question_body(PIN_ACCURACY)
        r = api.post(f"/host/games/{gid}/questions", host_b.token, json=body)
        assert r.status_code == 201, r.text
        qid = r.json()["id"]

        assert (
            api.post(
                f"/host/games/{gid}/questions", host_a.token, json=body
            ).status_code
            == 403
        )
        r = api.put(
            f"/host/games/{gid}/questions/{qid}",
            host_a.token,
            json={
                "answer_data": {
                    "target": {"x": 0, "y": 0},
                    "r_full": 0.1,
                    "r_zero": 0.2,
                }
            },
        )
        assert r.status_code == 403
        assert (
            _get_question(api, admin_token, gid, qid)["answer_data"]
            == PIN_ACCURACY.answer_data
        )
    finally:
        cleanup.run()


# ---------------------------------------------------------------------------
# Export / import
# ---------------------------------------------------------------------------


def test_export_import_round_trip(api: Api, admin_token: str, played_game: dict):
    r = api.get(f"/host/games/{played_game['game_id']}/export", admin_token)
    assert r.status_code == 200, r.text
    bundle = r.json()
    assert bundle["version"] == 1
    exported = [q for q in bundle["questions"] if q["type"] == "pin_the_spot"]
    assert exported and exported[0]["config"] == PIN_CONFIG

    r = api.post(
        "/host/games/import",
        admin_token,
        files=_files(bundle),
        data={"course_id": str(played_game["course_id"])},
    )
    assert r.status_code == 201, r.text
    new_id = r.json()["game_id"]
    try:
        r = api.get(f"/host/games/{new_id}/questions", admin_token)
        assert r.status_code == 200, r.text
        imported = [q for q in r.json() if q["type"] == "pin_the_spot"]
        assert len(imported) == len(exported)
        for got, sent in zip(imported, exported):
            assert got["config"] == sent["config"]
            assert got["answer_data"] == sent["answer_data"]
            assert got["grading_type"] == sent["grading_type"]
            assert got["points_value"] == pytest.approx(sent["points_value"])
    finally:
        assert api.delete(f"/admin/games/{new_id}", admin_token).status_code == 204


@pytest.mark.parametrize(
    "config",
    [
        {"image_width": 10, "image_height": 10},
        {**PIN_CONFIG, "image_url": "ftp://x/y.png"},
    ],
    ids=["missing_image", "bad_scheme"],
)
def test_import_question_without_valid_image_fails_by_number(
    api: Api, admin_token: str, config
):
    ok = _question_body(MC_ACCURACY)
    bad = _question_body(PIN_ACCURACY, config=config)
    r = api.post("/admin/games/import", admin_token, files=_files(_bundle([ok, bad])))
    assert r.status_code == 422, r.text
    assert "Question 2 invalid" in r.text


def test_session_report_draws_taps(api: Api, admin_token: str, played_game: dict):
    r = api.get(f"/host/sessions/{played_game['session_id']}/report", admin_token)
    assert r.status_code == 200, r.text
    html = r.text
    assert "Pin the Spot" in html
    assert 'class="pin-board"' in html
    assert html.count('class="pin-tap"') == 1
    assert 'class="pin-full"' in html and 'class="pin-zero"' in html
