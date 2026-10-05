"""
put_in_order integration tests that scenarios can't express
(docs/design-put-in-order.md → Tests → Integration).

  * Rejected socket submissions (a rejected answer emits only `error`, so run_game
    would hang on answer_received) — driven with TestSocketClient directly.
  * Authoring REST rules: create/update/import validation (422) and the
    played-question guard (409), on a module-scoped game with one played session.

Runs against the Docker stack on :8000. The tests have no database access, so "nothing
was recorded" is shown through behaviour (a later valid answer is not alreadyAnswered).
"""

from __future__ import annotations

import asyncio
import json
import uuid
from collections.abc import Iterator

import pytest

from .conftest import create_guest_tokens, create_questions, create_room
from .engine.orchestrator import run_game
from .engine.scoring import GameScenario, PlayerScript, QuestionSpec
from .engine.socket_client import TestSocketClient as SocketClient
from .scenarios.all_question_types import MC_ACCURACY, PIO_ACCURACY, PIO_COMPLETENESS
from .test_host_admin_restructure import Api, Cleanup, _jwt_sub

_EVENT_TIMEOUT = 15.0
_PIO_ERROR = (
    "put_in_order answer must include orderedIndices as a permutation of the item indices"
)
_CONFLICT_MESSAGE = (
    "This question has recorded answers from a past session, so its items "
    "cannot be changed. Create a new question instead."
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _new_course_and_game(api: Api, admin: str, cleanup: Cleanup, label: str) -> tuple[int, int]:
    """An admin-created course plus an unattached game (admin may run it, like game_setup)."""
    tag = uuid.uuid4().hex[:8]
    r = api.post("/admin/courses", admin, json={"name": f"PIO {label} {tag}", "semester": "Test"})
    assert r.status_code == 201, r.text
    course_id = r.json()["id"]
    r = api.post("/admin/games", admin, json={"title": f"PIO {label} {tag}", "description": ""})
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


def _play_session(
    base_url: str,
    admin: str,
    cleanup: Cleanup,
    course_id: int,
    game_id: int,
    questions: list[QuestionSpec],
    responses: list[dict | None],
) -> None:
    """One COMPLETED session with one guest answering `responses`."""
    room_code = create_room(base_url, admin, course_id, game_id)
    tokens = create_guest_tokens(base_url, room_code, 1)
    cleanup.users.append(_jwt_sub(tokens[0]))
    scenario = GameScenario(
        name="pio_fixture_session",
        questions=questions,
        player_scripts=[PlayerScript(responses=responses)],
    )
    asyncio.run(
        run_game(
            base_url=base_url,
            host_token=admin,
            player_tokens=tokens,
            room_code=room_code,
            scenario=scenario,
        )
    )


def _bundle(questions: list[dict]) -> dict:
    return {
        "format": "buzzer/game",
        "version": 1,
        "game": {"title": f"PIO import {uuid.uuid4().hex[:6]}", "description": "", "max_players": 10},
        "questions": questions,
    }


def _files(bundle: dict) -> dict:
    return {"file": ("g.json", json.dumps(bundle), "application/json")}


@pytest.fixture(scope="module")
def api(base_url: str) -> Api:
    return Api(base_url)


@pytest.fixture()
def fn_cleanup(api: Api, admin_token: str) -> Iterator[Cleanup]:
    cleanup = Cleanup(api, admin_token)
    yield cleanup
    cleanup.run()


# ---------------------------------------------------------------------------
# Rejected submissions
# ---------------------------------------------------------------------------


async def test_invalid_orders_are_rejected_then_valid_accepted(
    base_url: str, admin_token: str, api: Api
):
    cleanup = Cleanup(api, admin_token)
    try:
        course_id, game_id = _new_course_and_game(api, admin_token, cleanup, "reject")
        scenario = GameScenario(
            name="pio_reject", questions=[PIO_ACCURACY], player_scripts=[]
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

            bad_payloads = [
                [0, 0, 1, 2],  # duplicate
                [0, 1, 2],  # missing an index
                [0, 1, 2, 9],  # out of range
                "0123",  # not a list
                [True, 0, 2, 3],  # JSON true: sorts to [0,1,2,3], only type(x) is int rejects it
            ]
            for bad in bad_payloads:
                await player.emit(
                    "submit_answer",
                    {
                        "question_id": question_id,
                        "answer_data": {"orderedIndices": bad},
                        "answer_time_ms": 100,
                    },
                )
                err = await player.wait_for("error", _EVENT_TIMEOUT)
                assert err["message"] == _PIO_ERROR, (bad, err)

            await player.emit(
                "submit_answer",
                {
                    "question_id": question_id,
                    "answer_data": {"orderedIndices": [3, 1, 0, 2]},
                    "answer_time_ms": 100,
                },
            )
            received = await player.wait_for("answer_received", _EVENT_TIMEOUT)
            # Not alreadyAnswered → none of the rejected payloads was recorded.
            assert "alreadyAnswered" not in received, received
            assert received["pointsAwarded"] == pytest.approx(0.83)
            assert received["isCorrect"] is False

            await host.emit("host_advance", {})  # → results
            await host.wait_for("question_results", _EVENT_TIMEOUT)
            await player.wait_for("question_results", _EVENT_TIMEOUT)
            await host.emit("host_advance", {})  # → game over
            game_over = await player.wait_for("game_over", _EVENT_TIMEOUT)
            await host.wait_for("game_over", _EVENT_TIMEOUT)
            (summary,) = game_over["questionSummary"]
            assert summary["playerAnswer"] == {"orderedIndices": [3, 1, 0, 2]}
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
    """
    MC_ACCURACY, PIO_ACCURACY and PIO_COMPLETENESS, played in one session; then an
    unplayed MC_ACCURACY added afterwards (so it has no session_scores rows).
    """
    cleanup = Cleanup(api, admin_token)
    try:
        course_id, game_id = _new_course_and_game(api, admin_token, cleanup, "played")
        played_specs = [MC_ACCURACY, PIO_ACCURACY, PIO_COMPLETENESS]
        scenario = GameScenario(name="pio_played", questions=played_specs, player_scripts=[])
        mc_id, pio_acc_id, pio_comp_id = create_questions(
            base_url, admin_token, game_id, scenario, False
        )
        _play_session(
            base_url,
            admin_token,
            cleanup,
            course_id,
            game_id,
            played_specs,
            [{"selectedIndex": 1}, {"orderedIndices": [1, 3, 0, 2]}, {"orderedIndices": [0, 1, 2, 3]}],
        )
        unplayed = GameScenario(name="pio_unplayed", questions=[MC_ACCURACY], player_scripts=[])
        (unplayed_mc_id,) = create_questions(base_url, admin_token, game_id, unplayed, False)
        yield {
            "course_id": course_id,
            "game_id": game_id,
            "mc_id": mc_id,
            "pio_accuracy_id": pio_acc_id,
            "pio_completeness_id": pio_comp_id,
            "unplayed_mc_id": unplayed_mc_id,
        }
    finally:
        cleanup.run()


# ---------------------------------------------------------------------------
# Create / update validation (422)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "overrides",
    [
        {"answer_data": {"correct_order": [0, 1, 2, 3]}},
        {"config": {"items": ["A", "B"]}, "answer_data": {"correct_order": [1, 0]}},
        {"config": {"items": ["C", "A", "D", "B"], "answer": [1, 3, 0, 2]}},
    ],
    ids=["identity_correct_order", "two_items", "extra_config_key"],
)
def test_create_rejects_invalid(api: Api, admin_token: str, played_game: dict, overrides):
    r = api.post(
        f"/host/games/{played_game['game_id']}/questions",
        admin_token,
        json=_question_body(PIO_ACCURACY, **overrides),
    )
    assert r.status_code == 422, r.text


def test_update_making_unplayed_question_invalid_is_422(
    api: Api, admin_token: str, played_game: dict
):
    game_id = played_game["game_id"]
    r = api.post(f"/host/games/{game_id}/questions", admin_token, json=_question_body(PIO_ACCURACY))
    assert r.status_code == 201, r.text
    qid = r.json()["id"]
    try:
        before = _get_question(api, admin_token, game_id, qid)
        r = api.put(
            f"/host/games/{game_id}/questions/{qid}",
            admin_token,
            json={"answer_data": {"correct_order": [0, 1, 2, 3]}},
        )
        assert r.status_code == 422, r.text
        assert r.json()["error"] == "VALIDATION_ERROR"
        assert r.json()["message"] == "Display order must differ from the correct order"
        assert _get_question(api, admin_token, game_id, qid) == before
    finally:
        api.delete(f"/host/games/{game_id}/questions/{qid}", admin_token)


# ---------------------------------------------------------------------------
# Played-question guard (409)
# ---------------------------------------------------------------------------


def test_prompt_only_update_of_played_question_is_allowed(
    api: Api, admin_token: str, played_game: dict
):
    game_id, qid = played_game["game_id"], played_game["pio_accuracy_id"]
    r = api.put(
        f"/host/games/{game_id}/questions/{qid}",
        admin_token,
        json={
            "prompt": "Put the letters in alphabetical order (edited).",
            "config": PIO_ACCURACY.config,
            "answer_data": PIO_ACCURACY.answer_data,
        },
    )
    assert r.status_code == 200, r.text
    q = _get_question(api, admin_token, game_id, qid)
    assert q["prompt"] == "Put the letters in alphabetical order (edited)."
    assert q["config"]["items"] == PIO_ACCURACY.config["items"]
    assert q["answer_data"]["correct_order"] == PIO_ACCURACY.answer_data["correct_order"]


@pytest.mark.parametrize(
    "body",
    [
        {"config": {"items": ["A", "C", "D", "B"]}},
        {"answer_data": {"correct_order": [3, 1, 0, 2]}},
        {"type": "multiple_choice", "config": {"options": ["a", "b"]}, "answer_data": {"answer_points": [1, 0]}},
    ],
    ids=["items", "correct_order", "type"],
)
def test_changing_played_question_items_is_409(
    api: Api, admin_token: str, played_game: dict, body
):
    game_id, qid = played_game["game_id"], played_game["pio_accuracy_id"]
    before = _get_question(api, admin_token, game_id, qid)
    r = api.put(f"/host/games/{game_id}/questions/{qid}", admin_token, json=body)
    assert r.status_code == 409, r.text
    assert r.json()["message"] == _CONFLICT_MESSAGE
    after = _get_question(api, admin_token, game_id, qid)
    assert (after["type"], after["config"], after["answer_data"]) == (
        before["type"],
        before["config"],
        before["answer_data"],
    )


def test_played_mc_cannot_become_put_in_order(api: Api, admin_token: str, played_game: dict):
    game_id = played_game["game_id"]
    body = {
        "type": "put_in_order",
        "config": PIO_ACCURACY.config,
        "answer_data": PIO_ACCURACY.answer_data,
    }
    r = api.put(f"/host/games/{game_id}/questions/{played_game['mc_id']}", admin_token, json=body)
    assert r.status_code == 409, r.text

    r = api.put(
        f"/host/games/{game_id}/questions/{played_game['unplayed_mc_id']}", admin_token, json=body
    )
    assert r.status_code == 200, r.text
    assert r.json()["type"] == "put_in_order"


# ---------------------------------------------------------------------------
# Import
# ---------------------------------------------------------------------------


def test_import_with_identity_correct_order_is_422(
    api: Api, admin_token: str, played_game: dict, fn_cleanup: Cleanup
):
    bundle = _bundle([_question_body(PIO_ACCURACY, answer_data={"correct_order": [0, 1, 2, 3]})])
    r = api.post(
        "/host/games/import",
        admin_token,
        files=_files(bundle),
        data={"course_id": str(played_game["course_id"])},
    )
    if r.status_code == 201:  # don't leak a game if the assertion below fails
        fn_cleanup.games.append(r.json()["game_id"])
    assert r.status_code == 422, r.text


def test_imported_completeness_without_correct_order_prompt_edit(
    base_url: str, api: Api, admin_token: str, fn_cleanup: Cleanup
):
    """
    Regression: an imported COMPLETENESS question with no correct_order, once played, can
    still have its prompt edited when the editor resends the items and an empty
    answer_data (None == None for the guard); adding a correct_order is a 409.
    """
    tag = uuid.uuid4().hex[:8]
    r = api.post("/admin/courses", admin_token, json={"name": f"PIO import {tag}", "semester": "Test"})
    assert r.status_code == 201, r.text
    course_id = r.json()["id"]

    spec = QuestionSpec(
        type="put_in_order",
        grading_type="COMPLETENESS",
        prompt="Order these however you like.",
        config={"items": ["W", "X", "Y", "Z"]},
        answer_data={},
        points_value=1,
    )
    r = api.post(
        "/host/games/import",
        admin_token,
        files=_files(_bundle([_question_body(spec)])),
        data={"course_id": str(course_id)},
    )
    assert r.status_code == 201, r.text
    game_id = r.json()["game_id"]
    fn_cleanup.games.append(game_id)

    r = api.get(f"/host/games/{game_id}/questions", admin_token)
    assert r.status_code == 200, r.text
    (question,) = r.json()
    qid = question["id"]

    _play_session(base_url, admin_token, fn_cleanup, course_id, game_id, [spec], [{"orderedIndices": [0, 1, 2, 3]}])

    body = {"prompt": "Order these however you like (edited).", "config": spec.config, "answer_data": {}}
    r = api.put(f"/host/games/{game_id}/questions/{qid}", admin_token, json=body)
    assert r.status_code == 200, r.text
    q = _get_question(api, admin_token, game_id, qid)
    assert q["prompt"] == "Order these however you like (edited)."
    assert q["config"]["items"] == spec.config["items"]
    assert "correct_order" not in q["answer_data"]

    r = api.put(
        f"/host/games/{game_id}/questions/{qid}",
        admin_token,
        json={**body, "answer_data": {"correct_order": [1, 0, 3, 2]}},
    )
    assert r.status_code == 409, r.text
