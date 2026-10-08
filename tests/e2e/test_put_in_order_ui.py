"""
Browser checks for the put_in_order question type (docs/design-put-in-order.md → Tests →
E2E): authoring in the host editor (scramble on save, no reshuffle on a prompt-only
edit) as a HOST and as an ADMIN arriving from the admin app, and a play-through with
pick-and-place on the player page, the host bar chart, partial credit, and the game-over recap.

Independent tests, so one failing can't cascade into the other.
"""

from __future__ import annotations

import re
import uuid

from playwright.sync_api import Page, expect

from .conftest import _jwt_sub
from .support import Cleanup, Env

AUTHORED = ["A", "B", "C", "D"]
CORRECT_TEXT = "A → B → C → D"


def taps_to_reach(start: list[int], target: list[int]) -> list[tuple[int, int]]:
    """
    Pick-and-place tap pairs (pick row k, then tap row pos) that turn `start` into
    `target`, using the player page's insert semantics. Filling positions left to right
    never disturbs an earlier position, so this takes at most n-1 pairs.
    """
    order = list(start)
    taps = []
    for pos, item in enumerate(target):
        k = order.index(item)
        if k != pos:
            taps.append((k, pos))
            moved = order.pop(k)
            order.insert(pos, moved)
    assert order == target
    return taps


def _host_user(env: Env, cleanup: Cleanup, name: str, title: str) -> tuple:
    """A fresh host: HOST on course A only, granted exactly one new (question-less) game."""
    host = cleanup.user(name)
    cleanup.grant_course(host, env.course_a["id"], "HOST")
    game = cleanup.game(title, env.course_a["id"], questions=0)
    cleanup.grant_game(host, game["id"])
    return host, game


def _game_row(page: Page, title: str):
    """The innermost card holding a game's title and its Questions button."""
    return (
        page.locator("div")
        .filter(has=page.get_by_text(title, exact=True))
        .filter(has=page.get_by_role("button", name="Questions"))
        .last
    )


def _questions(env: Env, token: str, game_id: int) -> list[dict]:
    r = env.api.get(f"/host/games/{game_id}/questions", token)
    assert r.status_code == 200, r.text
    return r.json()


# ---------------------------------------------------------------------------
# 1. Authoring
# ---------------------------------------------------------------------------


def _author_put_in_order(env: Env, page: Page, token: str, game_id: int) -> None:
    """Create, reopen and edit a put_in_order question on an open question editor page."""
    page.get_by_role("button", name="Add Question").click()
    page.locator("select").first.select_option("put_in_order")
    page.get_by_placeholder("Question text…").fill("Order the letters")
    page.get_by_test_id("pio-add-row").click()  # the form starts with 3 rows
    for i, text in enumerate(AUTHORED):
        page.get_by_test_id(f"pio-item-{i}").fill(text)
    page.get_by_role("button", name="Save Question").click()
    expect(page.get_by_placeholder("Question text…")).to_have_count(0)  # form closed = saved
    expect(page.get_by_role("button", name="Edit")).to_have_count(1)

    (q,) = _questions(env, token, game_id)
    items, correct_order = q["config"]["items"], q["answer_data"]["correct_order"]
    assert sorted(items) == AUTHORED
    assert items != AUTHORED, "display order must be scrambled"
    assert [items[i] for i in correct_order] == AUTHORED

    # Reopen: the editor shows the authored (correct) order, not the scramble.
    page.get_by_role("button", name="Edit").click()
    for i, text in enumerate(AUTHORED):
        expect(page.get_by_test_id(f"pio-item-{i}")).to_have_value(text)

    # Prompt-only edit: the stored scramble is resent verbatim.
    page.get_by_placeholder("Question text…").fill("Order the letters (edited)")
    page.get_by_role("button", name="Save Question").click()
    expect(page.get_by_placeholder("Question text…")).to_have_count(0)  # form closed = saved
    expect(page.get_by_text("Order the letters (edited)")).to_be_visible()

    (q2,) = _questions(env, token, game_id)
    assert q2["prompt"] == "Order the letters (edited)"
    assert q2["config"]["items"] == items
    assert q2["answer_data"]["correct_order"] == correct_order


