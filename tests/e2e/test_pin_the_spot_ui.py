"""
Browser checks for the pin_the_spot question type (docs/design-pin-the-spot.md §12 → Browser):
authoring in the host editor (file upload → downscaled JPEG data: URL, click to place the
target, pushing sliders, prompt-only edit keeps the image byte for byte), and a play-through
(prompt on the phone, tap, drag, Lock in, partial credit, host boards, game-over recap).

Two independent tests, so one failing can't cascade into the other.
"""

from __future__ import annotations

import base64
import re
import struct
import uuid
import zlib

from playwright.sync_api import Locator, Page, expect

from .conftest import _jwt_sub
from .support import Cleanup, Env


def _png(width: int, height: int, rgb: tuple[int, int, int] = (40, 120, 200)) -> bytes:
    """A solid-colour PNG, built by hand (no imaging dependency)."""

    def chunk(kind: bytes, data: bytes) -> bytes:
        body = kind + data
        return struct.pack(">I", len(data)) + body + struct.pack(">I", zlib.crc32(body) & 0xFFFFFFFF)

    row = b"\x00" + bytes(rgb) * width
    raw = row * height
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(raw))
        + chunk(b"IEND", b"")
    )


def _fit(box: dict, aspect: float) -> tuple[float, float, float, float]:
    """Mirror of fitRect: the drawn image rect inside the canvas's bounding box."""
    w = box["width"]
    h = w * aspect
    if h > box["height"]:
        h = box["height"]
        w = h / aspect
    return box["x"] + (box["width"] - w) / 2, box["y"] + (box["height"] - h) / 2, w, h


def _point(canvas: Locator, aspect: float, fx: float, fy: float) -> tuple[float, float]:
    """Viewport coordinates of image fraction (fx, fy) on a board (scrolled into view)."""
    canvas.scroll_into_view_if_needed()
    box = canvas.bounding_box()
    assert box, "canvas not laid out"
    x, y, w, h = _fit(box, aspect)
    return x + fx * w, y + fy * h


def _host_user(env: Env, cleanup: Cleanup, name: str, title: str) -> tuple:
    host = cleanup.user(name)
    cleanup.grant_course(host, env.course_a["id"], "HOST")
    game = cleanup.game(title, env.course_a["id"], questions=0)
    cleanup.grant_game(host, game["id"])
    return host, game


def _questions(env: Env, token: str, game_id: int) -> list[dict]:
    r = env.api.get(f"/host/games/{game_id}/questions", token)
    assert r.status_code == 200, r.text
    return r.json()


# ---------------------------------------------------------------------------
# 1. Authoring
# ---------------------------------------------------------------------------


def test_pin_the_spot_authoring(env: Env, page_as, cleanup: Cleanup):
    host, game = _host_user(env, cleanup, "pts_author", f"E2E PTS author {uuid.uuid4().hex[:6]}")
    page: Page = page_as(host.token)
    page.goto(f"/host/games/{game['id']}/questions")

    page.get_by_role("button", name="Add Question").click()
    page.locator("select").first.select_option("pin_the_spot")
    page.get_by_placeholder("Question text…").fill("Tap the right half")
    save = page.get_by_role("button", name="Save Question")
    expect(save).to_be_disabled()  # no image yet

    # A 2000×1000 PNG is downscaled to 1280×640 and re-encoded as JPEG.
    page.get_by_test_id("pin-file").set_input_files(
        files=[{"name": "map.png", "mimeType": "image/png", "buffer": _png(2000, 1000)}]
    )
    picker = page.get_by_test_id("pin-target-picker")
    expect(picker).to_have_attribute("data-loaded", "true")
    expect(page.get_by_text("1280 × 640")).to_be_visible()
    expect(save).to_be_disabled()  # ACCURACY needs a target

    x, y = _point(picker, 0.5, 0.75, 0.5)
    page.mouse.click(x, y)
    expect(save).to_be_enabled()

    # Pushing sliders: full-credit radius 0.3 pushes zero-credit up to at least 0.31.
    page.get_by_test_id("pin-r-full").fill("0.3")
    expect(page.get_by_test_id("pin-r-zero")).to_have_value(re.compile(r"^0\.3[1-9]"))
    save.click()
    expect(page.get_by_placeholder("Question text…")).to_have_count(0)  # form closed = saved

    (q,) = _questions(env, host.token, game["id"])
    assert q["type"] == "pin_the_spot"
    assert q["config"]["image_url"].startswith("data:image/jpeg;base64,")
    assert (q["config"]["image_width"], q["config"]["image_height"]) == (1280, 640)
    target = q["answer_data"]["target"]
    assert abs(target["x"] - 0.75) < 0.02 and abs(target["y"] - 0.5) < 0.03
    assert q["answer_data"]["r_full"] == 0.3
    assert q["answer_data"]["r_zero"] >= 0.31

    # Prompt-only edit resends the image and answer key byte for byte.
    page.get_by_role("button", name="Edit").click()
    page.get_by_placeholder("Question text…").fill("Tap the right half (edited)")
    page.get_by_role("button", name="Save Question").click()
    expect(page.get_by_placeholder("Question text…")).to_have_count(0)
    (q2,) = _questions(env, host.token, game["id"])
    assert q2["prompt"] == "Tap the right half (edited)"
    assert q2["config"] == q["config"]
    assert q2["answer_data"] == q["answer_data"]


