"""
T8 image library integration tests (docs/design-image-support.md → section 8).

  * Upload / serve: measured size, 413 / 422 rejections, file names, the public GET
    without a token, nosniff + ETag + 304, canonical ids only.
  * Access: another course's host gets 403; another course's image is a 404 through
    your own course's path; ADMIN passes.
  * Question references: ownership, key placement, omitted vs. null, Pin the Spot
    image_id (server-set size), error precedence.
  * A played game: replace / delete / update guards, where-used, scoring parity.
  * Real-time payloads carry ids, never bytes.

Runs against the Docker stack on :8000.
"""

from __future__ import annotations

import asyncio
import base64
import io
import json
import pathlib
import subprocess
import time
import uuid
from collections.abc import Iterator

import httpx
import pytest
from PIL import Image

from .conftest import create_guest_tokens, create_room
from .engine.orchestrator import run_game
from .engine.scoring import GameScenario, PlayerScript, QuestionSpec
from .engine.socket_client import TestSocketClient as SocketClient
from .test_host_admin_restructure import (
    Api,
    Cleanup,
    _admin_game,
    _grant_course,
    _jwt_sub,
    _make_user,
)

_EVENT_TIMEOUT = 15.0


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def png_bytes(size=(40, 20), color=(200, 30, 30)) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", size, color).save(buf, "PNG")
    return buf.getvalue()


def new_course(api: Api, admin: str, label: str) -> int:
    tag = uuid.uuid4().hex[:8]
    r = api.post(
        "/admin/courses", admin, json={"name": f"IMG {label} {tag}", "semester": "Test"}
    )
    assert r.status_code == 201, r.text
    return r.json()["id"]


def upload(
    api: Api,
    token: str,
    course_id: int,
    data: bytes | None = None,
    name: str = "pic.png",
    content_type: str = "image/png",
) -> httpx.Response:
    return api.post(
        f"/host/courses/{course_id}/images",
        token,
        files={"file": (name, data if data is not None else png_bytes(), content_type)},
    )


def upload_ok(api: Api, token: str, course_id: int, data: bytes | None = None) -> dict:
    r = upload(api, token, course_id, data)
    assert r.status_code == 201, r.text
    return r.json()


def replace(api: Api, token: str, course_id: int, image_id: str, data: bytes):
    return api.put(
        f"/host/courses/{course_id}/images/{image_id}",
        token,
        files={"file": ("new.png", data, "image/png")},
    )


@pytest.fixture(scope="module")
def api(base_url: str) -> Api:
    return Api(base_url)


@pytest.fixture(scope="module")
def two_courses(api: Api, admin_token: str) -> Iterator[dict]:
    """Course A with two HOSTs, course B with another HOST; nobody has both."""
    cleanup = Cleanup(api, admin_token)
    try:
        a = new_course(api, admin_token, "A")
        b = new_course(api, admin_token, "B")
        host_a = _make_user(api, admin_token, cleanup, "imghosta")
        host_a2 = _make_user(api, admin_token, cleanup, "imghosta2")
        host_b = _make_user(api, admin_token, cleanup, "imghostb")
        _grant_course(api, admin_token, host_a, a, "HOST")
        _grant_course(api, admin_token, host_a2, a, "HOST")
        _grant_course(api, admin_token, host_b, b, "HOST")
        yield {"a": a, "b": b, "host_a": host_a, "host_a2": host_a2, "host_b": host_b}
    finally:
        cleanup.run()


# ---------------------------------------------------------------------------
# Upload
# ---------------------------------------------------------------------------


def test_upload_returns_measured_size(api: Api, two_courses: dict):
    host, course = two_courses["host_a"], two_courses["a"]
    body = upload_ok(api, host.token, course, png_bytes((64, 48)))
    assert (body["width"], body["height"]) == (64, 48)
    assert body["content_type"] == "image/png"
    assert body["url"] == f"/api/images/{body['id']}"
    assert body["used_by"] == []
    assert body["uploaded_by_name"] == "imghosta"
    listed = api.get(f"/host/courses/{course}/images", host.token).json()
    assert body["id"] in [img["id"] for img in listed]


def test_upload_rejects_oversized_file_with_413(api: Api, two_courses: dict):
    r = upload(api, two_courses["host_a"].token, two_courses["a"], b"\0" * 5_000_001)
    assert r.status_code == 413, r.text


@pytest.mark.parametrize(
    "data, name, content_type",
    [
        (b'<svg xmlns="http://www.w3.org/2000/svg"/>', "x.svg", "image/svg+xml"),
        (b"<html><body>hi</body></html>", "x.png", "image/png"),
        (b"plain text", "x.txt", "text/plain"),
    ],
    ids=["svg", "html_named_png", "text"],
)
def test_upload_rejects_non_images_with_422(
    api: Api, two_courses: dict, data, name, content_type
):
    r = upload(
        api, two_courses["host_a"].token, two_courses["a"], data, name, content_type
    )
    assert r.status_code == 422, r.text


@pytest.mark.parametrize(
    "name, stored",
    [
        ("photos/", "image"),
        ("C:\\photos\\cat.png", "cat.png"),
        ("x" * 296 + ".png", ("x" * 296 + ".png")[:255]),
    ],
    ids=["missing", "path_removed", "long"],
)
def test_upload_file_names(api: Api, two_courses: dict, name: str, stored: str):
    r = upload(api, two_courses["host_a"].token, two_courses["a"], name=name)
    assert r.status_code == 201, r.text
    assert r.json()["filename"] == stored


# ---------------------------------------------------------------------------
# Public serving
# ---------------------------------------------------------------------------


def test_public_get_needs_no_token_and_supports_etag(
    api: Api, base_url: str, two_courses: dict
):
    data = png_bytes((10, 10))
    body = upload_ok(api, two_courses["host_a"].token, two_courses["a"], data)
    r = httpx.get(f"{base_url}{body['url']}")
    assert r.status_code == 200
    assert r.content == data
    assert r.headers["content-type"] == "image/png"
    assert r.headers["content-length"] == str(len(data))
    assert r.headers["x-content-type-options"] == "nosniff"
    assert r.headers["cache-control"] == "no-cache"
    assert r.headers["content-disposition"] == "inline"
    etag = r.headers["etag"]
    r = httpx.get(f"{base_url}{body['url']}", headers={"If-None-Match": etag})
    assert r.status_code == 304
    assert r.content == b""
    assert r.headers["etag"] == etag


