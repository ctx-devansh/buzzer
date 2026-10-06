"""
Unit tests for the T8 image library's pure helpers (docs/design-image-support.md §8).

No Docker stack needed: fixtures are generated with Pillow in memory.

Run with (from the repo root, so the root pytest.ini puts backend/ on the path):
    pytest -c pytest.ini tests/unit/test_image_service.py -v
"""

from __future__ import annotations

import hashlib
import io
import math
import struct

import pytest
from app.schemas.admin import validate_image_keys, validate_pin_the_spot
from app.services.image_service import (
    MAX_UPLOAD_BYTES,
    ImageRejected,
    ImageTooLarge,
    clamp_radii,
    process_upload,
)
from PIL import Image
from PIL.PngImagePlugin import PngInfo

GPS_IFD = 0x8825
ORIENTATION = 0x0112


def _encode(img: Image.Image, fmt: str, **params) -> bytes:
    buf = io.BytesIO()
    img.save(buf, fmt, **params)
    return buf.getvalue()


def _photo(size=(40, 20)) -> Image.Image:
    img = Image.new("RGB", size)
    for x in range(size[0]):
        for y in range(size[1]):
            img.putpixel((x, y), (x * 6 % 256, y * 12 % 256, (x + y) % 256))
    return img


def _jpeg_with_exif(orientation: int | None = None, gps: bool = False) -> bytes:
    exif = Image.Exif()
    exif[0x010F] = "PhoneMaker"
    if orientation:
        exif[ORIENTATION] = orientation
    if gps:
        exif[GPS_IFD] = {1: "N", 2: (43.0, 4.0, 30.0)}
    return _encode(_photo(), "JPEG", exif=exif.tobytes(), quality=95)


def _maker_exif() -> bytes:
    exif = Image.Exif()
    exif[0x010F] = "PhoneMaker"
    return exif.tobytes()


def _jpeg_with_iptc() -> bytes:
    """A clean JPEG with an APP13 (Photoshop/IPTC) segment spliced in after SOI."""
    raw = _encode(_photo(), "JPEG", quality=95)
    payload = b"Photoshop 3.0\x008BIM\x04\x04\x00\x00\x00\x00\x00\x0cMadison, WI\x00"
    segment = b"\xff\xed" + struct.pack(">H", len(payload) + 2) + payload
    return raw[:2] + segment + raw[2:]


def _png_with_text() -> bytes:
    meta = PngInfo()
    meta.add_text("Author", "someone")
    return _encode(_photo(), "PNG", pnginfo=meta)


def _animated_gif() -> bytes:
    frames = [Image.new("P", (16, 16), color) for color in (1, 2, 3)]
    buf = io.BytesIO()
    frames[0].save(buf, "GIF", save_all=True, append_images=frames[1:], duration=100)
    return buf.getvalue()


FIXTURES = {
    "png": lambda: _encode(_photo(), "PNG"),
    "png_rgba": lambda: _encode(Image.new("RGBA", (10, 10), (1, 2, 3, 100)), "PNG"),
    "png_text": _png_with_text,
    "jpeg": lambda: _encode(_photo(), "JPEG", quality=95),
    "jpeg_exif": lambda: _jpeg_with_exif(orientation=6, gps=True),
    "jpeg_comment": lambda: _encode(_photo(), "JPEG", comment=b"secret"),
    "jpeg_iptc": _jpeg_with_iptc,
    "gif_static": lambda: _encode(Image.new("P", (12, 8), 5), "GIF"),
    "gif_comment": lambda: _encode(
        Image.new("P", (12, 8), 5), "GIF", comment=b"Shot at 43.07N 89.40W"
    ),
    "gif_transparent": lambda: _encode(
        Image.new("P", (12, 8), 5), "GIF", transparency=5, comment=b"note"
    ),
    "gif_animated": _animated_gif,
    "webp": lambda: _encode(_photo(), "WEBP", quality=80),
    "webp_exif": lambda: _encode(_photo(), "WEBP", quality=80, exif=_maker_exif()),
}


# ---------------------------------------------------------------------------
# Accepted formats
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "name, content_type",
    [
        ("png", "image/png"),
        ("jpeg", "image/jpeg"),
        ("gif_static", "image/gif"),
        ("gif_animated", "image/gif"),
        ("webp", "image/webp"),
    ],
)
def test_accepts_each_format(name, content_type):
    out = process_upload(FIXTURES[name]())
    assert out.content_type == content_type
    assert out.width > 0 and out.height > 0
    assert out.byte_size == len(out.data)


def test_animated_gif_is_stored_byte_for_byte():
    raw = _animated_gif()
    assert process_upload(raw).data == raw


