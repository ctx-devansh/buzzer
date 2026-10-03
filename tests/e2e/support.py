"""
API helpers for the browser tests: set up users, courses, grants and games over
REST so each test drives the UI only for the behaviour it is checking.

Kept separate from tests/integration/ on purpose (that suite's helpers are private
to its test module); the shapes are the same.
"""

from __future__ import annotations

import pathlib
import uuid
from dataclasses import dataclass, field

import httpx

REPO_ROOT = pathlib.Path(__file__).parent.parent.parent
PASSWORD = "e2e-password-123"
TIMEOUT = 10.0

MC_QUESTION = {
    "type": "multiple_choice",
    "grading_type": "ACCURACY",
    "prompt": "E2E: which is first?",
    "config": {"options": ["first", "second"]},
    "answer_data": {"answer_points": [1, 0]},
    "points_value": 1,
    "time_limit_seconds": 30,
}


def read_env() -> dict[str, str]:
    env: dict[str, str] = {}
    path = REPO_ROOT / ".env"
    if path.exists():
        for line in path.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                env[k.strip()] = v.strip()
    return env


@dataclass
class Api:
    base_url: str

    def call(self, method: str, path: str, token: str | None = None, **kw) -> httpx.Response:
        headers = {"Authorization": f"Bearer {token}"} if token else {}
        return httpx.request(
            method, f"{self.base_url}/api{path}", headers=headers, timeout=TIMEOUT, **kw
        )

    def get(self, path: str, token: str | None = None, **kw) -> httpx.Response:
        return self.call("GET", path, token, **kw)

    def post(self, path: str, token: str | None = None, **kw) -> httpx.Response:
        return self.call("POST", path, token, **kw)

    def delete(self, path: str, token: str | None = None, **kw) -> httpx.Response:
        return self.call("DELETE", path, token, **kw)

    def login(self, username: str, password: str) -> str:
        r = self.post("/auth/login", json={"username": username, "password": password})
        assert r.status_code == 200, f"login {username} failed: {r.status_code} {r.text}"
        return r.json()["access_token"]


@dataclass
class User:
    id: str
    username: str
    token: str


@dataclass
class Cleanup:
    """Deletes what a fixture created: sessions, then games, then users."""

    api: Api
    admin: str
    sessions: list[str] = field(default_factory=list)
    games: list[int] = field(default_factory=list)
    users: list[str] = field(default_factory=list)

    def run(self) -> None:
        failed = []
        paths = (
            [f"/game/sessions/{sid}" for sid in self.sessions]
            + [f"/admin/games/{gid}" for gid in self.games]
            + [f"/admin/users/{uid}" for uid in self.users]
        )
        for path in paths:
            r = self.api.delete(path, self.admin)
            if r.status_code not in (204, 404):
                failed.append(f"DELETE {path} -> {r.status_code} {r.text[:200]}")
        assert not failed, "teardown failed:\n" + "\n".join(failed)

    # -- builders -------------------------------------------------------------

    def course(self, label: str, tag: str) -> dict:
        # Courses have no DELETE endpoint; the "E2E Course" prefix makes leftovers findable.
        r = self.api.post(
            "/admin/courses", self.admin, json={"name": f"E2E Course {label} {tag}", "semester": "E2E"}
        )
        assert r.status_code == 201, r.text
        return r.json()

    def user(self, name: str) -> User:
        username = f"e2e_{name}_{uuid.uuid4().hex[:6]}"
        r = self.api.post(
            "/admin/users",
            self.admin,
            json={"username": username, "display_name": f"E2E {name}", "password": PASSWORD},
        )
        assert r.status_code == 201, r.text
        uid = r.json()["id"]
        self.users.append(uid)
        return User(id=uid, username=username, token=self.api.login(username, PASSWORD))

    def grant_course(self, user: User, course_id: int, role: str) -> None:
        r = self.api.post(
            f"/admin/users/{user.id}/course-access",
            self.admin,
            json={"course_id": course_id, "role": role},
        )
        assert r.status_code == 204, r.text

    def grant_game(self, user: User, game_id: int) -> None:
        r = self.api.post(
            f"/admin/users/{user.id}/game-access", self.admin, json={"game_id": game_id}
        )
        assert r.status_code == 204, r.text

    def game(self, title: str, course_id: int | None, questions: int = 1) -> dict:
        body: dict = {"title": title}
        if course_id is not None:
            body["course_id"] = course_id
        r = self.api.post("/admin/games", self.admin, json=body)
        assert r.status_code == 201, r.text
        game = r.json()
        self.games.append(game["id"])
        for _ in range(questions):
            r = self.api.post(f"/admin/games/{game['id']}/questions", self.admin, json=MC_QUESTION)
            assert r.status_code == 201, r.text
        return game

    def track_games_titled(self, title: str) -> None:
        """Register games a test created through the UI (ids unknown up front)."""
        for g in self.api.get("/admin/games", self.admin).json():
            if g["title"] == title and g["id"] not in self.games:
                self.games.append(g["id"])


@dataclass
class Env:
    api: Api
    admin: str
    tag: str
    course_a: dict
    course_b: dict
    host: User          # HOST on A, PLAYER on B; granted game_a
    player_only: User   # PLAYER on A only
    game_a: dict        # attached to A, granted to host, played to COMPLETED once
    game_b: dict        # attached to B, granted to nobody
    completed_sid: str  # host's completed session of game_a
    guest_token: str    # the guest who played it