@pytest.mark.parametrize("image_id", [str(uuid.uuid4()), "not-a-uuid"])
def test_public_get_unknown_id_is_404(base_url: str, image_id: str):
    assert httpx.get(f"{base_url}/api/images/{image_id}").status_code == 404


def test_public_get_non_canonical_id_is_404(
    api: Api, base_url: str, two_courses: dict
):
    body = upload_ok(api, two_courses["host_a"].token, two_courses["a"])
    for variant in (body["id"].upper(), body["id"].replace("-", "")):
        assert httpx.get(f"{base_url}/api/images/{variant}").status_code == 404


# ---------------------------------------------------------------------------
# Access
# ---------------------------------------------------------------------------


def test_other_course_host_gets_403(api: Api, two_courses: dict):
    a, host_b = two_courses["a"], two_courses["host_b"]
    img = upload_ok(api, two_courses["host_a"].token, a)
    path = f"/host/courses/{a}/images"
    assert api.get(path, host_b.token).status_code == 403
    assert api.get(f"{path}/{img['id']}", host_b.token).status_code == 403
    assert upload(api, host_b.token, a).status_code == 403
    assert replace(api, host_b.token, a, img["id"], png_bytes()).status_code == 403
    assert api.delete(f"{path}/{img['id']}", host_b.token).status_code == 403


def test_other_course_image_is_404_through_own_course(api: Api, two_courses: dict):
    img = upload_ok(api, two_courses["host_a"].token, two_courses["a"])
    host_b, b = two_courses["host_b"], two_courses["b"]
    path = f"/host/courses/{b}/images/{img['id']}"
    assert api.get(path, host_b.token).status_code == 404
    assert replace(api, host_b.token, b, img["id"], png_bytes()).status_code == 404
    assert api.delete(path, host_b.token).status_code == 404


def test_admin_passes(api: Api, admin_token: str, two_courses: dict):
    img = upload_ok(api, admin_token, two_courses["a"])
    r = api.get(f"/host/courses/{two_courses['a']}/images/{img['id']}", admin_token)
    assert r.status_code == 200, r.text


# ---------------------------------------------------------------------------
# Replace / delete (unused images)
# ---------------------------------------------------------------------------


