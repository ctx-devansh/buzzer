"""
Browser (Playwright) tests against the nginx deployment on :8080, which serves the
built host/admin/player apps from one origin and proxies /api and /socket.io.

Prerequisites
-------------
    docker compose up -d        # the stack, including nginx on :8080
    npm run build               # nginx serves frontend/*/dist — rebuild after UI changes
    pip install -r tests/e2e/requirements.txt && playwright install chromium

Run:  pytest tests/e2e            (add --headed or --slowmo 300 to watch)

Shape
-----
* Data is set up over REST (support.py); the browser only exercises the UI under test.
* Signing in is done by seeding `localStorage.token` before the page loads (all apps
  share one origin and one token key). One test signs in through the real login form.
* `env` is session-scoped and read-only; tests that mutate build their own resources
  with the function-scoped `cleanup`.
* Courses cannot be deleted (no endpoint) and are left behind as "E2E Course …".
"""

from __future__ import annotations

import asyncio
import base64
import json
import os
import threading
import uuid
from collections.abc import Callable, Iterator

import httpx
import pytest
from playwright.sync_api import Browser, Page

from tests.integration.engine.orchestrator import run_game
from tests.integration.engine.scoring import GameScenario, PlayerScript, QuestionSpec

from .support import MC_QUESTION, REPO_ROOT, Api, Cleanup, Env, read_env

_DEFAULT_BASE_URL = "http://localhost:8080"


@pytest.fixture(scope="session")
def base_url(request) -> str:
    """Overrides pytest-base-url's fixture; page.goto('/host/...') resolves against it."""
    return (request.config.getoption("--base-url") or _DEFAULT_BASE_URL).rstrip("/")


@pytest.fixture(scope="session")
def api(base_url: str) -> Api:
    try:
        ok = httpx.get(f"{base_url}/api/health", timeout=3).status_code == 200
        ok = ok and httpx.get(f"{base_url}/host/", timeout=3).status_code == 200
    except httpx.HTTPError:
        ok = False
    if not ok:
        pytest.skip(f"{base_url} is not serving the apps — run `docker compose up -d` and `npm run build`")
    return Api(base_url)


@pytest.fixture(scope="session", autouse=True)
def _built_apps_are_current(api: Api) -> None:
    """A stale dist/ makes every UI assertion meaningless, so refuse to run on one."""
    if os.environ.get("E2E_SKIP_BUILD_CHECK"):
        return
    stale = []
    for app in ("host", "admin"):
        src = REPO_ROOT / "frontend" / app / "src"
        index = REPO_ROOT / "frontend" / app / "dist" / "index.html"
        newest_src = max(p.stat().st_mtime for p in src.rglob("*") if p.is_file())
        if not index.exists() or index.stat().st_mtime < newest_src:
            stale.append(app)
    if stale:
        pytest.fail(
            f"frontend/{{{','.join(stale)}}}/dist is older than its src/ — run `npm run build` "
            "(or set E2E_SKIP_BUILD_CHECK=1)",
            pytrace=False,
        )


@pytest.fixture(scope="session")
def admin_token(api: Api) -> str:
    env = read_env()
    return api.login(
        env.get("ADMIN_USERNAME") or os.environ.get("ADMIN_USERNAME", "admin"),
        env.get("ADMIN_PASSWORD") or os.environ.get("ADMIN_PASSWORD", "changeme123"),
    )


# ---------------------------------------------------------------------------
# Signed-in pages
# ---------------------------------------------------------------------------


@pytest.fixture()
def page_as(browser: Browser, base_url: str) -> Iterator[Callable[[str | None], Page]]:
    """
    page_as(token) -> a Page in a fresh context whose localStorage.token is `token`
    (None = signed out). Each call is isolated, like a separate private window.
    """
    contexts = []

    def make(token: str | None) -> Page:
        context = browser.new_context(base_url=base_url, accept_downloads=True)
        if token:
            context.add_init_script(f"window.localStorage.setItem('token', {token!r});")
        contexts.append(context)
        return context.new_page()

    yield make
    for context in contexts:
        context.close()


# ---------------------------------------------------------------------------
# Shared, read-only world
# ---------------------------------------------------------------------------


def _jwt_sub(token: str) -> str:
    payload = token.split(".")[1]
    payload += "=" * (-len(payload) % 4)
    return json.loads(base64.urlsafe_b64decode(payload))["sub"]


def _play_to_completion(base_url: str, host_token: str, room_code: str, guest_token: str) -> None:
    """
    Run one game over Socket.IO with the integration engine. In a thread of its own
    because Playwright's sync API owns the main thread's event loop.
    """
    scenario = GameScenario(
        name="e2e_one_question",
        questions=[QuestionSpec(**MC_QUESTION)],
        player_scripts=[PlayerScript(responses=[{"selectedIndex": 0}])],
    )
    errors: list[BaseException] = []

    def target() -> None:
        try:
            asyncio.run(run_game(base_url, host_token, [guest_token], room_code, scenario))
        except BaseException as exc:  # re-raised on the main thread
            errors.append(exc)

    thread = threading.Thread(target=target)
    thread.start()
    thread.join(timeout=120)
    assert not thread.is_alive(), "game did not finish within 120s"
    if errors:
        raise errors[0]


@pytest.fixture(scope="session")
def env(api: Api, admin_token: str) -> Iterator[Env]:
    cleanup = Cleanup(api, admin_token)
    tag = uuid.uuid4().hex[:6]
    try:
        course_a = cleanup.course("A", tag)
        course_b = cleanup.course("B", tag)
        host = cleanup.user("host")
        player_only = cleanup.user("player")
        cleanup.grant_course(host, course_a["id"], "HOST")
        cleanup.grant_course(host, course_b["id"], "PLAYER")
        cleanup.grant_course(player_only, course_a["id"], "PLAYER")
        game_a = cleanup.game(f"E2E Quiz A {tag}", course_a["id"])
        game_b = cleanup.game(f"E2E Quiz B {tag}", course_b["id"])
        cleanup.grant_game(host, game_a["id"])

        r = api.post(
            "/game/rooms", host.token, json={"game_id": game_a["id"], "course_id": course_a["id"]}
        )
        assert r.status_code == 201, r.text
        room_code, sid = r.json()["room_code"], r.json()["session_id"]
        cleanup.sessions.append(sid)
        r = api.post(
            "/auth/guest",
            json={
                "display_name": f"E2E Guest {tag}",
                "email": f"e2e.guest.{tag}@example.com",
                "room_code": room_code,
            },
        )
        assert r.status_code == 200, r.text
        guest_token = r.json()["access_token"]
        cleanup.users.append(_jwt_sub(guest_token))
        _play_to_completion(api.base_url, host.token, room_code, guest_token)

        yield Env(
            api=api,
            admin=admin_token,
            tag=tag,
            course_a=course_a,
            course_b=course_b,
            host=host,
            player_only=player_only,
            game_a=game_a,
            game_b=game_b,
            completed_sid=sid,
            guest_token=guest_token,
        )
    finally:
        cleanup.run()


@pytest.fixture()
def cleanup(env: Env) -> Iterator[Cleanup]:
    c = Cleanup(env.api, env.admin)
    yield c
    c.run()