def test_put_in_order_authoring(env: Env, page_as, cleanup: Cleanup):
    host, game = _host_user(env, cleanup, "pio_author", f"E2E PIO author {uuid.uuid4().hex[:6]}")
    page: Page = page_as(host.token)
    page.goto(f"/host/games/{game['id']}/questions")
    _author_put_in_order(env, page, host.token, game["id"])


def test_put_in_order_authoring_as_admin(
    env: Env, page_as, cleanup: Cleanup, admin_credentials: tuple[str, str]
):
    """
    An ADMIN signs in through the admin app and authors put_in_order from there: its "Games"
    link opens the host app's games list, where authoring for every type lives, and the admin
    needs no grant. The page starts signed out (no seeded token), so reaching /host/ signed in
    proves the shared-origin token carry-over.
    """
    title = f"E2E PIO admin {uuid.uuid4().hex[:6]}"
    game = cleanup.game(title, env.course_a["id"], questions=0)  # no course or game grant
    username, password = admin_credentials
    page: Page = page_as(None)
    page.goto("/admin/login")
    page.get_by_placeholder("Username").fill(username)
    page.get_by_placeholder("Password").fill(password)
    page.get_by_role("button", name="Sign In").click()
    expect(page).to_have_url(re.compile(r"/admin/users$"))

    page.get_by_role("link", name="Games").click()
    expect(page).to_have_url(re.compile(r"/host/games$"))
    # The URL alone can match for a moment before the host app's RequireAuth redirects to
    # /host/login. The shell's "Sign out" only renders past RequireAuth, so this proves the
    # host app found the token the admin app's login form stored.
    expect(page.get_by_role("navigation").get_by_text("Sign out", exact=True)).to_be_visible()
    _game_row(page, title).get_by_role("button", name="Questions").click()  # all games listed
    expect(page).to_have_url(re.compile(rf"/host/games/{game['id']}/questions$"))
    _author_put_in_order(env, page, env.admin, game["id"])


# ---------------------------------------------------------------------------
# 2–4. Play-through
# ---------------------------------------------------------------------------

Q1 = {
    "prompt": "Order the letters (1)",
    "items": ["B", "D", "A", "C"],
    "correct_order": [2, 0, 3, 1],
}
Q2 = {
    "prompt": "Order the letters (2)",
    "items": ["C", "A", "D", "B"],
    "correct_order": [1, 3, 0, 2],
}


def _apply_taps(page: Page, target: list[int]) -> None:
    for k, pos in taps_to_reach(list(range(4)), target):
        page.get_by_test_id(f"pio-row-{k}").click()
        page.get_by_test_id(f"pio-row-{pos}").click()


def _recap_row(page: Page, prompt: str):
    """The innermost recap card holding this prompt (the rows differ only by prompt)."""
    return (
        page.locator("div")
        .filter(has=page.get_by_text(prompt, exact=True))
        .filter(has_text="Your answer")
        .last
    )


