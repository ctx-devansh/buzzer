"""
T8 image library integration tests (docs/design-image-support.md → section 8).

  * Upload / serve: measured size, 413 / 422 rejections, file names, the public GET
    without a token, nosniff + ETag + 304, canonical ids only.
  * Access: another course's host gets 403; another course's image is a 404 through
    your own course's path; ADMIN passes.
  * Replace / delete of library images, including the where-used guards.

Runs against the Docker stack on :8000.
"""

from __future__ import annotations

import io
import uuid
from collections.abc import Iterator

import httpx
import pytest
from PIL import Image

from .test_host_admin_restructure import (
    Api,
    Cleanup,
    _grant_course,
    _make_user,
)


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