def test_static_gif_is_stored_byte_for_byte():
    raw = FIXTURES["gif_static"]()
    assert process_upload(raw).data == raw


@pytest.mark.parametrize("name", ["png", "jpeg", "webp", "png_rgba"])
def test_clean_image_is_stored_byte_for_byte(name):
    raw = FIXTURES[name]()
    assert process_upload(raw).data == raw


# ---------------------------------------------------------------------------
# Rejections
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "raw",
    [
        b'<svg xmlns="http://www.w3.org/2000/svg"><script>alert(1)</script></svg>',
        b"just some plain text",
        b"<!doctype html><html><body>renamed.png</body></html>",
    ],
    ids=["svg", "text", "html_renamed_png"],
)
def test_rejects_non_images(raw):
    with pytest.raises(ImageRejected) as exc:
        process_upload(raw)
    assert not isinstance(exc.value, ImageTooLarge)


def test_rejects_truncated_png():
    raw = FIXTURES["png"]()
    with pytest.raises(ImageRejected):
        process_upload(raw[: len(raw) // 2])


def test_rejects_empty_file():
    with pytest.raises(ImageRejected):
        process_upload(b"")


def test_rejects_file_over_limit_as_too_large():
    with pytest.raises(ImageTooLarge):
        process_upload(b"\x89PNG" + b"\0" * MAX_UPLOAD_BYTES)


def test_rejects_decompression_bomb():
    # 7000 x 7000 = 49 MP, over the 40 MP limit, yet a tiny 1-bit file.
    raw = _encode(Image.new("1", (7000, 7000)), "PNG")
    assert len(raw) < MAX_UPLOAD_BYTES
    with pytest.raises(ImageRejected, match="pixels"):
        process_upload(raw)


def test_pixel_limit_is_checked_before_decoding(monkeypatch):
    """Over 40 MP is refused from the header alone: nothing is ever load()ed."""
    raw = _encode(Image.new("1", (7000, 7000)), "PNG")

    def no_load(self):
        raise AssertionError("decoded an over-limit image")

    monkeypatch.setattr(Image.Image, "load", no_load)
    with pytest.raises(ImageRejected, match="pixels"):
        process_upload(raw)


def test_pillow_global_pixel_limit_is_untouched():
    import app.services.image_service  # noqa: F401  (import has no side effects)

    assert Image.MAX_IMAGE_PIXELS == int(1024 * 1024 * 1024 // 4 // 3)


def test_rejects_side_over_20000():
    raw = _encode(Image.new("1", (20_001, 1)), "PNG")
    with pytest.raises(ImageRejected, match="20000"):
        process_upload(raw)


# ---------------------------------------------------------------------------
# Metadata, orientation, hash
# ---------------------------------------------------------------------------


def test_exif_with_gps_is_removed():
    raw = _jpeg_with_exif(gps=True)
    assert Image.open(io.BytesIO(raw)).getexif().get(GPS_IFD) is not None
    out = process_upload(raw)
    stored = Image.open(io.BytesIO(out.data))
    assert not stored.getexif()
    assert "exif" not in stored.info


@pytest.mark.parametrize("name", ["png_text", "jpeg_comment", "jpeg_iptc", "gif_comment"])
def test_other_metadata_is_removed(name):
    raw = FIXTURES[name]()
    out = process_upload(raw)
    assert out.data != raw
    stored = Image.open(io.BytesIO(out.data))
    assert not {"comment", "Author", "photoshop"} & set(stored.info)
    assert all(marker != "APP13" for marker, _ in getattr(stored, "applist", []))


def test_iptc_fixture_really_carries_iptc():
    assert "photoshop" in Image.open(io.BytesIO(_jpeg_with_iptc())).info


def test_orientation_is_applied_and_size_swaps():
    raw = _jpeg_with_exif(orientation=6)  # 40 x 20, "rotate 90° clockwise"
    out = process_upload(raw)
    assert (out.width, out.height) == (20, 40)


def test_sha256_is_of_stored_bytes():
    out = process_upload(_jpeg_with_exif(gps=True))
    assert out.sha256 == hashlib.sha256(out.data).hexdigest()


@pytest.mark.parametrize("name", sorted(FIXTURES))
def test_idempotent(name):
    once = process_upload(FIXTURES[name]())
    twice = process_upload(once.data)
    assert twice.data == once.data
    assert twice.sha256 == once.sha256


# ---------------------------------------------------------------------------
# clamp_radii (replace step 4)
# ---------------------------------------------------------------------------

PIN_URL = "https://example.com/board.png"


def test_clamp_tall_to_wide():
    answer = {"target": {"x": 0.5, "y": 0.5}, "r_full": 0.9, "r_zero": 3.0}
    out = clamp_radii(answer, 400, 100)  # diagonal √(1 + 0.25²) ≈ 1.0308
    assert out["r_zero"] == math.floor(math.hypot(1, 0.25) * 100) / 100 == 1.03
    assert out["r_full"] <= out["r_zero"] - 0.01 + 1e-12
    assert out["target"] == answer["target"]
    config = {"image_url": PIN_URL, "image_width": 400, "image_height": 100}
    validate_pin_the_spot("ACCURACY", config, out)


def test_clamp_leaves_fitting_radii_alone():
    answer = {"target": {"x": 0.1, "y": 0.9}, "r_full": 0.05, "r_zero": 0.2}
    assert clamp_radii(answer, 400, 100) == answer


def test_clamp_without_target_is_untouched():
    assert clamp_radii({}, 400, 100) == {}


# ---------------------------------------------------------------------------
# validate_image_keys (design 3.2, 3.3)
# ---------------------------------------------------------------------------

IMG = "0b9b6a52-3f9e-4c1a-9a43-2f1d5e6c7b80"
NON_CANONICAL = {
    "upper_case": IMG.upper(),
    "no_hyphens": IMG.replace("-", ""),
    "braces": "{" + IMG + "}",
    "not_a_uuid": "not-a-uuid",
}
TWO = {"options": ["a", "b"]}


@pytest.mark.parametrize(
    "q_type, prompt_image_id, config",
    [
        ("true_false", None, {"option_image_ids": [IMG, None]}),
        ("fill_in_the_blank", None, {"option_image_ids": [IMG]}),
        ("put_in_order", None, {"items": ["a", "b", "c"], "option_image_ids": [IMG]}),
        ("pin_the_spot", None, {"option_image_ids": [IMG]}),
        ("multiple_choice", None, {**TWO, "image_id": IMG}),
        ("pin_the_spot", IMG, {"image_id": IMG}),
        ("multiple_choice", None, {**TWO, "option_image_ids": [IMG]}),
        ("multiple_choice", None, {**TWO, "option_image_ids": "x"}),
    ],
    ids=[
        "option_ids_on_tf",
        "option_ids_on_fitb",
        "option_ids_on_pio",
        "option_ids_on_pin",
        "image_id_on_mc",
        "prompt_image_on_pin",
        "option_ids_wrong_length",
        "option_ids_not_a_list",
    ],
)
def test_validate_image_keys_rejects(q_type, prompt_image_id, config):
    with pytest.raises(ValueError):
        validate_image_keys(q_type, prompt_image_id, config)


@pytest.mark.parametrize("bad", sorted(NON_CANONICAL))
def test_non_canonical_ids_rejected_in_every_position(bad):
    bad_id = NON_CANONICAL[bad]
    with pytest.raises(ValueError, match="prompt_image_id"):
        validate_image_keys("multiple_choice", bad_id, TWO)
    with pytest.raises(ValueError, match=r"option_image_ids\[1\]"):
        validate_image_keys(
            "multiple_choice", None, {**TWO, "option_image_ids": [IMG, bad_id]}
        )
    config = {"image_id": bad_id, "image_width": 10, "image_height": 10}
    with pytest.raises(ValueError, match="image_id"):
        validate_pin_the_spot("COMPLETENESS", config, {})


@pytest.mark.parametrize(
    "q_type, prompt_image_id, config",
    [
        ("multiple_choice", IMG, {**TWO, "option_image_ids": [IMG, None]}),
        ("multi_select", None, {**TWO, "option_image_ids": [None, None]}),
        ("true_false", IMG, {}),
        ("pin_the_spot", None, {"image_id": IMG}),
    ],
)
def test_validate_image_keys_accepts(q_type, prompt_image_id, config):
    validate_image_keys(q_type, prompt_image_id, config)


def test_pin_accepts_image_id_and_rejects_both_sources():
    sized = {"image_width": 10, "image_height": 10}
    validate_pin_the_spot("COMPLETENESS", {"image_id": IMG, **sized}, {})
    both = {"image_id": IMG, "image_url": PIN_URL, **sized}
    with pytest.raises(ValueError, match="exactly"):
        validate_pin_the_spot("COMPLETENESS", both, {})


def test_static_gif_comment_removed_and_transparency_kept():
    out = process_upload(FIXTURES["gif_transparent"]())
    stored = Image.open(io.BytesIO(out.data))
    assert out.content_type == "image/gif"
    assert "comment" not in stored.info
    # Pillow compacts the palette on save, so check the pixel, not the index.
    assert stored.convert("RGBA").getpixel((0, 0))[3] == 0
