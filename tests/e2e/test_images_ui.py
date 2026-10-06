"""
Browser checks for T8 image support (docs/design-image-support.md §8): upload on the
course library page, author a multiple-choice question with a prompt image and image
options, play it (the host shows the prompt image, the phone shows image tiles but not the
prompt image, results show thumbnails), then the library's guards: a used image can't be
deleted, and replacing an image changes what the host shows after a reload (within one
document a browser may reuse an image it already loaded, design §4.3).

Two independent tests, so one failing can't cascade into the other.
"""

from __future__ import annotations

import re
import struct
import uuid
import zlib

from playwright.sync_api import Page, expect

from .conftest import _jwt_sub
from .support import Cleanup, Env


def _png(width: int, height: int, rgb: bytes = b"\x40\x80\xc0") -> bytes:
    """A solid-colour RGB PNG, built by hand so the test needs no imaging library."""

    def chunk(kind: bytes, data: bytes) -> bytes:
        body = kind + data
        return struct.pack(">I", len(data)) + body + struct.pack(">I", zlib.crc32(body))

    row = b"\x00" + rgb * width
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


def _library(env: Env, token: str) -> list[dict]:
    r = env.api.get(f"/host/courses/{env.course_a['id']}/images", token)
    assert r.status_code == 200, r.text
    return r.json()


def _upload(env: Env, token: str, name: str, data: bytes) -> dict:
    r = env.api.post(
        f"/host/courses/{env.course_a['id']}/images",
        token,
        files={"file": (name, data, "image/png")},
    )
    assert r.status_code == 201, r.text
    return r.json()


def _delete_images(env: Env, cleanup: Cleanup, ids: list[str]) -> None:
    """Courses can't be deleted, so don't let test images pile up in course A: delete the
    games first (cleanup.run is idempotent; the fixture's second run finds only 404s), then
    the now-unused images."""
    cleanup.run()
    for image_id in ids:
        r = env.api.delete(f"/host/courses/{env.course_a['id']}/images/{image_id}", env.admin)
        assert r.status_code in (204, 404), r.text


def _pick(page: Page, filename: str) -> None:
    dialog = page.get_by_role("dialog", name="Choose an image")
    expect(dialog).to_be_visible()
    dialog.get_by_test_id("picker-image").filter(has_text=filename).click()
    expect(dialog).to_have_count(0)


def _natural_width(page: Page, locator) -> int:
    expect(locator).to_be_visible()
    page.wait_for_function("el => el.complete && el.naturalWidth > 0", arg=locator.element_handle())
    return locator.evaluate("el => el.naturalWidth")


# ---------------------------------------------------------------------------
# 1. Upload, author, play
# ---------------------------------------------------------------------------

PROMPT = "Which picture is the blue one?"


