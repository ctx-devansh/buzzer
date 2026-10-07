"""
T9 evidence: the key-screen screenshots in both themes, plus a rendered-contrast check
(docs/design-better-ui.md §4.6 and §4.10).

Deliberately not named test_*.py, so a normal `pytest` run doesn't collect it. Run it explicitly,
against the Docker stack, after a build:

    npm run build && pytest tests/e2e/capture_ui_screens.py

It writes docs/ui/after/<theme>/<app>/<NN-name>.png (the 41-screen table in the design doc) and
docs/ui/after/axe-report.txt. At every shot it runs axe-core's color-contrast and
link-in-text-block rules; violations are collected and the test fails once, at the end, with one
report, so a violation never leaves a half-played game behind.

Order: a full game in light, a full game in dark (the in-game screens), then the management and
admin screens in both themes, so both themes show identical data (two completed sessions).
"""

from __future__ import annotations

import json
import re
import uuid
from pathlib import Path

from axe_playwright_python.sync_playwright import Axe
from playwright.sync_api import Page, expect

from .conftest import _jwt_sub
from .support import REPO_ROOT, Cleanup, Env

OUT = REPO_ROOT / "docs" / "ui" / "after"
BUNDLE = Path(__file__).parent / "fixtures" / "ui_capture_showcase.json"
THEMES = ("light", "dark")

PHONE = {"viewport": {"width": 390, "height": 844}, "device_scale_factor": 2}
PROJECTOR = {"viewport": {"width": 1920, "height": 1080}}
DESKTOP = {"viewport": {"width": 1440, "height": 900}}

AXE_RULES = {"runOnly": {"type": "rule", "values": ["color-contrast", "link-in-text-block"]}}
_axe = Axe()
_violations: list[str] = []


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _open(page_as, token: str | None, theme: str, size: dict) -> Page:
    page = page_as(token, color_scheme=theme, **size)
    page.context.add_init_script(f"window.localStorage.setItem('buzzer-theme', '{theme}');")
    return page


def _settle(page: Page) -> None:
    """Fonts loaded, images decoded, canvases drawn, transitions done."""
    page.evaluate("document.fonts.ready")
    page.wait_for_function("[...document.images].every(img => img.complete)")
    page.wait_for_function(
        "[...document.querySelectorAll('canvas[data-loaded]')].every(c => c.dataset.loaded === 'true')"
    )
    page.wait_for_timeout(700)  # bar/width transitions are 500-700 ms


def _shot(page: Page, theme: str, name: str) -> None:
    _settle(page)
    path = OUT / theme / f"{name}.png"
    path.parent.mkdir(parents=True, exist_ok=True)
    page.screenshot(path=str(path))
    for v in _axe.run(page, options=AXE_RULES).response["violations"]:
        for node in v["nodes"]:
            detail = node.get("any") or node.get("all") or [{}]
            ratio = (detail[0].get("data") or {}).get("contrastRatio", "")
            _violations.append(f"{theme}/{name}: {v['id']} {ratio} {', '.join(map(str, node['target']))}")


def _guest(env: Env, cleanup: Cleanup, room: str, name: str) -> str:
    r = env.api.post(
        "/auth/guest",
        json={"display_name": name, "email": f"e2e.capture.{uuid.uuid4().hex[:6]}@example.com", "room_code": room},
    )
    assert r.status_code == 200, r.text
    token = r.json()["access_token"]
    cleanup.users.append(_jwt_sub(token))
    return token


# The backend emits a phase's events before it saves the new phase to Redis
# (backend/app/websocket/gateway.py, host_advance), so an action within milliseconds of an event
# can be read against the old phase: a second host_advance re-shows results and the game stalls, or
# an answer is rejected. People never act that fast; this script does, so it waits a moment after
# each transition. (A known backend race, outside T9; to be fixed on its own branch.)
SERVER_SETTLE_MS = 800


def _wait_locked_in(player: Page) -> None:
    expect(player.get_by_text("Answer locked in!")).to_be_visible()


def _tap(player: Page, name: str) -> None:
    player.get_by_role("button", name=re.compile(re.escape(name))).click()


def _order(player: Page, items: list[str], correct: list[int]) -> None:
    """Pick-and-place the put-in-order rows into `correct` (indices into `items`)."""
    current = list(range(len(items)))
    for pos, item in enumerate(correct):
        at = current.index(item)
        if at != pos:
            player.get_by_test_id(f"pio-row-{at}").click()
            player.get_by_test_id(f"pio-row-{pos}").click()
            current.insert(pos, current.pop(at))