def test_put_in_order_play_through(env: Env, page_as, cleanup: Cleanup):
    host, game = _host_user(env, cleanup, "pio_host", f"E2E PIO play {uuid.uuid4().hex[:6]}")
    for q in (Q1, Q2):
        r = env.api.post(
            f"/host/games/{game['id']}/questions",
            host.token,
            json={
                "type": "put_in_order",
                "grading_type": "ACCURACY",
                "prompt": q["prompt"],
                "config": {"items": q["items"]},
                "answer_data": {"correct_order": q["correct_order"]},
                "points_value": 1,
                "time_limit_seconds": 120,
            },
        )
        assert r.status_code == 201, r.text

    # ── Room: the host's only course and game are auto-selected ────────────────
    host_page = page_as(host.token)
    host_page.goto("/host/home")
    expect(host_page.locator("select").nth(1)).to_have_value(str(game["id"]))
    host_page.get_by_role("button", name="Create Room").click()
    expect(host_page).to_have_url(re.compile(r"/host/game/[A-Z0-9]+/lobby$"))
    room_code = re.search(r"/host/game/([A-Z0-9]+)/lobby", host_page.url).group(1)
    r = env.api.get(f"/game/rooms/{room_code}", host.token)
    assert r.status_code == 200, r.text
    cleanup.sessions.append(r.json()["session_id"])

    r = env.api.post(
        "/auth/guest",
        json={
            "display_name": "E2E PIO player",
            "email": f"e2e.pio.{uuid.uuid4().hex[:6]}@example.com",
            "room_code": room_code,
        },
    )
    assert r.status_code == 200, r.text
    guest_token = r.json()["access_token"]
    cleanup.users.append(_jwt_sub(guest_token))

    player = page_as(guest_token)
    player.goto(f"/player/game/{room_code}/lobby")
    start = host_page.get_by_role("button", name="Start Game")
    expect(start).to_be_enabled()
    start.click()

    # ── Q1: perfect order ─────────────────────────────────────────────────────
    rows = [player.get_by_test_id(f"pio-row-{p}") for p in range(4)]
    for p, row in enumerate(rows):
        expect(row).to_contain_text(Q1["items"][p])

    # Tapping the same row twice cancels the pick.
    rows[0].click()
    expect(rows[0]).to_have_attribute("aria-pressed", "true")
    rows[0].click()
    expect(rows[0]).to_have_attribute("aria-pressed", "false")

    _apply_taps(player, Q1["correct_order"])
    player.get_by_test_id("pio-lock-in").click()
    # Wait for the server's answer_received before revealing, or the two race.
    expect(player.get_by_text("Answer locked in!")).to_be_visible()

    host_page.get_by_role("button", name="Show Results").click()
    expect(player.get_by_text("Correct!", exact=True)).to_be_visible()
    expect(player.get_by_text("+1 pts")).to_be_visible()
    expect(player.locator("p").filter(has_text="Correct order:")).to_have_text(
        f"Correct order: {CORRECT_TEXT}"
    )

    expect(host_page.get_by_text("Players who placed each item correctly")).to_be_visible()
    for p in range(4):
        expect(host_page.get_by_test_id(f"pio-bar-{p}")).to_be_visible()
        expect(host_page.get_by_test_id(f"pio-bar-{p}-count")).to_have_text("1")

    # ── Q2: one adjacent swap (B, A, C, D) → 5 of 6 pairs → 0.83 ───────────────
    host_page.get_by_role("button", name="Next Question").click()
    expect(player.get_by_test_id("pio-row-0")).to_contain_text(Q2["items"][0])
    _apply_taps(player, [3, 1, 0, 2])
    player.get_by_test_id("pio-lock-in").click()
    expect(player.get_by_text("Answer locked in!")).to_be_visible()

    host_page.get_by_role("button", name="Show Results").click()
    expect(player.get_by_text("Partially correct", exact=True)).to_be_visible()
    expect(player.get_by_text("+0.83 pts")).to_be_visible()
    expect(player.locator("p").filter(has_text="Correct order:")).to_have_text(
        f"Correct order: {CORRECT_TEXT}"
    )

    # ── Game over recap ───────────────────────────────────────────────────────
    host_page.get_by_role("button", name="Show Final Results").click()
    expect(player.get_by_text("Game Over!")).to_be_visible()

    row1 = _recap_row(player, Q1["prompt"])
    expect(row1).to_contain_text("✓")
    expect(row1).to_contain_text(CORRECT_TEXT)
    expect(row1).not_to_contain_text("Correct:")

    row2 = _recap_row(player, Q2["prompt"])
    expect(row2).to_contain_text("◐")
    expect(row2).to_contain_text("B → A → C → D")
    expect(row2).to_contain_text(f"Correct: {CORRECT_TEXT}")