def test_upload_author_and_play_with_images(env: Env, page_as, cleanup: Cleanup):
    tag = uuid.uuid4().hex[:6]
    host, game = _host_user(env, cleanup, "img_host", f"E2E images {tag}")
    names = {"prompt": f"prompt-{tag}.png", "blue": f"blue-{tag}.png", "red": f"red-{tag}.png"}
    created: list[str] = []
    try:
        # ── Library page: upload images ─────────────────────────────────────────
        page: Page = page_as(host.token)
        page.goto("/host/courses")
        page.get_by_role("button", name="Images").first.click()
        expect(page).to_have_url(re.compile(rf"/host/courses/{env.course_a['id']}/images$"))
        before = page.get_by_test_id("library-image").count()
        page.get_by_test_id("library-upload").set_input_files(
            [
                {"name": names["prompt"], "mimeType": "image/png", "buffer": _png(300, 200, b"\x10\xa0\x10")},
                {"name": names["blue"], "mimeType": "image/png", "buffer": _png(120, 120, b"\x10\x10\xe0")},
            ]
        )
        expect(page.get_by_test_id("library-image")).to_have_count(before + 2)
        expect(page.get_by_text(names["blue"])).to_be_visible()
        by_name = {img["filename"]: img["id"] for img in _library(env, host.token)}
        created += [by_name[names["prompt"]], by_name[names["blue"]]]

        # ── Editor: MC question with a prompt image and two image options ───────
        page.goto(f"/host/games/{game['id']}/questions")
        page.get_by_role("button", name="Add Question").click()
        page.get_by_placeholder("Question text…").fill(PROMPT)
        page.get_by_test_id("prompt-image-add").click()
        _pick(page, names["prompt"])
        expect(page.get_by_test_id("prompt-image")).to_be_visible()

        page.get_by_placeholder("Option 1").fill("Blue")
        page.get_by_placeholder("Option 2").fill("Red")
        page.get_by_test_id("option-image-add-0").click()
        _pick(page, names["blue"])
        # The second option's image is uploaded from inside the picker.
        page.get_by_test_id("option-image-add-1").click()
        dialog = page.get_by_role("dialog", name="Choose an image")
        dialog.get_by_role("button", name="Upload new").click()
        dialog.get_by_test_id("picker-file").set_input_files(
            {"name": names["red"], "mimeType": "image/png", "buffer": _png(120, 120, b"\xe0\x10\x10")}
        )
        expect(dialog).to_have_count(0)
        expect(page.get_by_test_id("option-image-1")).to_be_visible()
        page.get_by_role("button", name="Save Question").click()
        expect(page.get_by_placeholder("Question text…")).to_have_count(0)

        r = env.api.get(f"/host/games/{game['id']}/questions", host.token)
        (q,) = r.json()
        by_name = {img["filename"]: img["id"] for img in _library(env, host.token)}
        created.append(by_name[names["red"]])
        assert q["prompt_image_id"] == by_name[names["prompt"]]
        assert q["config"]["option_image_ids"] == [by_name[names["blue"]], by_name[names["red"]]]

        # ── Play ────────────────────────────────────────────────────────────────
        host_page = page_as(host.token)
        host_page.goto("/host/home")
        expect(host_page.locator("select").nth(1)).to_have_value(str(game["id"]))
        host_page.get_by_role("button", name="Create Room").click()
        expect(host_page).to_have_url(re.compile(r"/host/game/[A-Z0-9]+/lobby$"))
        room_code = re.search(r"/host/game/([A-Z0-9]+)/lobby", host_page.url).group(1)
        cleanup.sessions.append(env.api.get(f"/game/rooms/{room_code}", host.token).json()["session_id"])

        r = env.api.post(
            "/auth/guest",
            json={
                "display_name": "E2E image player",
                "email": f"e2e.img.{tag}@example.com",
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

        # Host: the prompt image under the prompt. Phone: image tiles, no prompt image.
        prompt_img = host_page.get_by_test_id("prompt-image")
        expect(prompt_img).to_have_attribute("src", f"/api/images/{q['prompt_image_id']}")
        assert _natural_width(host_page, prompt_img) == 300
        expect(player.get_by_test_id("option-image")).to_have_count(2)
        expect(player.locator(f"img[src*='{q['prompt_image_id']}']")).to_have_count(0)
        player.get_by_role("button", name=re.compile("Blue")).click()
        expect(host_page.get_by_text("1 / 1 answered")).to_be_visible()

        # Results: thumbnails beside the bars.
        host_page.get_by_role("button", name="Show Results").click()
        expect(host_page.get_by_test_id("bar-thumb")).to_have_count(2)
    finally:
        _delete_images(env, cleanup, created)


# ---------------------------------------------------------------------------
# 2. Library guards
# ---------------------------------------------------------------------------


def test_used_image_cannot_be_deleted_and_replace_shows_new_image(
    env: Env, page_as, cleanup: Cleanup
):
    tag = uuid.uuid4().hex[:6]
    host, game = _host_user(env, cleanup, "img_lib", f"E2E image guards {tag}")
    used = _upload(env, host.token, f"inuse-{tag}.png", _png(100, 100))
    unused = _upload(env, host.token, f"spare-{tag}.png", _png(50, 50))
    r = env.api.post(
        f"/host/games/{game['id']}/questions",
        host.token,
        json={
            "type": "true_false",
            "grading_type": "COMPLETENESS",
            "prompt": "Is this a square?",
            "prompt_image_id": used["id"],
            "config": {},
            "answer_data": {},
            "time_limit_seconds": 120,
        },
    )
    assert r.status_code == 201, r.text
    try:
        page: Page = page_as(host.token)
        page.goto(f"/host/courses/{env.course_a['id']}/images")
        used_card = page.get_by_test_id("library-image").filter(has_text=used["filename"])
        unused_card = page.get_by_test_id("library-image").filter(has_text=unused["filename"])

        # A used image's Delete is disabled and the card says where it is used.
        expect(used_card.get_by_role("button", name="Delete")).to_be_disabled()
        used_card.get_by_role("button", name="Used in 1 question").click()
        expect(used_card.get_by_role("link", name=re.compile(rf"E2E image guards {tag}, question 1"))).to_be_visible()

        # An unused one can be deleted (with an inline confirm).
        unused_card.get_by_role("button", name="Delete").click()
        unused_card.get_by_test_id("library-confirm-delete").click()
        expect(page.get_by_test_id("library-image").filter(has_text=unused["filename"])).to_have_count(0)

        # Replace while the question is on the host screen (design §8): reload the host page,
        # sync_state restores the question, and the prompt image has the new size. The test
        # doesn't expect a change before the reload.
        host_page = page_as(host.token)
        host_page.goto("/host/home")
        expect(host_page.locator("select").nth(1)).to_have_value(str(game["id"]))
        host_page.get_by_role("button", name="Create Room").click()
        expect(host_page).to_have_url(re.compile(r"/host/game/[A-Z0-9]+/lobby$"))
        room_code = re.search(r"/host/game/([A-Z0-9]+)/lobby", host_page.url).group(1)
        cleanup.sessions.append(env.api.get(f"/game/rooms/{room_code}", host.token).json()["session_id"])
        r = env.api.post(
            "/auth/guest",
            json={
                "display_name": "E2E image guard player",
                "email": f"e2e.imgguard.{tag}@example.com",
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
        prompt_img = host_page.get_by_test_id("prompt-image")
        assert _natural_width(host_page, prompt_img) == 100

        used_card.get_by_test_id("library-replace").set_input_files(
            {"name": f"inuse-{tag}.png", "mimeType": "image/png", "buffer": _png(240, 60, b"\xff\x00\x00")}
        )
        expect(used_card.get_by_text("240 × 60")).to_be_visible()
        assert _natural_width(page, used_card.locator("img").first) == 240  # the local cache-buster

        host_page.reload()
        assert _natural_width(host_page, host_page.get_by_test_id("prompt-image")) == 240
    finally:
        _delete_images(env, cleanup, [used["id"], unused["id"]])