def _pin(player: Page, x: float, y: float) -> None:
    canvas = player.locator("canvas[data-loaded='true']")
    box = canvas.bounding_box()
    assert box
    canvas.click(position={"x": box["width"] * x, "y": box["height"] * y})


# ---------------------------------------------------------------------------
# One full game per theme: screens 01-19
# ---------------------------------------------------------------------------


def _play(env: Env, cleanup: Cleanup, page_as, host_token: str, theme: str, bundle: dict) -> None:
    q = bundle["questions"]
    host = _open(page_as, host_token, theme, PROJECTOR)
    host.goto("/host/home")
    host.get_by_role("button", name="Create Room").click()
    expect(host).to_have_url(re.compile(r"/host/game/[A-Z0-9]+/lobby$"))
    room = re.search(r"/host/game/([A-Z0-9]+)/lobby", host.url).group(1)
    r = env.api.get(f"/game/rooms/{room}", host_token)
    assert r.status_code == 200, r.text
    cleanup.sessions.append(r.json()["session_id"])

    # 01-02: a signed-out phone joining
    visitor = _open(page_as, None, theme, PHONE)
    visitor.goto("/player/join")
    _shot(visitor, theme, "player/01-join")
    visitor.goto(f"/player/name/{room}")
    expect(visitor.get_by_placeholder("Your name")).to_be_visible()
    _shot(visitor, theme, "player/02-name-guest")

    alex, sam, jordan = (
        _open(page_as, _guest(env, cleanup, room, name), theme, PHONE) for name in ("Alex", "Sam", "Jordan")
    )
    for p in (alex, sam, jordan):
        p.goto(f"/player/game/{room}/lobby")
    expect(host.get_by_text("3 players joined")).to_be_visible()
    _shot(alex, theme, "player/03-lobby")
    _shot(host, theme, "host/14-lobby")
    host.get_by_role("button", name="Start Game").click()
    expect(host.get_by_role("button", name="Show Results")).to_be_visible()
    host.wait_for_timeout(SERVER_SETTLE_MS)

    def reveal() -> None:
        host.get_by_role("button", name="Show Results").click()
        expect(host.get_by_role("heading", name=re.compile(r"Results$"))).to_be_visible()
        host.wait_for_timeout(SERVER_SETTLE_MS)

    def advance(last: bool = False) -> None:
        host.get_by_role("button", name="Show Final Results" if last else "Next Question").click()
        if not last:
            expect(host.get_by_role("button", name="Show Results")).to_be_visible()
            host.wait_for_timeout(SERVER_SETTLE_MS)

    # Q1 multiple choice with option images: Alex right, Sam and Jordan wrong
    expect(alex.get_by_test_id("option-grid")).to_be_visible()
    _shot(alex, theme, "player/04-question-mc-images")
    _tap(alex, q[0]["config"]["options"][3])
    _wait_locked_in(alex)
    _shot(alex, theme, "player/10-feedback")
    _tap(sam, q[0]["config"]["options"][0])
    _tap(jordan, q[0]["config"]["options"][1])
    _wait_locked_in(sam)
    _wait_locked_in(jordan)
    reveal()
    expect(alex.get_by_text("Correct!", exact=True)).to_be_visible()
    expect(sam.get_by_text("Incorrect", exact=True)).to_be_visible()
    _shot(host, theme, "host/17-results-mc")
    _shot(alex, theme, "player/11-results-correct")
    _shot(sam, theme, "player/12-results-incorrect")
    advance()

    # Q2 true/false with a prompt image (shown on the projector only)
    expect(host.get_by_test_id("prompt-image")).to_be_visible()
    expect(alex.get_by_role("button", name="True")).to_be_visible()
    _shot(host, theme, "host/15-question-prompt-image")
    _shot(alex, theme, "player/05-question-true-false")
    for p, answer in ((alex, "False"), (sam, "True"), (jordan, "False")):
        p.get_by_role("button", name=answer, exact=True).click()
        _wait_locked_in(p)
    reveal()
    advance()

    # Q3 fill in the blank
    expect(alex.get_by_placeholder("Type your answer…")).to_be_visible()
    _shot(alex, theme, "player/06-question-fill-blank")
    for p, answer in ((alex, "black"), (sam, "white"), (jordan, "black")):
        p.get_by_placeholder("Type your answer…").fill(answer)
        p.get_by_role("button", name="Submit").click()
        _wait_locked_in(p)
    reveal()
    _shot(host, theme, "host/36-results-fill-blank")
    advance()

    # Q4 multi-select: the shot shows one selected row
    options = q[3]["config"]["options"]
    _tap(alex, options[0])
    _shot(alex, theme, "player/07-question-multi-select")
    for name in (options[2], options[4]):
        _tap(alex, name)
    _tap(sam, options[1])
    _tap(jordan, options[0])
    for p in (alex, sam, jordan):
        p.get_by_role("button", name=re.compile(r"^Submit")).click()
        _wait_locked_in(p)
    reveal()
    advance()

    # Q5 put in order
    expect(alex.get_by_test_id("pio-row-0")).to_be_visible()
    _shot(alex, theme, "player/08-question-put-in-order")
    _shot(host, theme, "host/34-question-put-in-order")
    _order(alex, q[4]["config"]["items"], q[4]["answer_data"]["correct_order"])
    for p in (alex, sam, jordan):
        p.get_by_test_id("pio-lock-in").click()
        _wait_locked_in(p)
    reveal()
    expect(alex.locator("p").filter(has_text="Correct order:")).to_be_visible()
    _shot(host, theme, "host/35-results-put-in-order")
    _shot(alex, theme, "player/31-results-put-in-order")
    advance()

    # Q6 Pin the Spot
    target = q[5]["answer_data"]["target"]
    expect(host.get_by_test_id("pin-board-question")).to_be_visible()
    _shot(host, theme, "host/16-question-pin")
    expect(alex.locator("canvas[data-loaded='true']")).to_be_visible()
    _pin(alex, target["x"], target["y"])
    _shot(alex, theme, "player/09-question-pin-placed")
    _pin(sam, 0.12, 0.2)
    _pin(jordan, target["x"] + 0.05, target["y"] + 0.04)
    for p in (alex, sam, jordan):
        p.get_by_test_id("pin-lock-in").click()
        _wait_locked_in(p)
    reveal()
    _shot(host, theme, "host/18-results-pin")
    expect(alex.get_by_text("Correct!", exact=True)).to_be_visible()
    _shot(alex, theme, "player/32-results-pin")
    advance()

    # Q7 multiple choice, completeness grading. First the locked state, on both screens.
    host.get_by_role("button", name="Lock Question").click()
    expect(host.get_by_role("button", name="Unlock Question")).to_be_visible()
    expect(sam.get_by_text("Answers locked — waiting for results…")).to_be_visible()
    host.wait_for_timeout(SERVER_SETTLE_MS)
    _shot(host, theme, "host/37-question-locked")
    _shot(sam, theme, "player/33-question-locked")
    host.get_by_role("button", name="Unlock Question").click()
    expect(host.get_by_role("button", name="Lock Question")).to_be_visible()
    expect(sam.get_by_text("Answers locked — waiting for results…")).to_have_count(0)
    host.wait_for_timeout(SERVER_SETTLE_MS)
    for p, i in ((alex, 1), (sam, 2), (jordan, 1)):
        _tap(p, q[6]["config"]["options"][i])
        _wait_locked_in(p)
    reveal()
    advance(last=True)
    expect(host.get_by_role("heading", name="Game Over!")).to_be_visible()
    expect(alex.get_by_role("heading", name="Game Over!")).to_be_visible()
    _shot(host, theme, "host/19-game-over")
    _shot(alex, theme, "player/13-game-over")
    for p in (host, visitor, alex, sam, jordan):
        p.context.close()