def test_replace_keeps_id_changes_etag_and_uploader(
    api: Api, base_url: str, two_courses: dict
):
    course = two_courses["a"]
    img = upload_ok(
        api, two_courses["host_a"].token, course, png_bytes((10, 10), (1, 1, 1))
    )
    before = httpx.get(f"{base_url}{img['url']}").headers["etag"]
    r = replace(
        api,
        two_courses["host_a2"].token,
        course,
        img["id"],
        png_bytes((30, 10), (9, 9, 9)),
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["id"] == img["id"]
    assert (body["width"], body["height"]) == (30, 10)
    assert body["filename"] == "new.png"
    assert body["uploaded_by_name"] == "imghosta2"
    assert body["size_changed"] is True
    assert body["resized_question_ids"] == []
    assert body["clamped_question_ids"] == []
    assert httpx.get(f"{base_url}{img['url']}").headers["etag"] != before


def test_replace_rejects_non_image(api: Api, two_courses: dict):
    host, course = two_courses["host_a"], two_courses["a"]
    img = upload_ok(api, host.token, course)
    assert replace(api, host.token, course, img["id"], b"nope").status_code == 422


def test_delete_unused_image(api: Api, base_url: str, two_courses: dict):
    host, course = two_courses["host_a"], two_courses["a"]
    img = upload_ok(api, host.token, course)
    r = api.delete(f"/host/courses/{course}/images/{img['id']}", host.token)
    assert r.status_code == 204, r.text
    assert httpx.get(f"{base_url}{img['url']}").status_code == 404
    listed = api.get(f"/host/courses/{course}/images", host.token).json()
    assert img["id"] not in [i["id"] for i in listed]


# ---------------------------------------------------------------------------
# Question references (design 3.3, 3.4, 4.2)
# ---------------------------------------------------------------------------

PIN_ANSWER = {"target": {"x": 0.5, "y": 0.5}, "r_full": 0.05, "r_zero": 0.2}


def mc_body(prompt_image_id=None, option_image_ids=None, **overrides) -> dict:
    config: dict = {"options": ["Red", "Blue"]}
    if option_image_ids is not None:
        config["option_image_ids"] = option_image_ids
    body = {
        "type": "multiple_choice",
        "grading_type": "ACCURACY",
        "prompt": "Which colour?",
        "config": config,
        "answer_data": {"answer_points": [0, 100]},
        "points_value": 100,
    }
    if prompt_image_id is not None:
        body["prompt_image_id"] = prompt_image_id
    body.update(overrides)
    return body


def pin_body(config: dict, answer: dict = PIN_ANSWER, **overrides) -> dict:
    body = {
        "type": "pin_the_spot",
        "grading_type": "ACCURACY",
        "prompt": "Tap the centre.",
        "config": config,
        "answer_data": answer,
        "points_value": 1000,
    }
    body.update(overrides)
    return body


def add_question(api: Api, token: str, game_id: int, body: dict) -> dict:
    r = api.post(f"/host/games/{game_id}/questions", token, json=body)
    assert r.status_code == 201, r.text
    return r.json()


def update(api: Api, token: str, game_id: int, qid: int, body: dict):
    return api.put(f"/host/games/{game_id}/questions/{qid}", token, json=body)


def get_question(api: Api, token: str, game_id: int, qid: int) -> dict:
    r = api.get(f"/host/games/{game_id}/questions", token)
    assert r.status_code == 200, r.text
    return next(q for q in r.json() if q["id"] == qid)


@pytest.fixture(scope="module")
def ref_setup(api: Api, admin_token: str, two_courses: dict) -> Iterator[dict]:
    """A game attached to course A, an image in A and one in B."""
    cleanup = Cleanup(api, admin_token)
    try:
        game = _admin_game(api, admin_token, cleanup, "IMG refs", two_courses["a"])
        own = upload_ok(api, admin_token, two_courses["a"], png_bytes((100, 50)))
        foreign = upload_ok(api, admin_token, two_courses["b"])
        yield {"game_id": game["id"], "own": own["id"], "foreign": foreign["id"]}
    finally:
        cleanup.run()


_BAD_REFERENCES = {
    "other_course_prompt": lambda r: mc_body(prompt_image_id=r["foreign"]),
    "unknown_prompt": lambda r: mc_body(prompt_image_id=str(uuid.uuid4())),
    "upper_case_prompt": lambda r: mc_body(prompt_image_id=r["own"].upper()),
    "other_course_option": lambda r: mc_body(option_image_ids=[None, r["foreign"]]),
    "option_ids_wrong_length": lambda r: mc_body(option_image_ids=[r["own"]]),
    "option_ids_on_true_false": lambda r: {
        "type": "true_false",
        "grading_type": "COMPLETENESS",
        "prompt": "True?",
        "config": {"option_image_ids": [r["own"], None]},
    },
    "pin_url_and_id": lambda r: pin_body(
        {
            "image_url": "https://example.com/x.png",
            "image_id": r["own"],
            "image_width": 100,
            "image_height": 50,
        }
    ),
    "pin_other_course_canvas": lambda r: pin_body(
        {"image_id": r["foreign"], "image_width": 100, "image_height": 50}
    ),
    "pin_with_prompt_image": lambda r: pin_body(
        {"image_id": r["own"], "image_width": 100, "image_height": 50},
        prompt_image_id=r["own"],
    ),
}


@pytest.mark.parametrize("case", sorted(_BAD_REFERENCES))
def test_bad_reference_rejected_on_create(
    api: Api, admin_token: str, ref_setup: dict, case: str
):
    body = _BAD_REFERENCES[case](ref_setup)
    r = api.post(
        f"/host/games/{ref_setup['game_id']}/questions", admin_token, json=body
    )
    assert r.status_code == 422, r.text


@pytest.mark.parametrize("case", sorted(_BAD_REFERENCES))
def test_bad_reference_rejected_on_update(
    api: Api, admin_token: str, ref_setup: dict, case: str
):
    body = _BAD_REFERENCES[case](ref_setup)
    # Start from a valid question of the same type, then PUT the bad body.
    if body["type"] == "pin_the_spot":
        start = pin_body(
            {"image_id": ref_setup["own"], "image_width": 1, "image_height": 1}
        )
    elif body["type"] == "true_false":
        start = {**body, "config": {}}
    else:
        start = mc_body()
    q = add_question(api, admin_token, ref_setup["game_id"], start)
    r = update(api, admin_token, ref_setup["game_id"], q["id"], body)
    assert r.status_code == 422, r.text


def test_stale_option_image_ids_after_adding_an_option_is_rejected(
    api: Api, admin_token: str, ref_setup: dict
):
    """A stale client adds an option but resends the old, now too-short list."""
    game_id, own = ref_setup["game_id"], ref_setup["own"]
    q = add_question(api, admin_token, game_id, mc_body(option_image_ids=[own, None]))
    config = {"options": ["Red", "Blue", "Green"], "option_image_ids": [own, None]}
    r = update(api, admin_token, game_id, q["id"], {"config": config})
    assert r.status_code == 422, r.text
    assert "option_image_ids" in r.text


def test_config_without_option_image_ids_removes_them(
    api: Api, admin_token: str, ref_setup: dict
):
    game_id, own = ref_setup["game_id"], ref_setup["own"]
    q = add_question(api, admin_token, game_id, mc_body(option_image_ids=[own, None]))
    config = {"options": ["Red", "Blue", "Green"]}
    r = update(api, admin_token, game_id, q["id"], {"config": config})
    assert r.status_code == 200, r.text
    assert "option_image_ids" not in get_question(api, admin_token, game_id, q["id"])[
        "config"
    ]


def test_unattached_game_cannot_reference_images(
    api: Api, admin_token: str, ref_setup: dict
):
    cleanup = Cleanup(api, admin_token)
    try:
        game = _admin_game(api, admin_token, cleanup, "IMG unattached", None)
        r = api.post(
            f"/host/games/{game['id']}/questions",
            admin_token,
            json=mc_body(prompt_image_id=ref_setup["own"]),
        )
        assert r.status_code == 422, r.text
        assert "attached to a course" in r.text
    finally:
        cleanup.run()


def test_prompt_image_omitted_keeps_null_clears(
    api: Api, admin_token: str, ref_setup: dict
):
    game_id = ref_setup["game_id"]
    q = add_question(
        api, admin_token, game_id, mc_body(prompt_image_id=ref_setup["own"])
    )
    assert q["prompt_image_id"] == ref_setup["own"]
    r = update(api, admin_token, game_id, q["id"], {"prompt": "Renamed"})
    assert r.status_code == 200, r.text
    assert r.json()["prompt_image_id"] == ref_setup["own"]
    r = update(api, admin_token, game_id, q["id"], {"prompt_image_id": None})
    assert r.status_code == 200, r.text
    assert r.json()["prompt_image_id"] is None
    assert get_question(api, admin_token, game_id, q["id"])["prompt_image_id"] is None


def test_legacy_update_gets_no_new_structure_validation(
    api: Api, admin_token: str, ref_setup: dict
):
    """MC keeps its unvalidated update path; only image checks were added."""
    game_id = ref_setup["game_id"]
    q = add_question(api, admin_token, game_id, mc_body())
    legacy = {"options": ["Only one"]}  # create would reject: needs 2 options
    assert (
        update(api, admin_token, game_id, q["id"], {"config": legacy}).status_code
        == 200
    )
    r = update(api, admin_token, game_id, q["id"], {"prompt": "Prompt-only edit"})
    assert r.status_code == 200, r.text


def test_pin_radii_checked_against_real_image_size(
    api: Api, admin_token: str, ref_setup: dict
):
    """The client claims a square (diagonal 1.41); the image is 2:1 (diagonal 1.118)."""
    config = {"image_id": ref_setup["own"], "image_width": 10, "image_height": 10}
    answer = {"target": {"x": 0.5, "y": 0.5}, "r_full": 0.1, "r_zero": 1.3}
    r = api.post(
        f"/host/games/{ref_setup['game_id']}/questions",
        admin_token,
        json=pin_body(config, answer),
    )
    assert r.status_code == 422, r.text


def test_pin_image_id_size_is_set_by_server(
    api: Api, admin_token: str, ref_setup: dict
):
    q = add_question(
        api,
        admin_token,
        ref_setup["game_id"],
        pin_body({"image_id": ref_setup["own"], "image_width": 7, "image_height": 7}),
    )
    assert (q["config"]["image_width"], q["config"]["image_height"]) == (100, 50)
    stored = get_question(api, admin_token, ref_setup["game_id"], q["id"])
    assert (stored["config"]["image_width"], stored["config"]["image_height"]) == (
        100,
        50,
    )


# ---------------------------------------------------------------------------
# A played game: guards on replace, delete and update
# ---------------------------------------------------------------------------


def _play(
    base_url: str,
    api: Api,
    admin: str,
    cleanup: Cleanup,
    course_id: int,
    game_id: int,
    scenario: GameScenario,
) -> list[dict]:
    room_code = create_room(base_url, admin, course_id, game_id)
    r = api.get(f"/game/rooms/{room_code}", admin)
    cleanup.sessions.append(r.json()["session_id"])
    tokens = create_guest_tokens(base_url, room_code, len(scenario.player_scripts))
    cleanup.users.extend(_jwt_sub(t) for t in tokens)
    return asyncio.run(
        run_game(
            base_url=base_url,
            host_token=admin,
            player_tokens=tokens,
            room_code=room_code,
            scenario=scenario,
        )
    )


PIO_BODY = {
    "type": "put_in_order",
    "grading_type": "ACCURACY",
    "prompt": "Order them.",
    "config": {"items": ["b", "a", "c"]},
    "answer_data": {"correct_order": [1, 0, 2]},
    "points_value": 100,
}


@pytest.fixture(scope="module")
def played(
    base_url: str, api: Api, admin_token: str, two_courses: dict
) -> Iterator[dict]:
    """
    Course A game, played once: q1 MC with a prompt image and an option image,
    q2 Pin the Spot on a library canvas, q3 the same Pin the Spot by URL,
    q4 put_in_order.
    """
    cleanup = Cleanup(api, admin_token)
    course = two_courses["a"]
    try:
        game = _admin_game(
            api, admin_token, cleanup, f"IMG played {uuid.uuid4().hex[:4]}", course
        )
        prompt = upload_ok(api, admin_token, course)["id"]
        option = upload_ok(api, admin_token, course)["id"]
        canvas = upload_ok(api, admin_token, course, png_bytes((1000, 500)))["id"]
        other_canvas = upload_ok(api, admin_token, course, png_bytes((1000, 500)))["id"]
        url_config = {
            "image_url": "https://example.com/map.png",
            "image_width": 1000,
            "image_height": 500,
        }
        q1 = add_question(
            api,
            admin_token,
            game["id"],
            mc_body(prompt_image_id=prompt, option_image_ids=[None, option]),
        )
        q2 = add_question(
            api,
            admin_token,
            game["id"],
            pin_body({"image_id": canvas, "image_width": 1000, "image_height": 500}),
        )
        add_question(api, admin_token, game["id"], pin_body(url_config))
        q4 = add_question(api, admin_token, game["id"], PIO_BODY)
        tap = {"x": 0.6, "y": 0.5}
        scenario = GameScenario(
            name="img_played",
            questions=[
                QuestionSpec(
                    "multiple_choice",
                    "ACCURACY",
                    "Which colour?",
                    q1["config"],
                    {"answer_points": [0, 100]},
                    100,
                ),
                QuestionSpec(
                    "pin_the_spot", "ACCURACY", "Tap.", q2["config"], PIN_ANSWER
                ),
                QuestionSpec(
                    "pin_the_spot", "ACCURACY", "Tap.", url_config, PIN_ANSWER
                ),
                QuestionSpec(
                    "put_in_order",
                    "ACCURACY",
                    "Order them.",
                    PIO_BODY["config"],
                    PIO_BODY["answer_data"],
                    100,
                ),
            ],
            player_scripts=[
                PlayerScript(
                    responses=[
                        {"selectedIndex": 1},
                        tap,
                        tap,
                        {"orderedIndices": [1, 0, 2]},
                    ]
                )
            ],
        )
        (game_over,) = _play(
            base_url, api, admin_token, cleanup, course, game["id"], scenario
        )
        yield {
            "course": course,
            "game_id": game["id"],
            "title": game["title"],
            "q1": q1["id"],
            "q2": q2["id"],
            "q4": q4["id"],
            "prompt": prompt,
            "option": option,
            "canvas": canvas,
            "other_canvas": other_canvas,
            "summary": game_over["questionSummary"],
            "session_id": cleanup.sessions[-1],
        }
    finally:
        cleanup.run()


def test_library_canvas_scores_like_url_canvas(played: dict):
    _, by_id, by_url, _ = played["summary"]
    assert 0 < by_id["pointsAwarded"] < 1000
    assert by_id["pointsAwarded"] == by_url["pointsAwarded"]


def test_played_canvas_cannot_be_replaced(api: Api, admin_token: str, played: dict):
    r = replace(
        api, admin_token, played["course"], played["canvas"], png_bytes((10, 10))
    )
    assert r.status_code == 409, r.text
    assert "Upload it as a new image instead" in r.text


@pytest.mark.parametrize("key", ["prompt", "option"])
def test_played_prompt_or_option_image_can_be_replaced(
    api: Api, admin_token: str, played: dict, key: str
):
    r = replace(api, admin_token, played["course"], played[key], png_bytes((12, 12)))
    assert r.status_code == 200, r.text
    assert r.json()["used_by"][0]["played"] is True


def test_switching_played_canvas_is_409(api: Api, admin_token: str, played: dict):
    config = {
        "image_id": played["other_canvas"],
        "image_width": 1000,
        "image_height": 500,
    }
    r = update(api, admin_token, played["game_id"], played["q2"], {"config": config})
    assert r.status_code == 409, r.text


def test_played_canvas_prompt_edit_with_stale_size_passes(
    api: Api, admin_token: str, played: dict
):
    stale = {"image_id": played["canvas"], "image_width": 999, "image_height": 1}
    r = update(
        api,
        admin_token,
        played["game_id"],
        played["q2"],
        {"prompt": "Tap it again.", "config": stale, "answer_data": PIN_ANSWER},
    )
    assert r.status_code == 200, r.text
    assert r.json()["config"]["image_width"] == 1000


def test_image_error_comes_before_played_guard(
    api: Api, admin_token: str, played: dict
):
    """Design 4.1: image checks run right after the merge, before any 409."""
    game_id, qid = played["game_id"], played["q4"]
    changed = {"config": {"items": ["b", "a", "c", "d"]}}
    r = update(api, admin_token, game_id, qid, changed)
    assert r.status_code == 409, r.text
    r = update(
        api, admin_token, game_id, qid, {**changed, "prompt_image_id": str(uuid.uuid4())}
    )
    assert r.status_code == 422, r.text
    assert "prompt_image_id" in r.text


def test_delete_used_image_is_409_naming_the_question(
    api: Api, admin_token: str, played: dict
):
    r = api.delete(
        f"/host/courses/{played['course']}/images/{played['prompt']}", admin_token
    )
    assert r.status_code == 409, r.text
    assert f"{played['title']}, question 1 (prompt)" in r.text


def test_where_used_lists_roles(api: Api, admin_token: str, played: dict):
    r = api.get(
        f"/host/courses/{played['course']}/images/{played['canvas']}", admin_token
    )
    assert r.status_code == 200, r.text
    (use,) = r.json()["used_by"]
    assert use["question_id"] == played["q2"]
    assert use["roles"] == ["canvas"]
    assert use["played"] is True
    listed = api.get(f"/host/courses/{played['course']}/images", admin_token).json()
    by_id = {img["id"]: img for img in listed}
    assert by_id[played["option"]]["used_by"][0]["roles"] == ["option"]


def test_course_host_without_game_access_sees_where_used(
    api: Api, two_courses: dict, played: dict
):
    """Decision 6: the library is course-wide, not filtered by game access."""
    host = two_courses["host_a2"]
    r = api.get(f"/host/courses/{played['course']}/images/{played['prompt']}", host.token)
    assert r.status_code == 200, r.text
    assert r.json()["used_by"][0]["game_title"] == played["title"]


def test_delete_after_last_use_removed(api: Api, admin_token: str, two_courses: dict):
    cleanup = Cleanup(api, admin_token)
    course = two_courses["a"]
    try:
        game = _admin_game(api, admin_token, cleanup, "IMG delete", course)
        img = upload_ok(api, admin_token, course)["id"]
        q = add_question(api, admin_token, game["id"], mc_body(prompt_image_id=img))
        path = f"/host/courses/{course}/images/{img}"
        assert api.delete(path, admin_token).status_code == 409
        assert (
            update(
                api, admin_token, game["id"], q["id"], {"prompt_image_id": None}
            ).status_code
            == 200
        )
        assert api.delete(path, admin_token).status_code == 204
    finally:
        cleanup.run()


def test_replace_resizes_and_clamps_unplayed_canvas(
    api: Api, admin_token: str, two_courses: dict
):
    cleanup = Cleanup(api, admin_token)
    course = two_courses["a"]
    try:
        game = _admin_game(api, admin_token, cleanup, "IMG clamp", course)
        tall = upload_ok(api, admin_token, course, png_bytes((100, 400)))["id"]
        answer = {"target": {"x": 0.5, "y": 0.5}, "r_full": 0.5, "r_zero": 3.0}
        q = add_question(
            api,
            admin_token,
            game["id"],
            pin_body(
                {"image_id": tall, "image_width": 100, "image_height": 400}, answer
            ),
        )
        r = replace(api, admin_token, course, tall, png_bytes((400, 100)))
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["size_changed"] is True
        assert body["resized_question_ids"] == [q["id"]]
        assert body["clamped_question_ids"] == [q["id"]]
        # A fresh read: a lost in-place JSON change would fail here.
        stored = get_question(api, admin_token, game["id"], q["id"])
        assert (stored["config"]["image_width"], stored["config"]["image_height"]) == (
            400,
            100,
        )
        assert stored["answer_data"]["r_zero"] == 1.03  # floor₂(√(1 + 0.25²))
        assert stored["answer_data"]["r_full"] == 0.5
    finally:
        cleanup.run()


# ---------------------------------------------------------------------------
# Real-time payloads (design 4.5)
# ---------------------------------------------------------------------------


async def test_payloads_carry_image_ids_not_bytes(
    base_url: str, api: Api, admin_token: str, two_courses: dict
):
    cleanup = Cleanup(api, admin_token)
    course = two_courses["a"]
    clients: list[SocketClient] = []
    try:
        game = _admin_game(api, admin_token, cleanup, "IMG payload", course)
        prompt = upload_ok(api, admin_token, course)["id"]
        option = upload_ok(api, admin_token, course)["id"]
        add_question(
            api,
            admin_token,
            game["id"],
            mc_body(prompt_image_id=prompt, option_image_ids=[option, None]),
        )
        room_code = create_room(base_url, admin_token, course, game["id"])
        cleanup.sessions.append(
            api.get(f"/game/rooms/{room_code}", admin_token).json()["session_id"]
        )
        (token,) = create_guest_tokens(base_url, room_code, 1)
        cleanup.users.append(_jwt_sub(token))

        host = SocketClient(base_url, admin_token, "host")
        player = SocketClient(base_url, token, "player")
        clients += [host, player]
        for client, role in ((host, "HOST"), (player, "PLAYER")):
            await client.connect()
            await client.emit("join_room", {"room_code": room_code, "role": role})
            await client.wait_for("sync_state", _EVENT_TIMEOUT)
        await host.emit("host_advance", {})
        for client in (host, player):
            payload = await client.wait_for("new_question", _EVENT_TIMEOUT)
            assert payload["promptImageId"] == prompt
            assert payload["config"]["option_image_ids"] == [option, None]
            assert "data:" not in json.dumps(payload)

        # A reconnecting host gets the prompt image back through sync_state.
        host2 = SocketClient(base_url, admin_token, "host2")
        clients.append(host2)
        await host2.connect()
        await host2.emit("join_room", {"room_code": room_code, "role": "HOST"})
        sync = await host2.wait_for("sync_state", _EVENT_TIMEOUT)
        assert sync["currentQuestion"]["promptImageId"] == prompt

        # The host game_over summary carries the option image ids (via config).
        await player.emit(
            "submit_answer",
            {
                "question_id": payload["questionId"],
                "answer_data": {"selectedIndex": 0},
                "answer_time_ms": 300,
            },
        )
        await player.wait_for("answer_received", _EVENT_TIMEOUT)
        await host2.emit("host_advance", {})
        await host2.wait_for("question_results", _EVENT_TIMEOUT)
        await host2.emit("host_advance", {})
        over = await host2.wait_for("game_over", _EVENT_TIMEOUT)
        assert over["questionSummary"][0]["config"]["option_image_ids"] == [
            option,
            None,
        ]
    finally:
        await asyncio.gather(*[c.disconnect() for c in clients], return_exceptions=True)
        cleanup.run()


# ---------------------------------------------------------------------------
# Export / import (design 4.7)
# ---------------------------------------------------------------------------

_REPO_ROOT = pathlib.Path(__file__).parent.parent.parent


def _export(api: Api, token: str, game_id: int) -> dict:
    r = api.get(f"/host/games/{game_id}/export", token)
    assert r.status_code == 200, r.text
    return r.json()


def _import(api: Api, token: str, bundle: dict | bytes, course_id: int | None):
    content = bundle if isinstance(bundle, bytes) else json.dumps(bundle)
    files = {"file": ("g.json", content, "application/json")}
    if course_id is None:
        return api.post("/admin/games/import", token, files=files)
    return api.post(
        "/host/games/import", token, files=files, data={"course_id": str(course_id)}
    )


def _course_image_ids(api: Api, token: str, course_id: int) -> set[str]:
    r = api.get(f"/host/courses/{course_id}/images", token)
    assert r.status_code == 200, r.text
    return {img["id"] for img in r.json()}


def delete_image_row(image_id: str) -> None:
    """Stand-in for the accepted delete race: remove a row behind the scan's back."""
    assert image_id == str(uuid.UUID(image_id))  # never interpolate anything else
    subprocess.run(
        [
            "docker",
            "compose",
            "exec",
            "-T",
            "mysql",
            "sh",
            "-c",
            'mysql -uroot -p"$MYSQL_ROOT_PASSWORD" "$MYSQL_DATABASE" '
            f"-e \"DELETE FROM images WHERE id = '{image_id}'\"",
        ],
        check=True,
        cwd=_REPO_ROOT,
        capture_output=True,
    )


@pytest.fixture(scope="module")
def image_game(api: Api, admin_token: str, two_courses: dict) -> Iterator[dict]:
    """A course-A game with a prompt image, option images and a library canvas."""
    cleanup = Cleanup(api, admin_token)
    course = two_courses["a"]
    try:
        game = _admin_game(api, admin_token, cleanup, "IMG export", course)
        jpeg = io.BytesIO()
        Image.new("RGB", (30, 20), (10, 120, 200)).save(jpeg, "JPEG", quality=90)
        prompt = upload_ok(api, admin_token, course, jpeg.getvalue())["id"]
        option = upload_ok(api, admin_token, course, png_bytes((8, 8), (0, 255, 0)))[
            "id"
        ]
        canvas = upload_ok(api, admin_token, course, png_bytes((200, 100)))["id"]
        add_question(
            api,
            admin_token,
            game["id"],
            mc_body(prompt_image_id=prompt, option_image_ids=[option, option]),
        )
        add_question(
            api,
            admin_token,
            game["id"],
            pin_body({"image_id": canvas, "image_width": 200, "image_height": 100}),
        )
        add_question(api, admin_token, game["id"], mc_body())
        yield {
            "game_id": game["id"],
            "cleanup": cleanup,
            "images": {prompt, option, canvas},
        }
    finally:
        cleanup.run()


def test_game_without_images_exports_version_1(
    api: Api, admin_token: str, two_courses: dict
):
    cleanup = Cleanup(api, admin_token)
    try:
        game = _admin_game(api, admin_token, cleanup, "IMG v1", two_courses["a"])
        add_question(api, admin_token, game["id"], mc_body())
        bundle = _export(api, admin_token, game["id"])
        assert bundle["version"] == 1
        assert "images" not in bundle
        assert "prompt_image_id" not in bundle["questions"][0]
    finally:
        cleanup.run()


def test_export_v2_round_trip_into_other_course(
    api: Api, admin_token: str, base_url: str, image_game: dict, two_courses: dict
):
    bundle = _export(api, admin_token, image_game["game_id"])
    assert bundle["version"] == 2
    assert {e["id"] for e in bundle["images"]} == image_game["images"]
    assert len(bundle["images"]) == 3  # the option image once, though used twice
    assert bundle["questions"][2]["prompt_image_id"] is None

    target = two_courses["b"]
    before = _course_image_ids(api, admin_token, target)
    r = _import(api, admin_token, bundle, target)
    assert r.status_code == 201, r.text
    new_game = r.json()["game_id"]
    image_game["cleanup"].games.append(new_game)
    added = _course_image_ids(api, admin_token, target) - before
    assert len(added) == 3 and not added & image_game["images"]

    questions = api.get(f"/host/games/{new_game}/questions", admin_token).json()
    mc, pin, _ = questions
    assert mc["prompt_image_id"] in added
    assert set(mc["config"]["option_image_ids"]) <= added
    assert pin["config"]["image_id"] in added
    assert (pin["config"]["image_width"], pin["config"]["image_height"]) == (200, 100)
    # Same bytes (process_upload is idempotent), so the JPEG survives the round trip.
    by_id = {e["id"]: e for e in bundle["images"]}
    original = base64.b64decode(
        by_id[bundle["questions"][0]["prompt_image_id"]]["data_base64"]
    )
    assert (
        httpx.get(f"{base_url}/api/images/{mc['prompt_image_id']}").content == original
    )

    # A second import reuses the images: no new rows.
    r = _import(api, admin_token, bundle, target)
    assert r.status_code == 201, r.text
    image_game["cleanup"].games.append(r.json()["game_id"])
    assert _course_image_ids(api, admin_token, target) - before == added


def test_import_into_own_course_reuses_originals(
    api: Api, admin_token: str, image_game: dict, two_courses: dict
):
    course = two_courses["a"]
    bundle = _export(api, admin_token, image_game["game_id"])
    before = _course_image_ids(api, admin_token, course)
    r = _import(api, admin_token, bundle, course)
    assert r.status_code == 201, r.text
    image_game["cleanup"].games.append(r.json()["game_id"])
    assert _course_image_ids(api, admin_token, course) == before


def test_import_reuses_the_oldest_of_identical_rows(api: Api, admin_token: str):
    cleanup = Cleanup(api, admin_token)
    try:
        course = new_course(api, admin_token, "oldest")
        data = png_bytes((9, 9), (4, 5, 6))
        older = upload_ok(api, admin_token, course, data)["id"]
        time.sleep(1.1)  # created_at has one-second resolution; ties go by id
        newer = upload_ok(api, admin_token, course, data)["id"]
        game = _admin_game(api, admin_token, cleanup, "IMG oldest", course)
        add_question(api, admin_token, game["id"], mc_body(prompt_image_id=newer))
        r = _import(api, admin_token, _export(api, admin_token, game["id"]), course)
        assert r.status_code == 201, r.text
        cleanup.games.append(r.json()["game_id"])
        (q,) = api.get(f"/host/games/{r.json()['game_id']}/questions", admin_token).json()
        assert q["prompt_image_id"] == older
        assert _course_image_ids(api, admin_token, course) == {older, newer}
    finally:
        cleanup.run()


def test_unused_image_entry_is_checked_but_not_inserted(
    api: Api, admin_token: str, image_game: dict
):
    bundle = _export(api, admin_token, image_game["game_id"])
    extra = png_bytes((5, 5), (1, 2, 3))
    bundle["images"].append(
        {"id": "unused", "data_base64": base64.b64encode(extra).decode()}
    )
    course = new_course(api, admin_token, "unused")
    r = _import(api, admin_token, bundle, course)
    assert r.status_code == 201, r.text
    image_game["cleanup"].games.append(r.json()["game_id"])
    assert len(_course_image_ids(api, admin_token, course)) == 3


def test_admin_import_rejects_v2_with_images(
    api: Api, admin_token: str, image_game: dict
):
    bundle = _export(api, admin_token, image_game["game_id"])
    r = _import(api, admin_token, bundle, None)
    assert r.status_code == 422, r.text
    assert "must be imported into a course" in r.text


@pytest.mark.parametrize(
    "mutate",
    [
        lambda q: q.update(prompt_image_id=str(uuid.uuid4())),
        lambda q: q["config"].update(option_image_ids=[None, None]),
    ],
    ids=["prompt_image_id", "option_image_ids"],
)
def test_v1_file_with_image_key_is_rejected(
    api: Api, admin_token: str, two_courses: dict, mutate
):
    question = mc_body()
    mutate(question)
    bundle = {
        "format": "buzzer/game",
        "version": 1,
        "game": {"title": "v1 with image"},
        "questions": [question],
    }
    r = _import(api, admin_token, bundle, two_courses["a"])
    assert r.status_code == 422, r.text
    assert "need a version 2 file" in r.text


def test_v1_file_with_null_prompt_image_imports(
    api: Api, admin_token: str, image_game: dict, two_courses: dict
):
    bundle = {
        "format": "buzzer/game",
        "version": 1,
        "game": {"title": "v1 null image"},
        "questions": [{**mc_body(), "prompt_image_id": None}],
    }
    r = _import(api, admin_token, bundle, two_courses["a"])
    assert r.status_code == 201, r.text
    image_game["cleanup"].games.append(r.json()["game_id"])


def test_broken_image_after_a_valid_one_fails_whole_import(
    api: Api, admin_token: str, image_game: dict
):
    bundle = _export(api, admin_token, image_game["game_id"])
    bundle["images"].append({"id": "broken", "data_base64": "not base64!!"})
    course = new_course(api, admin_token, "broken")
    r = _import(api, admin_token, bundle, course)
    assert r.status_code == 422, r.text
    assert "Image 4 invalid" in r.text
    assert _course_image_ids(api, admin_token, course) == set()
    assert api.get("/host/games", admin_token, params={"course_id": course}).json() == []


def test_failure_after_images_flushed_leaves_nothing(
    api: Api, admin_token: str, image_game: dict
):
    """Images are inserted and flushed before the questions; a bad question after
    that must still leave no image or game rows (get_db rolls back)."""
    bundle = _export(api, admin_token, image_game["game_id"])
    bundle["questions"][1]["answer_data"] = {
        "target": {"x": 0.5, "y": 0.5},
        "r_full": 0.1,
        "r_zero": 1.2,  # past the 2:1 canvas's diagonal (≈ 1.118)
    }
    bundle["questions"][1]["config"]["image_width"] = 100  # claims a square
    course = new_course(api, admin_token, "rollback")
    r = _import(api, admin_token, bundle, course)
    assert r.status_code == 422, r.text
    assert "Question 2 invalid" in r.text
    assert _course_image_ids(api, admin_token, course) == set()
    assert api.get("/host/games", admin_token, params={"course_id": course}).json() == []


def test_export_with_dangling_reference_is_409(
    api: Api, admin_token: str, two_courses: dict
):
    cleanup = Cleanup(api, admin_token)
    course = two_courses["a"]
    try:
        game = _admin_game(api, admin_token, cleanup, "IMG dangling", course)
        option = upload_ok(api, admin_token, course)["id"]
        add_question(api, admin_token, game["id"], mc_body())
        add_question(
            api, admin_token, game["id"], mc_body(option_image_ids=[None, option])
        )
        delete_image_row(option)
        r = api.get(f"/host/games/{game['id']}/export", admin_token)
        assert r.status_code == 409, r.text
        assert "Question 2 refers to an image that was deleted" in r.text
    finally:
        cleanup.run()


def test_sample_games_still_import(api: Api, admin_token: str, two_courses: dict):
    cleanup = Cleanup(api, admin_token)
    try:
        for path in sorted((_REPO_ROOT / "sample_games").glob("*.json")):
            r = _import(api, admin_token, path.read_bytes(), two_courses["a"])
            assert r.status_code == 201, f"{path.name}: {r.text}"
            cleanup.games.append(r.json()["game_id"])
    finally:
        cleanup.run()


# ---------------------------------------------------------------------------
# HTML session report (design 4.6)
# ---------------------------------------------------------------------------


def test_report_embeds_images_and_survives_missing_ones(
    base_url: str, api: Api, admin_token: str, two_courses: dict
):
    cleanup = Cleanup(api, admin_token)
    course = two_courses["a"]
    try:
        game = _admin_game(api, admin_token, cleanup, "IMG report", course)
        mc_prompt = upload_ok(api, admin_token, course)["id"]
        option = upload_ok(api, admin_token, course, png_bytes((8, 8), (0, 9, 0)))["id"]
        ms_prompt = upload_ok(api, admin_token, course, png_bytes((6, 6), (7, 0, 0)))[
            "id"
        ]
        canvas = upload_ok(api, admin_token, course, png_bytes((200, 100)))["id"]
        q1 = add_question(
            api,
            admin_token,
            game["id"],
            mc_body(prompt_image_id=mc_prompt, option_image_ids=[None, option]),
        )
        ms = {
            "type": "multi_select",
            "grading_type": "COMPLETENESS",
            "prompt": "Pick some.",
            "prompt_image_id": ms_prompt,
            "config": {"options": ["x", "y"], "option_image_ids": [option, None]},
            "points_value": 10,
        }
        q2 = add_question(api, admin_token, game["id"], ms)
        q3 = add_question(
            api,
            admin_token,
            game["id"],
            pin_body({"image_id": canvas, "image_width": 200, "image_height": 100}),
        )
        scenario = GameScenario(
            name="img_report",
            questions=[
                QuestionSpec(
                    "multiple_choice",
                    "ACCURACY",
                    "Which colour?",
                    q1["config"],
                    {"answer_points": [0, 100]},
                    100,
                ),
                QuestionSpec(
                    "multi_select", "COMPLETENESS", "Pick some.", q2["config"], {}, 10
                ),
                QuestionSpec(
                    "pin_the_spot", "ACCURACY", "Tap.", q3["config"], PIN_ANSWER
                ),
            ],
            player_scripts=[
                PlayerScript(
                    responses=[
                        {"selectedIndex": 1},
                        {"selectedIndices": [0]},
                        {"x": 0.5, "y": 0.5},
                    ]
                )
            ],
        )
        _play(base_url, api, admin_token, cleanup, course, game["id"], scenario)
        report = f"/host/sessions/{cleanup.sessions[-1]}/report"

        r = api.get(report, admin_token)
        assert r.status_code == 200, r.text
        html = r.text
        assert html.count('<img class="q-prompt-img" src="data:image/png;base64,') == 2
        assert html.count('<img class="bar-thumb" src="data:image/png;base64,') == 1
        assert '<image href="data:image/png;base64,' in html  # the library canvas
        assert "/api/images/" not in html  # self-contained: no links to the server

        # The accepted delete race: rows gone behind the scan's back.
        delete_image_row(option)
        delete_image_row(canvas)
        r = api.get(report, admin_token)
        assert r.status_code == 200, r.text
        assert 'class="bar-thumb"' not in r.text
        assert "Image missing" in r.text
        assert r.text.count('class="q-prompt-img"') == 2
    finally:
        cleanup.run()


def test_question_numbers_are_positions_not_order_index(
    api: Api, admin_token: str, two_courses: dict
):
    """Mean review R1: a delete leaves a gap in order_index; labels follow the editor."""
    cleanup = Cleanup(api, admin_token)
    course = two_courses["a"]
    try:
        game = _admin_game(api, admin_token, cleanup, "IMG numbering", course)
        first = add_question(api, admin_token, game["id"], mc_body())
        prompt = upload_ok(api, admin_token, course)["id"]
        option = upload_ok(api, admin_token, course)["id"]
        add_question(
            api,
            admin_token,
            game["id"],
            mc_body(prompt_image_id=prompt, option_image_ids=[None, option]),
        )
        r = api.delete(f"/host/games/{game['id']}/questions/{first['id']}", admin_token)
        assert r.status_code == 204, r.text

        r = api.get(f"/host/courses/{course}/images/{prompt}", admin_token)
        (use,) = r.json()["used_by"]
        assert (use["order_index"], use["question_number"]) == (1, 1)
        r = api.delete(f"/host/courses/{course}/images/{prompt}", admin_token)
        assert r.status_code == 409
        assert "IMG numbering, question 1 (prompt)" in r.text

        delete_image_row(option)
        r = api.get(f"/host/games/{game['id']}/export", admin_token)
        assert r.status_code == 409
        assert "Question 1 refers to an image that was deleted" in r.text
    finally:
        cleanup.run()
