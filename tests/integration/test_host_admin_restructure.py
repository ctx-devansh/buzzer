"""
Integration tests for the T4 host/admin restructure
(docs/design-host-admin-restructure.md §10).

Fixture shape — deliberately NOT conftest.game_setup's:
  * `t4_env` is session-scoped: courses A/B, host_a/host_b, a PLAYER-only user,
    an A-attached game granted to host_a, an A-attached game granted to nobody,
    a B-attached game granted to host_b, and an unattached game — built once.
  * Rows that mutate shared state (question CRUD, roster upload/patch, attach-to-
    course, revoked access) take their own function-scoped resources.
  * Teardown order: sessions (DELETE /game/sessions/{id} frees the Redis room
    slot), then games (DELETE /admin/games cascades sessions/scores), then users.
  * The two courses are left behind as inert records (there is no course DELETE
    endpoint), named "T4 Course A/B <tag>" so a leak is identifiable.
"""

from __future__ import annotations

import asyncio
import base64
import json
import uuid
from collections.abc import Iterator
from dataclasses import dataclass, field

import httpx
import pytest

from .conftest import create_guest_tokens
from .engine.orchestrator import run_game
from .engine.scoring import GameScenario, PlayerScript, QuestionSpec

_TIMEOUT = 10.0
_PASSWORD = "t4-password-123"

