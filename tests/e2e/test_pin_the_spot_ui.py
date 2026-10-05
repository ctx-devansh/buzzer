"""
Browser checks for the pin_the_spot question type (docs/design-pin-the-spot.md): authoring
in the host editor (file upload, click to place the target, prompt-only edits keep the
image), and a play-through with a tap on the player canvas, the host's question and
results boards, partial credit, and the game-over recap.

Two independent tests, so one failing can't cascade into the other.
"""

from __future__ import annotations

import base64
import re
import struct
import uuid
import zlib

import pytest
from playwright.sync_api import Page, expect

from .conftest import _jwt_sub
from .support import Cleanup, Env


def _png(width: int, height: int) -> bytes:
    """A solid-colour RGB PNG, built by hand so the test needs no imaging library."""

    def chunk(kind: bytes, data: bytes) -> bytes:
        body = kind + data
        return struct.pack(">I", len(data)) + body + struct.pack(">I", zlib.crc32(body))

    row = b"\x00" + b"\x40\x80\xc0" * width
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(row * height))
        + chunk(b"IEND", b"")
    )


def _host_user(env: Env, cleanup: Cleanup, name: str, title: str) -> tuple:
    """A fresh host: HOST on course A only, granted exactly one new (question-less) game."""
    host = cleanup.user(name)
    cleanup.grant_course(host, env.course_a["id"], "HOST")
    game = cleanup.game(title, env.course_a["id"], questions=0)
    cleanup.grant_game(host, game["id"])
    return host, game


def _questions(env: Env, token: str, game_id: int) -> list[dict]:
    r = env.api.get(f"/host/games/{game_id}/questions", token)
    assert r.status_code == 200, r.text
    return r.json()


def _click_at(page: Page, test_id: str, fx: float, fy: float) -> None:
    """Click a canvas at a fraction of its size."""
    canvas = page.get_by_test_id(test_id)
    expect(canvas).to_be_visible()
    box = canvas.bounding_box()
    assert box and box["width"] > 0, box
    canvas.click(position={"x": box["width"] * fx, "y": box["height"] * fy})


# ---------------------------------------------------------------------------
# 1. Authoring
# ---------------------------------------------------------------------------


def test_pin_the_spot_authoring(env: Env, page_as, cleanup: Cleanup):
    host, game = _host_user(env, cleanup, "pts_author", f"E2E PTS author {uuid.uuid4().hex[:6]}")
    page: Page = page_as(host.token)
    page.goto(f"/host/games/{game['id']}/questions")

    page.get_by_role("button", name="Add Question").click()
    page.locator("select").first.select_option("pin_the_spot")
    page.get_by_placeholder("Question text…").fill("Tap the spot")
    save = page.get_by_role("button", name="Save Question")
    expect(save).to_be_disabled()  # no image yet

    page.get_by_test_id("pin-file").set_input_files(
        {"name": "map.png", "mimeType": "image/png", "buffer": _png(400, 200)}
    )
    expect(page.get_by_text("400 × 200 px")).to_be_visible()
    expect(save).to_be_disabled()  # ACCURACY still needs a target

    _click_at(page, "pin-editor-board", 0.75, 0.25)
    expect(page.get_by_test_id("pin-r-full")).to_be_visible()
    expect(save).to_be_enabled()
    save.click()
    expect(page.get_by_placeholder("Question text…")).to_have_count(0)  # form closed = saved

    (q,) = _questions(env, host.token, game["id"])
    assert q["type"] == "pin_the_spot"
    assert q["config"]["image_url"].startswith("data:image/jpeg;base64,")
    assert (q["config"]["image_width"], q["config"]["image_height"]) == (400, 200)
    target = q["answer_data"]["target"]
    assert target["x"] == pytest.approx(0.75, abs=0.02)
    assert target["y"] == pytest.approx(0.25, abs=0.02)
    assert (q["answer_data"]["r_full"], q["answer_data"]["r_zero"]) == (0.05, 0.2)
    expect(page.get_by_text(re.compile(r"Target \(7[4-6]%, 2[4-6]%\)"))).to_be_visible()

    # Prompt-only edit: the image and target are resent unchanged.
    page.get_by_role("button", name="Edit").click()
    page.get_by_placeholder("Question text…").fill("Tap the spot (edited)")
    page.get_by_role("button", name="Save Question").click()
    expect(page.get_by_placeholder("Question text…")).to_have_count(0)

    (q2,) = _questions(env, host.token, game["id"])
    assert q2["prompt"] == "Tap the spot (edited)"
    assert q2["config"] == q["config"]
    assert q2["answer_data"] == q["answer_data"]


# ---------------------------------------------------------------------------
# 2. Play-through
# ---------------------------------------------------------------------------

PROMPT = "Tap the middle of the picture"


def test_pin_the_spot_play_through(env: Env, page_as, cleanup: Cleanup):
    host, game = _host_user(env, cleanup, "pts_host", f"E2E PTS play {uuid.uuid4().hex[:6]}")
    image_url = "data:image/png;base64," + base64.b64encode(_png(400, 200)).decode()
    r = env.api.post(
        f"/host/games/{game['id']}/questions",
        host.token,
        json={
            "type": "pin_the_spot",
            "grading_type": "ACCURACY",
            "prompt": PROMPT,
            "config": {"image_url": image_url, "image_width": 400, "image_height": 200},
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

    # ── Question: the host shows the image, the player taps ──────────────────────
    expect(host_page.get_by_test_id("host-pin-question")).to_be_visible()
    expect(player.get_by_text(PROMPT)).to_be_visible()
    lock_in = player.get_by_test_id("pin-lock-in")
    expect(lock_in).to_be_disabled()
    expect(player.get_by_text("Tap the picture to drop a pin")).to_be_visible()

    _click_at(player, "pin-canvas", 0.1, 0.1)  # first tap…
    expect(player.get_by_text("Drag or tap again to move your pin")).to_be_visible()
    # …then move it: a quarter of the height below the target is 0.125 image widths on
    # this 2:1 image, half way between the circles → about 500 of 1000.
    _click_at(player, "pin-canvas", 0.5, 0.75)
    lock_in.click()
    expect(player.get_by_text("Answer locked in!")).to_be_visible()
    expect(host_page.get_by_text("1 / 1 answered")).to_be_visible()

    # ── Results ───────────────────────────────────────────────────────────────
    host_page.get_by_role("button", name="Show Results").click()
    expect(player.get_by_text("Partially correct", exact=True)).to_be_visible()
    points_text = player.get_by_text(re.compile(r"^\+[\d,.]+ pts$")).inner_text()
    points = float(points_text.strip("+ pts").replace(",", ""))
    assert 450 <= points <= 550, points_text
    expect(player.get_by_test_id("pin-canvas")).to_be_visible()  # your pin over the target

    expect(host_page.get_by_test_id("host-pin-results")).to_be_visible()
    expect(host_page.get_by_text(re.compile("Every tap, with the full-credit"))).to_be_visible()

    # ── Game over recap ───────────────────────────────────────────────────────
    host_page.get_by_role("button", name="Show Final Results").click()
    expect(player.get_by_text("Game Over!")).to_be_visible()
    row = (
        player.locator("div")
        .filter(has=player.get_by_text(PROMPT, exact=True))
        .filter(has_text="Your answer")
        .last
    )
    expect(row).to_contain_text("◐")
    expect(row).to_contain_text("Pin placed")
    expect(host_page.get_by_text("Pin the Spot", exact=False).first).to_be_visible()