# ---------------------------------------------------------------------------
# 2. Play-through
# ---------------------------------------------------------------------------

IMAGE = "data:image/png;base64," + base64.b64encode(_png(100, 100)).decode()
Q1 = {"prompt": "Tap the centre (1)", "tap": (0.625, 0.5)}  # d 0.125 → 500, partial
Q2 = {"prompt": "Tap the centre (2)", "tap": (0.51, 0.5)}  # inside r_full → 1000


def _recap_row(page: Page, prompt: str):
    return (
        page.locator("div")
        .filter(has=page.get_by_text(prompt, exact=True))
        .filter(has_text="Your answer")
        .last
    )


def test_pin_the_spot_play_through(env: Env, page_as, cleanup: Cleanup):
    host, game = _host_user(env, cleanup, "pts_host", f"E2E PTS play {uuid.uuid4().hex[:6]}")
    for q in (Q1, Q2):
        r = env.api.post(
            f"/host/games/{game['id']}/questions",
            host.token,
            json={
                "type": "pin_the_spot",
                "grading_type": "ACCURACY",
                "prompt": q["prompt"],
                "config": {"image_url": IMAGE, "image_width": 100, "image_height": 100},
                "answer_data": {"target": {"x": 0.5, "y": 0.5}, "r_full": 0.05, "r_zero": 0.2},
                "points_value": 1000,
                "time_limit_seconds": 120,
            },
        )
        assert r.status_code == 201, r.text

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
            "display_name": "E2E PTS player",
            "email": f"e2e.pts.{uuid.uuid4().hex[:6]}@example.com",
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

    # ── Q1: tap off-target, drag to the half-credit spot ───────────────────────
    expect(player.get_by_test_id("pin-prompt")).to_have_text(Q1["prompt"])
    expect(host_page.get_by_test_id("pin-board-question")).to_be_visible()
    lock = player.get_by_test_id("pin-lock-in")
    expect(lock).to_be_disabled()
    canvas = player.get_by_test_id("pin-canvas")
    expect(canvas).to_have_attribute("data-loaded", "true")  # taps before load are ignored
    sx, sy = _point(canvas, 1.0, 0.2, 0.2)
    tx, ty = _point(canvas, 1.0, *Q1["tap"])
    player.mouse.move(sx, sy)
    player.mouse.down()
    player.mouse.move(tx, ty, steps=8)
    player.mouse.up()
    expect(lock).to_be_enabled()
    lock.click()
    expect(player.get_by_text("Answer locked in!")).to_be_visible()

    host_page.get_by_role("button", name="Show Results").click()
    expect(player.get_by_text("Partially correct", exact=True)).to_be_visible()
    expect(player.get_by_text("+500 pts")).to_be_visible()
    expect(host_page.get_by_test_id("pin-board-results")).to_be_visible()
    expect(host_page.get_by_text("1 / 1 answered")).to_be_visible()

    # ── Q2: a tap inside the full-credit circle, locked in with the keyboard ────
    host_page.get_by_role("button", name="Next Question").click()
    expect(player.get_by_test_id("pin-prompt")).to_have_text(Q2["prompt"])
    canvas = player.get_by_test_id("pin-canvas")
    expect(canvas).to_have_attribute("data-loaded", "true")
    player.mouse.click(*_point(canvas, 1.0, *Q2["tap"]))
    canvas.focus()
    player.keyboard.press("Enter")
    expect(player.get_by_text("Answer locked in!")).to_be_visible()

    host_page.get_by_role("button", name="Show Results").click()
    expect(player.get_by_text("Correct!", exact=True)).to_be_visible()
    expect(player.get_by_text("+1,000 pts")).to_be_visible()

    # ── Game over ─────────────────────────────────────────────────────────────
    host_page.get_by_role("button", name="Show Final Results").click()
    expect(player.get_by_text("Game Over!")).to_be_visible()
    expect(host_page.get_by_test_id("pin-board-gameover")).to_have_count(2)

    row1 = _recap_row(player, Q1["prompt"])
    expect(row1).to_contain_text("◐")
    expect(row1).to_contain_text("Pin placed")
    row2 = _recap_row(player, Q2["prompt"])
    expect(row2).to_contain_text("✓")