_MC_QUESTION = {
    "type": "multiple_choice",
    "grading_type": "ACCURACY",
    "prompt": "T4: which is first?",
    "config": {"options": ["first", "second"]},
    "answer_data": {"answer_points": [1, 0]},
    "points_value": 1,
    "time_limit_seconds": 30,
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _h(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _jwt_sub(token: str) -> str:
    payload = token.split(".")[1]
    payload += "=" * (-len(payload) % 4)
    return json.loads(base64.urlsafe_b64decode(payload))["sub"]


@dataclass
class Api:
    base_url: str

    def call(self, method: str, path: str, token: str, **kw) -> httpx.Response:
        return httpx.request(
            method, f"{self.base_url}/api{path}", headers=_h(token), timeout=_TIMEOUT, **kw
        )

    def get(self, path: str, token: str, **kw) -> httpx.Response:
        return self.call("GET", path, token, **kw)

    def post(self, path: str, token: str, **kw) -> httpx.Response:
        return self.call("POST", path, token, **kw)

    def put(self, path: str, token: str, **kw) -> httpx.Response:
        return self.call("PUT", path, token, **kw)

    def patch(self, path: str, token: str, **kw) -> httpx.Response:
        return self.call("PATCH", path, token, **kw)

    def delete(self, path: str, token: str, **kw) -> httpx.Response:
        return self.call("DELETE", path, token, **kw)


@dataclass
class Cleanup:
    """Records what a fixture created so teardown can delete it in the right order."""

    api: Api
    admin: str
    sessions: list[str] = field(default_factory=list)
    games: list[int] = field(default_factory=list)
    users: list[str] = field(default_factory=list)

    def run(self) -> None:
        for sid in self.sessions:
            self.api.delete(f"/game/sessions/{sid}", self.admin)
        for gid in self.games:
            self.api.delete(f"/admin/games/{gid}", self.admin)
        for uid in self.users:
            self.api.delete(f"/admin/users/{uid}", self.admin)


@dataclass
class User:
    id: str
    token: str


def _make_user(api: Api, admin: str, cleanup: Cleanup, name: str) -> User:
    username = f"t4_{name}_{uuid.uuid4().hex[:6]}"
    r = api.post(
        "/admin/users",
        admin,
        json={"username": username, "display_name": name, "password": _PASSWORD},
    )
    assert r.status_code == 201, r.text
    uid = r.json()["id"]
    cleanup.users.append(uid)
    r = httpx.post(
        f"{api.base_url}/api/auth/login",
        json={"username": username, "password": _PASSWORD},
        timeout=_TIMEOUT,
    )
    assert r.status_code == 200, r.text
    return User(id=uid, token=r.json()["access_token"])


def _grant_course(api: Api, admin: str, user: User, course_id: int, role: str) -> None:
    r = api.post(
        f"/admin/users/{user.id}/course-access",
        admin,
        json={"course_id": course_id, "role": role},
    )
    assert r.status_code == 204, r.text


def _grant_game(api: Api, admin: str, user: User, game_id: int) -> None:
    r = api.post(f"/admin/users/{user.id}/game-access", admin, json={"game_id": game_id})
    assert r.status_code == 204, r.text


def _admin_game(
    api: Api, admin: str, cleanup: Cleanup, title: str, course_id: int | None
) -> dict:
    body: dict = {"title": title}
    if course_id is not None:
        body["course_id"] = course_id
    r = api.post("/admin/games", admin, json=body)
    assert r.status_code == 201, r.text
    cleanup.games.append(r.json()["id"])
    return r.json()


def _create_room(api: Api, token: str, cleanup: Cleanup, game_id: int, course_id: int):
    r = api.post("/game/rooms", token, json={"game_id": game_id, "course_id": course_id})
    if r.status_code == 201:
        cleanup.sessions.append(r.json()["session_id"])
    return r


def _game_access(api: Api, admin: str, user_id: str) -> list[int]:
    r = api.get(f"/admin/users/{user_id}", admin)
    assert r.status_code == 200, r.text
    return r.json()["game_access"]


# ---------------------------------------------------------------------------
# Session-scoped environment
# ---------------------------------------------------------------------------


@dataclass
class T4Env:
    api: Api
    admin: str
    course_a: int
    course_b: int
    host_a: User
    host_b: User
    player_only: User
    game_a: dict  # attached to A, granted to host_a
    game_a_ungranted: dict  # attached to A, granted to nobody
    game_b: dict  # attached to B, granted to host_b
    game_unattached: dict


@pytest.fixture(scope="session")
def t4_env(docker_stack, base_url: str, admin_token: str) -> Iterator[T4Env]:
    api = Api(base_url)
    cleanup = Cleanup(api, admin_token)
    tag = uuid.uuid4().hex[:6]
    try:
        courses = []
        for label in ("A", "B"):
            r = api.post(
                "/admin/courses",
                admin_token,
                json={"name": f"T4 Course {label} {tag}", "semester": "T4"},
            )
            assert r.status_code == 201, r.text
            courses.append(r.json()["id"])
        course_a, course_b = courses

        host_a = _make_user(api, admin_token, cleanup, "host_a")
        host_b = _make_user(api, admin_token, cleanup, "host_b")
        player_only = _make_user(api, admin_token, cleanup, "player")
        _grant_course(api, admin_token, host_a, course_a, "HOST")
        _grant_course(api, admin_token, host_b, course_b, "HOST")
        _grant_course(api, admin_token, player_only, course_a, "PLAYER")

        game_a = _admin_game(api, admin_token, cleanup, f"T4 A {tag}", course_a)
        game_a_ungranted = _admin_game(
            api, admin_token, cleanup, f"T4 A ungranted {tag}", course_a
        )
        game_b = _admin_game(api, admin_token, cleanup, f"T4 B {tag}", course_b)
        game_unattached = _admin_game(
            api, admin_token, cleanup, f"T4 unattached {tag}", None
        )
        _grant_game(api, admin_token, host_a, game_a["id"])
        _grant_game(api, admin_token, host_b, game_b["id"])
        for g in (game_a, game_b, game_unattached):
            r = api.post(f"/admin/games/{g['id']}/questions", admin_token, json=_MC_QUESTION)
            assert r.status_code == 201, r.text

        yield T4Env(
            api=api,
            admin=admin_token,
            course_a=course_a,
            course_b=course_b,
            host_a=host_a,
            host_b=host_b,
            player_only=player_only,
            game_a=game_a,
            game_a_ungranted=game_a_ungranted,
            game_b=game_b,
            game_unattached=game_unattached,
        )
    finally:
        cleanup.run()


@dataclass
class CompletedSessions:
    host_a_sid: str
    host_b_sid: str
    guest_token: str


@pytest.fixture(scope="session")
def completed_sessions(t4_env: T4Env, base_url: str) -> Iterator[CompletedSessions]:
    """host_a and host_b each run their own game to COMPLETED with one guest player."""
    env = t4_env
    cleanup = Cleanup(env.api, env.admin)
    scenario = GameScenario(
        name="t4_one_question",
        questions=[QuestionSpec(**{k: v for k, v in _MC_QUESTION.items()})],
        player_scripts=[PlayerScript(responses=[{"selectedIndex": 0}])],
    )
    try:
        sids = []
        guest_token = ""
        for host, game, course in (
            (env.host_a, env.game_a, env.course_a),
            (env.host_b, env.game_b, env.course_b),
        ):
            r = _create_room(env.api, host.token, cleanup, game["id"], course)
            assert r.status_code == 201, r.text
            room_code = r.json()["room_code"]
            sids.append(r.json()["session_id"])
            tokens = create_guest_tokens(base_url, room_code, 1)
            cleanup.users.append(_jwt_sub(tokens[0]))
            guest_token = tokens[0]
            asyncio.run(
                run_game(
                    base_url=base_url,
                    host_token=host.token,
                    player_tokens=tokens,
                    room_code=room_code,
                    scenario=scenario,
                )
            )
        yield CompletedSessions(sids[0], sids[1], guest_token)
    finally:
        cleanup.run()


@pytest.fixture()
def fn_cleanup(t4_env: T4Env) -> Iterator[Cleanup]:
    cleanup = Cleanup(t4_env.api, t4_env.admin)
    yield cleanup
    cleanup.run()


# ---------------------------------------------------------------------------
# Visibility (§3.3)
# ---------------------------------------------------------------------------


def test_my_games_applies_intersection_rule(t4_env: T4Env):
    env = t4_env
    r = env.api.get("/game/my-games", env.host_a.token)
    assert r.status_code == 200
    ids = {g["id"] for g in r.json()}
    assert ids == {env.game_a["id"]}
    row = r.json()[0]
    assert row["course_id"] == env.course_a
    assert row["course_name"] == env.game_a["course_name"]


def test_my_games_listed_implies_creatable(t4_env: T4Env, fn_cleanup: Cleanup):
    env = t4_env
    games = env.api.get("/game/my-games", env.host_a.token).json()
    assert games
    for g in games:
        r = _create_room(env.api, env.host_a.token, fn_cleanup, g["id"], g["course_id"])
        assert r.status_code == 201, r.text


def test_my_games_course_filter_is_forgiving(t4_env: T4Env):
    env = t4_env
    r = env.api.get(f"/game/my-games?course_id={env.course_b}", env.host_a.token)
    assert r.status_code == 200
    assert r.json() == []
    r = env.api.get(f"/game/my-games?course_id={env.course_a}", env.host_a.token)
    assert [g["id"] for g in r.json()] == [env.game_a["id"]]


def test_host_games_course_param_is_a_gate(t4_env: T4Env):
    env = t4_env
    assert env.api.get(f"/host/games?course_id={env.course_b}", env.host_a.token).status_code == 403
    # Non-admin: a missing course looks like a missing grant (existence not leaked).
    assert env.api.get("/host/games?course_id=99999999", env.host_a.token).status_code == 403
    assert env.api.get("/host/games?course_id=99999999", env.admin).status_code == 404
    r = env.api.get(f"/host/games?course_id={env.course_a}", env.host_a.token)
    assert r.status_code == 200
    assert {g["id"] for g in r.json()} == {env.game_a["id"]}


def test_admin_sees_unattached_only_without_course_filter(t4_env: T4Env):
    env = t4_env
    all_ids = {g["id"] for g in env.api.get("/host/games", env.admin).json()}
    a_ids = {
        g["id"]
        for g in env.api.get(f"/host/games?course_id={env.course_a}", env.admin).json()
    }
    assert env.game_unattached["id"] in all_ids
    assert env.game_unattached["id"] not in a_ids
    assert {env.game_a["id"], env.game_a_ungranted["id"]} <= a_ids
    assert env.game_b["id"] not in a_ids


# ---------------------------------------------------------------------------
# Access
# ---------------------------------------------------------------------------


def test_host_without_game_grant_cannot_create_room(t4_env: T4Env, fn_cleanup: Cleanup):
    env = t4_env
    r = _create_room(
        env.api, env.host_a.token, fn_cleanup, env.game_a_ungranted["id"], env.course_a
    )
    assert r.status_code == 403


def test_player_only_user_has_no_host_courses(t4_env: T4Env):
    env = t4_env
    r = env.api.get("/game/my-courses", env.player_only.token)
    assert r.status_code == 200
    assert r.json() == []
    r = env.api.get(f"/host/games?course_id={env.course_a}", env.player_only.token)
    assert r.status_code == 403


def test_admin_my_courses_lists_every_course_as_host(t4_env: T4Env):
    env = t4_env
    mine = env.api.get("/game/my-courses", env.admin).json()
    every = env.api.get("/admin/courses", env.admin).json()
    assert {c["id"] for c in mine} == {c["id"] for c in every}
    assert all(c["role"] == "HOST" for c in mine)


def test_guest_token_gets_403_from_my_courses(completed_sessions: CompletedSessions, t4_env):
    r = t4_env.api.get("/game/my-courses", completed_sessions.guest_token)
    assert r.status_code == 403
    assert r.json()["message"] == "Authenticated account required"


# ---------------------------------------------------------------------------
# H5 — course-specific games
# ---------------------------------------------------------------------------


def test_game_cannot_run_in_another_course(t4_env: T4Env, fn_cleanup: Cleanup):
    env = t4_env
    r = _create_room(env.api, env.host_a.token, fn_cleanup, env.game_b["id"], env.course_a)
    assert r.status_code == 403
    # The course-identity rule is role-blind: not even ADMIN may run B's game in A.
    r = _create_room(env.api, env.admin, fn_cleanup, env.game_b["id"], env.course_a)
    assert r.status_code == 403


def test_unattached_game_is_admin_only(t4_env: T4Env, fn_cleanup: Cleanup):
    env = t4_env
    gid = env.game_unattached["id"]
    r = _create_room(env.api, env.host_a.token, fn_cleanup, gid, env.course_a)
    assert r.status_code == 403
    r = _create_room(env.api, env.admin, fn_cleanup, gid, env.course_a)
    assert r.status_code == 201, r.text


# ---------------------------------------------------------------------------
# H4 — game and question management
# ---------------------------------------------------------------------------


@pytest.fixture()
def host_a_game(t4_env: T4Env, fn_cleanup: Cleanup) -> dict:
    """A fresh game created by host_a through the host route."""
    env = t4_env
    r = env.api.post(
        "/host/games",
        env.host_a.token,
        json={"title": "T4 host-created", "description": "", "max_players": 20, "course_id": env.course_a},
    )
    assert r.status_code == 201, r.text
    fn_cleanup.games.append(r.json()["id"])
    return r.json()


def test_host_create_game_autogrants_and_returns_course_name(t4_env: T4Env, host_a_game: dict):
    env = t4_env
    assert host_a_game["course_id"] == env.course_a
    assert host_a_game["course_name"] == env.game_a["course_name"]
    assert host_a_game["course_name"]
    assert host_a_game["id"] in _game_access(env.api, env.admin, env.host_a.id)


def test_host_cannot_create_game_in_unhosted_course(t4_env: T4Env, fn_cleanup: Cleanup):
    env = t4_env
    r = env.api.post(
        "/host/games",
        env.host_a.token,
        json={"title": "nope", "course_id": env.course_b},
    )
    if r.status_code == 201:
        fn_cleanup.games.append(r.json()["id"])
    assert r.status_code == 403


def test_host_question_crud_and_reorder(t4_env: T4Env, host_a_game: dict):
    env = t4_env
    tok = env.host_a.token
    base = f"/host/games/{host_a_game['id']}/questions"

    ids = []
    for i in range(3):
        r = env.api.post(base, tok, json={**_MC_QUESTION, "prompt": f"Q{i} <script>x</script><b>b</b>"})
        assert r.status_code == 201, r.text
        assert "<script>" not in r.json()["prompt"]  # bleach ran on the host path too
        ids.append(r.json()["id"])

    r = env.api.put(f"{base}/{ids[0]}", tok, json={"prompt": "edited", "points_value": 5})
    assert r.status_code == 200, r.text
    assert r.json()["prompt"] == "edited"
    assert r.json()["points_value"] == 5

    new_order = [ids[2], ids[0], ids[1]]
    r = env.api.post(f"{base}/reorder", tok, json={"order": new_order})
    assert r.status_code == 204, r.text
    listed = env.api.get(base, tok).json()
    assert [q["id"] for q in listed] == new_order

    assert env.api.delete(f"{base}/{ids[1]}", tok).status_code == 204
    assert [q["id"] for q in env.api.get(base, tok).json()] == [ids[2], ids[0]]

    r = env.api.get(f"/host/games/{host_a_game['id']}/export", tok)
    assert r.status_code == 200
    bundle = r.json()
    assert bundle["version"] == 1
    assert "course_id" not in bundle["game"]
    assert len(bundle["questions"]) == 2


def test_host_question_calls_on_other_course_game_are_403(t4_env: T4Env):
    env = t4_env
    tok = env.host_a.token
    gid = env.game_b["id"]
    qid = env.api.get(f"/host/games/{gid}/questions", env.admin).json()[0]["id"]
    assert env.api.get(f"/host/games/{gid}", tok).status_code == 403
    assert env.api.get(f"/host/games/{gid}/questions", tok).status_code == 403
    assert env.api.post(f"/host/games/{gid}/questions", tok, json=_MC_QUESTION).status_code == 403
    assert env.api.put(f"/host/games/{gid}/questions/{qid}", tok, json={"prompt": "x"}).status_code == 403
    assert env.api.delete(f"/host/games/{gid}/questions/{qid}", tok).status_code == 403
    assert env.api.post(f"/host/games/{gid}/questions/reorder", tok, json={"order": [qid]}).status_code == 403
    assert env.api.get(f"/host/games/{gid}/export", tok).status_code == 403
    assert env.api.put(f"/host/games/{gid}", tok, json={"title": "x"}).status_code == 403


def test_host_question_must_belong_to_game(t4_env: T4Env, host_a_game: dict):
    env = t4_env
    other_qid = env.api.get(f"/host/games/{env.game_a['id']}/questions", env.host_a.token).json()[0]["id"]
    r = env.api.put(
        f"/host/games/{host_a_game['id']}/questions/{other_qid}",
        env.host_a.token,
        json={"prompt": "x"},
    )
    assert r.status_code == 404


def test_host_game_update_rejects_course_id(t4_env: T4Env, host_a_game: dict):
    env = t4_env
    gid = host_a_game["id"]
    r = env.api.put(f"/host/games/{gid}", env.host_a.token, json={"title": "x", "course_id": env.course_b})
    assert r.status_code == 422
    stored = env.api.get(f"/host/games/{gid}", env.host_a.token).json()
    assert stored["course_id"] == env.course_a
    assert stored["title"] == host_a_game["title"]

    r = env.api.put(f"/host/games/{gid}", env.host_a.token, json={"title": "renamed"})
    assert r.status_code == 200
    assert r.json()["title"] == "renamed"
    assert r.json()["course_name"] == env.game_a["course_name"]


def test_host_import_attaches_to_form_course_and_autogrants(t4_env: T4Env, fn_cleanup: Cleanup):
    env = t4_env
    bundle = {
        "format": "buzzer/game",
        "version": 1,
        # A hand-edited course_id in the file must be discarded, not honoured.
        "game": {"title": "T4 imported", "description": "", "max_players": 10, "course_id": env.course_b},
        "questions": [_MC_QUESTION],
    }
    files = {"file": ("g.json", json.dumps(bundle), "application/json")}
    r = env.api.post("/host/games/import", env.host_a.token, files=files, data={"course_id": str(env.course_a)})
    assert r.status_code == 201, r.text
    gid = r.json()["game_id"]
    fn_cleanup.games.append(gid)
    game = env.api.get(f"/host/games/{gid}", env.host_a.token).json()
    assert game["course_id"] == env.course_a
    assert gid in _game_access(env.api, env.admin, env.host_a.id)

    r = env.api.post("/host/games/import", env.host_a.token, files=files, data={"course_id": str(env.course_b)})
    assert r.status_code == 403


def test_admin_create_game_with_course_does_not_autogrant(t4_env: T4Env, fn_cleanup: Cleanup):
    env = t4_env
    game = _admin_game(env.api, env.admin, fn_cleanup, "T4 admin-created", env.course_a)
    assert game["course_id"] == env.course_a
    assert game["course_name"] == env.game_a["course_name"]
    assert game["id"] not in _game_access(env.api, env.admin, _jwt_sub(env.admin))
    assert game["id"] not in {g["id"] for g in env.api.get("/game/my-games", env.host_a.token).json()}


def test_admin_create_game_with_missing_course_is_404(t4_env: T4Env, fn_cleanup: Cleanup):
    env = t4_env
    r = env.api.post("/admin/games", env.admin, json={"title": "x", "course_id": 99999999})
    if r.status_code == 201:
        fn_cleanup.games.append(r.json()["id"])
    assert r.status_code == 404


def test_admin_attach_course_once_then_409(t4_env: T4Env, fn_cleanup: Cleanup):
    env = t4_env
    game = _admin_game(env.api, env.admin, fn_cleanup, "T4 to attach", None)
    assert game["course_id"] is None and game["course_name"] is None

    r = env.api.put(f"/admin/games/{game['id']}", env.admin, json={"course_id": env.course_a})
    assert r.status_code == 200, r.text
    assert r.json()["course_id"] == env.course_a
    assert r.json()["course_name"] == env.game_a["course_name"]

    r = env.api.put(f"/admin/games/{game['id']}", env.admin, json={"course_id": env.course_b})
    assert r.status_code == 409
    stored = env.api.get(f"/admin/games/{game['id']}", env.admin).json()
    assert stored["course_id"] == env.course_a


# ---------------------------------------------------------------------------
# H3 — roster management
# ---------------------------------------------------------------------------


def test_host_roster_upload_patch_and_deactivate(t4_env: T4Env):
    env = t4_env
    tok = env.host_a.token
    base = f"/host/courses/{env.course_a}/roster"
    tag = uuid.uuid4().hex[:6]
    keep, drop = f"t4keep{tag}", f"t4drop{tag}"

    rows = [
        {"netid": keep, "full_name": "Keep Me", "email": f"{keep}@example.com"},
        {"netid": drop, "full_name": "Drop Me", "email": f"{drop}@example.com"},
    ]
    r = env.api.post(f"{base}/import", tok, json={"rows": rows})
    assert r.status_code == 200, r.text
    assert r.json()["imported"] == 2

    r = env.api.post(f"{base}/import", tok, json={"rows": rows[:1]})
    assert r.status_code == 200, r.text
    assert r.json()["deactivated"] == 1  # course A is new this session: only `drop` is absent

    entries = {e["netid"]: e for e in env.api.get(base, tok).json()}
    assert entries[keep]["is_active"] is True
    assert entries[drop]["is_active"] is False

    r = env.api.patch(f"{base}/{entries[drop]['id']}", tok, json={"is_active": True, "full_name": " Back "})
    assert r.status_code == 200, r.text
    assert r.json()["is_active"] is True
    assert r.json()["full_name"] == "Back"


def test_host_roster_other_course_is_403_and_foreign_rid_404(t4_env: T4Env):
    env = t4_env
    tok = env.host_a.token
    b_base = f"/host/courses/{env.course_b}/roster"
    assert env.api.get(b_base, tok).status_code == 403
    rows = [{"netid": "x", "full_name": "x", "email": "x@example.com"}]
    assert env.api.post(f"{b_base}/import", tok, json={"rows": rows}).status_code == 403

    netid = f"t4b{uuid.uuid4().hex[:6]}"
    r = env.api.post(
        f"/admin/courses/{env.course_b}/roster/import",
        env.admin,
        json={"rows": [{"netid": netid, "full_name": "B Student", "email": f"{netid}@example.com"}]},
    )
    assert r.status_code == 200, r.text
    rid = next(e["id"] for e in env.api.get(f"/admin/courses/{env.course_b}/roster", env.admin).json() if e["netid"] == netid)

    assert env.api.patch(f"{b_base}/{rid}", tok, json={"is_active": False}).status_code == 403
    r = env.api.patch(f"/host/courses/{env.course_a}/roster/{rid}", tok, json={"is_active": False})
    assert r.status_code == 404


# ---------------------------------------------------------------------------
# H1/H2 + Sessions
# ---------------------------------------------------------------------------


def test_host_downloads_own_completed_session(t4_env: T4Env, completed_sessions: CompletedSessions):
    env = t4_env
    sid = completed_sessions.host_a_sid
    for path, ctype in (
        (f"/host/sessions/{sid}/report", "text/html"),
        (f"/game/sessions/{sid}/export", "text/csv"),
    ):
        r = env.api.get(path, env.host_a.token)
        assert r.status_code == 200, (path, r.text)
        assert r.headers["content-type"].startswith(ctype)
        disposition = r.headers["content-disposition"]
        assert 'filename="' in disposition and disposition.endswith('"')
        assert r.content


def test_host_cannot_download_other_hosts_session(t4_env: T4Env, completed_sessions: CompletedSessions):
    env = t4_env
    sid = completed_sessions.host_b_sid
    assert env.api.get(f"/host/sessions/{sid}/report", env.host_a.token).status_code == 403
    assert env.api.get(f"/game/sessions/{sid}/export", env.host_a.token).status_code == 403


def test_host_sessions_lists_only_own(t4_env: T4Env, completed_sessions: CompletedSessions):
    env = t4_env
    rows = env.api.get("/host/sessions", env.host_a.token).json()
    sids = {r["session_id"] for r in rows}
    assert completed_sessions.host_a_sid in sids
    assert completed_sessions.host_b_sid not in sids
    row = next(r for r in rows if r["session_id"] == completed_sessions.host_a_sid)
    assert row["status"] == "COMPLETED"
    assert isinstance(row["session_id"], str)

    admin_sids = {r["session_id"] for r in env.api.get("/host/sessions", env.admin).json()}
    assert {completed_sessions.host_a_sid, completed_sessions.host_b_sid} <= admin_sids

    completed = env.api.get("/host/sessions?status=COMPLETED", env.host_a.token).json()
    assert completed and all(r["status"] == "COMPLETED" for r in completed)
    abandoned = env.api.get("/host/sessions?status=ABANDONED", env.host_a.token).json()
    assert completed_sessions.host_a_sid not in {r["session_id"] for r in abandoned}
    assert env.api.get("/host/sessions?status=ACTIVE", env.host_a.token).status_code == 422


def test_session_row_identical_from_admin_and_host_routes(t4_env: T4Env, completed_sessions: CompletedSessions):
    env = t4_env
    sid = completed_sessions.host_a_sid
    admin_row = next(r for r in env.api.get("/admin/sessions", env.admin).json() if r["session_id"] == sid)
    host_row = next(r for r in env.api.get("/host/sessions", env.host_a.token).json() if r["session_id"] == sid)
    assert admin_row == host_row
    assert admin_row["player_count"] == 1


def test_revoked_host_keeps_own_sessions(t4_env: T4Env, fn_cleanup: Cleanup):
    env = t4_env
    host = _make_user(env.api, env.admin, fn_cleanup, "revoked")
    _grant_course(env.api, env.admin, host, env.course_a, "HOST")
    _grant_game(env.api, env.admin, host, env.game_a["id"])
    r = _create_room(env.api, host.token, fn_cleanup, env.game_a["id"], env.course_a)
    assert r.status_code == 201, r.text
    sid = r.json()["session_id"]

    r = env.api.delete(f"/admin/users/{host.id}/course-access/{env.course_a}", env.admin)
    assert r.status_code == 204

    assert env.api.get("/game/my-courses", host.token).json() == []
    r = env.api.get("/host/sessions", host.token)
    assert r.status_code == 200
    assert sid in {s["session_id"] for s in r.json()}
    r = env.api.get("/game/my-active-sessions", host.token)
    assert r.status_code == 200
    assert sid in {s["session_id"] for s in r.json()}
    # ...while game management is gone.
    assert env.api.get(f"/host/games/{env.game_a['id']}", host.token).status_code == 403


# ---------------------------------------------------------------------------
# Beyond §10: paths T4 refactored or added that the §10 table does not name
# ---------------------------------------------------------------------------


def _bundle(**game) -> dict:
    return {
        "format": "buzzer/game",
        "version": 1,
        "game": {"title": "T4 bundle", "description": "", "max_players": 10, **game},
        "questions": [_MC_QUESTION, {**_MC_QUESTION, "prompt": "second"}],
    }


def _files(bundle: dict | str) -> dict:
    body = bundle if isinstance(bundle, str) else json.dumps(bundle)
    return {"file": ("g.json", body, "application/json")}


def test_unauthenticated_and_guest_are_rejected_on_host_routes(
    t4_env: T4Env, completed_sessions: CompletedSessions
):
    env = t4_env
    r = httpx.get(f"{env.api.base_url}/api/host/games", timeout=_TIMEOUT)
    assert r.status_code == 401
    guest = completed_sessions.guest_token
    assert env.api.get("/host/games", guest).status_code == 403
    assert env.api.get("/host/sessions", guest).status_code == 403
    assert env.api.post("/host/games", guest, json={"title": "x", "course_id": env.course_a}).status_code == 403


def test_host_cannot_read_unattached_or_missing_game(t4_env: T4Env):
    env = t4_env
    tok = env.host_a.token
    assert env.api.get(f"/host/games/{env.game_unattached['id']}", tok).status_code == 403
    assert env.api.get(f"/host/games/{env.game_a_ungranted['id']}", tok).status_code == 403
    # A missing game is a 403 for a host (ids not leaked), a 404 for ADMIN.
    assert env.api.get("/host/games/99999999", tok).status_code == 403
    assert env.api.get("/host/games/99999999", env.admin).status_code == 404
    assert env.api.get(f"/host/games/{env.game_unattached['id']}", env.admin).status_code == 200


def test_hosts_cannot_delete_games(t4_env: T4Env, host_a_game: dict):
    env = t4_env
    gid = host_a_game["id"]
    # No DELETE on the host router at all, and the admin route stays admin-only.
    assert env.api.delete(f"/host/games/{gid}", env.host_a.token).status_code == 405
    assert env.api.delete(f"/admin/games/{gid}", env.host_a.token).status_code == 403
    assert env.api.get(f"/host/games/{gid}", env.host_a.token).status_code == 200


def test_other_host_cannot_see_host_created_game(t4_env: T4Env, host_a_game: dict):
    env = t4_env
    ids = {g["id"] for g in env.api.get("/host/games", env.host_b.token).json()}
    assert host_a_game["id"] not in ids
    assert env.api.get(f"/host/games/{host_a_game['id']}", env.host_b.token).status_code == 403


def test_host_reorder_rejects_wrong_id_set(t4_env: T4Env, host_a_game: dict):
    env = t4_env
    base = f"/host/games/{host_a_game['id']}/questions"
    qid = env.api.post(base, env.host_a.token, json=_MC_QUESTION).json()["id"]
    r = env.api.post(f"{base}/reorder", env.host_a.token, json={"order": [qid, 99999999]})
    assert r.status_code == 409


def test_host_report_for_missing_session_is_404(t4_env: T4Env):
    env = t4_env
    assert env.api.get(f"/host/sessions/{uuid.uuid4()}/report", env.host_a.token).status_code == 404


def test_export_then_import_into_a_different_course(t4_env: T4Env, fn_cleanup: Cleanup):
    """§3.2: the bundle is course-free, so a game round-trips into another course."""
    env = t4_env
    r = env.api.get(f"/host/games/{env.game_a['id']}/export", env.admin)
    assert r.status_code == 200
    exported = r.json()
    r = env.api.post(
        "/host/games/import",
        env.admin,
        files=_files(exported),
        data={"course_id": str(env.course_b)},
    )
    assert r.status_code == 201, r.text
    gid = r.json()["game_id"]
    fn_cleanup.games.append(gid)
    game = env.api.get(f"/host/games/{gid}", env.admin).json()
    assert game["course_id"] == env.course_b
    assert game["title"] == env.game_a["title"]
    src = env.api.get(f"/host/games/{env.game_a['id']}/questions", env.admin).json()
    dst = env.api.get(f"/host/games/{gid}/questions", env.admin).json()
    keys = ("type", "grading_type", "prompt", "config", "answer_data", "points_value")
    assert [{k: q[k] for k in keys} for q in dst] == [{k: q[k] for k in keys} for q in src]


@pytest.mark.parametrize(
    "body,fragment",
    [
        ("not json", "Invalid JSON"),
        ({**_bundle(), "format": "other"}, "Unrecognised file format"),
        ({**_bundle(), "version": 2}, "Unsupported version"),
        (_bundle(title=""), "Invalid game metadata"),
        ({**_bundle(), "questions": [{**_MC_QUESTION, "config": {"options": ["one"]}}]}, "Question 1 invalid"),
        ({**_bundle(), "game": "x"}, "'game' must be an object"),
        ({**_bundle(), "game": [["title", "x"]]}, "'game' must be an object"),
        ({**_bundle(), "questions": {"a": 1}}, "'questions' must be a list"),
        ([1, 2], "Unrecognised file format"),
    ],
    ids=["not-json", "format", "version", "metadata", "question", "game-str", "game-list", "questions-dict", "bundle-list"],
)
@pytest.mark.parametrize("route", ["host", "admin"])
def test_bad_bundle_is_422_on_both_import_routes(t4_env: T4Env, fn_cleanup: Cleanup, route, body, fragment):
    env = t4_env
    if route == "host":
        r = env.api.post("/host/games/import", env.host_a.token, files=_files(body), data={"course_id": str(env.course_a)})
    else:
        r = env.api.post("/admin/games/import", env.admin, files=_files(body))
    if r.status_code == 201:
        fn_cleanup.games.append(r.json()["game_id"])
    assert r.status_code == 422
    assert fragment in r.json()["detail"]


def test_admin_import_lands_unattached_and_ungranted(t4_env: T4Env, fn_cleanup: Cleanup):
    env = t4_env
    r = env.api.post("/admin/games/import", env.admin, files=_files(_bundle(course_id=env.course_a)))
    assert r.status_code == 201, r.text
    gid = r.json()["game_id"]
    fn_cleanup.games.append(gid)
    game = env.api.get(f"/admin/games/{gid}", env.admin).json()
    assert game["course_id"] is None  # the bundle's course_id is discarded, not honoured
    assert gid not in _game_access(env.api, env.admin, _jwt_sub(env.admin))
    assert len(env.api.get(f"/admin/games/{gid}/questions", env.admin).json()) == 2


def test_admin_question_routes_still_work_after_extraction(t4_env: T4Env, fn_cleanup: Cleanup):
    """The admin question routes now call services/authoring_service.py — regression-check them."""
    env = t4_env
    game = _admin_game(env.api, env.admin, fn_cleanup, "T4 admin authoring", None)
    base = f"/admin/games/{game['id']}/questions"
    ids = [
        env.api.post(base, env.admin, json={**_MC_QUESTION, "prompt": f"Q{i}<script>x</script>"}).json()["id"]
        for i in range(3)
    ]
    assert all("<script>" not in q["prompt"] for q in env.api.get(base, env.admin).json())
    r = env.api.put(f"{base}/{ids[1]}", env.admin, json={"prompt": "edited"})
    assert r.status_code == 200 and r.json()["prompt"] == "edited"
    assert env.api.post(f"{base}/reorder", env.admin, json={"order": ids[::-1]}).status_code == 204
    assert [q["id"] for q in env.api.get(base, env.admin).json()] == ids[::-1]
    assert env.api.post(f"{base}/reorder", env.admin, json={"order": ids[:1]}).status_code == 409
    assert env.api.delete(f"{base}/{ids[0]}", env.admin).status_code == 204
    assert env.api.delete(f"{base}/{ids[0]}", env.admin).status_code == 404
    r = env.api.get(f"/admin/games/{game['id']}/export", env.admin)
    assert r.status_code == 200
    assert [q["prompt"] for q in r.json()["questions"]] == ["Q2x", "edited"]  # bleach strips the tag, keeps its text


def test_admin_roster_patch_still_scoped_to_course(t4_env: T4Env):
    """admin.patch_roster_entry now calls roster_service — the course scoping must survive."""
    env = t4_env
    netid = f"t4adm{uuid.uuid4().hex[:6]}"
    r = env.api.post(
        f"/admin/courses/{env.course_b}/roster/import",
        env.admin,
        json={"rows": [{"netid": netid, "full_name": "Adm", "email": f"{netid}@example.com"}]},
    )
    assert r.status_code == 200, r.text
    rid = next(e["id"] for e in env.api.get(f"/admin/courses/{env.course_b}/roster", env.admin).json() if e["netid"] == netid)
    r = env.api.patch(f"/admin/courses/{env.course_b}/roster/{rid}", env.admin, json={"netid": "  MiXeD  "})
    assert r.status_code == 200 and r.json()["netid"] == "mixed"
    assert env.api.patch(f"/admin/courses/{env.course_a}/roster/{rid}", env.admin, json={"is_active": False}).status_code == 404