# ---------------------------------------------------------------------------
# Management and admin screens: 20-30
# ---------------------------------------------------------------------------


def _manage(env: Env, page_as, host_token: str, host_id: str, course_id: int, game_id: int, theme: str) -> None:
    login = _open(page_as, None, theme, DESKTOP)
    login.goto("/host/login")
    _shot(login, theme, "host/20-login")
    login.context.close()

    page = _open(page_as, host_token, theme, DESKTOP)
    for name, path, ready in (
        ("host/21-home", "/host/home", "Create Game Room"),
        ("host/22-games", "/host/games", "Games"),
        ("host/24-image-library", f"/host/courses/{course_id}/images", "Images"),
        ("host/26-roster", f"/host/courses/{course_id}/roster", "Course Roster"),
        ("host/38-courses", "/host/courses", "Courses"),
        ("host/27-sessions", "/host/sessions", "Sessions"),
    ):
        page.goto(path)
        expect(page.get_by_role("heading", name=ready, exact=True)).to_be_visible()
        _shot(page, theme, name)

    page.goto(f"/host/games/{game_id}/questions")
    page.get_by_role("button", name="Edit").nth(5).click()  # Q6, Pin the Spot
    expect(page.get_by_test_id("pin-editor")).to_be_visible()
    page.get_by_test_id("pin-editor").scroll_into_view_if_needed()
    _shot(page, theme, "host/23-editor-pin")
    page.get_by_role("button", name="Choose from library").click()
    expect(page.get_by_role("dialog", name="Choose an image")).to_be_visible()
    _shot(page, theme, "host/25-image-picker")
    page.context.close()

    admin_login = _open(page_as, None, theme, DESKTOP)
    admin_login.goto("/admin/login")
    expect(admin_login.get_by_role("heading", name="Admin Login")).to_be_visible()
    _shot(admin_login, theme, "admin/39-login")
    admin_login.context.close()

    admin = _open(page_as, env.admin, theme, DESKTOP)
    for name, path, ready in (
        ("admin/28-users", "/admin/users", "Users"),
        ("admin/29-user-detail", f"/admin/users/{host_id}", "Course Access"),
        ("admin/30-sessions", "/admin/sessions", "Sessions"),
        ("admin/40-courses", "/admin/courses", "Courses"),
        ("admin/41-guests", "/admin/guests", "Guest Users"),
    ):
        admin.goto(path)
        expect(admin.get_by_role("heading", name=ready, exact=True)).to_be_visible()
        _shot(admin, theme, name)
    admin.context.close()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def test_capture_ui_screens(env: Env, page_as, cleanup: Cleanup):
    tag = uuid.uuid4().hex[:6]
    course = cleanup.course("UI capture", tag)
    host = cleanup.user("capture_host")
    cleanup.grant_course(host, course["id"], "HOST")

    # The showcase game: every question type, option images, a prompt image and a Pin the Spot map.
    # Long time limits, so nothing expires while shots are taken.
    bundle = json.loads(BUNDLE.read_text())
    for question in bundle["questions"]:
        question["time_limit_seconds"] = 300  # the backend maximum
    r = env.api.post(
        "/host/games/import",
        host.token,
        files={"file": ("showcase.json", json.dumps(bundle).encode(), "application/json")},
        data={"course_id": str(course["id"])},
    )
    assert r.status_code == 201, r.text
    game_id = r.json()["game_id"]
    cleanup.games.append(game_id)

    # Roster data for screen 26: six students, one deactivated so the "Inactive" chip shows.
    rows = [
        {"netid": f"cap{tag}{i}", "full_name": name, "email": f"cap{tag}{i}@example.edu"}
        for i, name in enumerate(["Ada Byron", "Alan Turing", "Grace Hopper", "Edsger Dijkstra", "Barbara Liskov", "Ken Thompson"])
    ]
    r = env.api.post(f"/host/courses/{course['id']}/roster/import", host.token, json={"rows": rows})
    assert r.status_code == 200, r.text
    roster = env.api.get(f"/host/courses/{course['id']}/roster", host.token).json()
    r = env.api.call("PATCH", f"/host/courses/{course['id']}/roster/{roster[-1]['id']}", host.token, json={"is_active": False})
    assert r.status_code == 200, r.text

    try:
        for theme in THEMES:
            _play(env, cleanup, page_as, host.token, theme, bundle)
        for theme in THEMES:
            _manage(env, page_as, host.token, host.id, course["id"], game_id, theme)
    finally:
        # Courses can't be deleted; remove the imported game first, then its now-unused images.
        cleanup.run()
        for image in env.api.get(f"/host/courses/{course['id']}/images", env.admin).json():
            env.api.delete(f"/host/courses/{course['id']}/images/{image['id']}", env.admin)

    report = "\n".join(_violations) or "No color-contrast or link-in-text-block violations."
    (OUT / "axe-report.txt").write_text(report + "\n")
    assert not _violations, f"{len(_violations)} axe violations:\n{report}"
