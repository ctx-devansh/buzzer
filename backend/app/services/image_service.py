"""
Course image library (T8, docs/design-image-support.md).

`process_upload` is the single gate every stored image passes through (upload,
replace and import): it decides the format from the bytes, strips metadata, and is
idempotent, so an exported image re-imports byte for byte with the same sha256.
It is CPU-bound, so async callers run it with `run_in_threadpool`.
"""

from __future__ import annotations

import hashlib
import io
from dataclasses import dataclass

from PIL import Image as PILImage
from PIL import ImageOps

MAX_UPLOAD_BYTES = 5_000_000
MAX_IMAGE_SIDE = 20_000
MAX_IMAGE_PIXELS = 40_000_000

CONTENT_TYPES = {
    "PNG": "image/png",
    "JPEG": "image/jpeg",
    "GIF": "image/gif",
    "WEBP": "image/webp",
}

# `info` keys that are format and colour facts only. Anything else (exif, xmp,
# comment, icc_profile, photoshop/IPTC, PNG text chunks, keys nobody thought of)
# makes an image unclean, so it is re-encoded. Every key Pillow writes on re-encode
# must be in here, or process_upload stops being idempotent (the unit tests check).
CLEAN_INFO_KEYS = frozenset(
    {
        "jfif",
        "jfif_version",
        "jfif_unit",
        "jfif_density",
        "dpi",
        "progressive",
        "progression",
        "adobe",
        "adobe_transform",
        "gamma",
        "srgb",
        "chromaticity",
        "aspect",
        "transparency",
        "interlace",
        "loop",
        "background",
        "duration",
        "timestamp",
    }
)

# JPEG APP segments that carry no metadata: APP0 JFIF and APP14 Adobe (colour
# transform). APP1 (EXIF/XMP), APP2 (ICC), APP13 (IPTC) and the rest are unclean.
_CLEAN_JPEG_APP = {("APP0", b"JFIF"), ("APP14", b"Adobe")}

_UNSUPPORTED = "Not a supported image; use PNG, JPEG, GIF or WebP"


class ImageRejected(ValueError):
    """The bytes aren't an acceptable image. Routers map this to 422."""


class ImageTooLarge(ImageRejected):
    """Over MAX_UPLOAD_BYTES. Routers map this to 413."""


@dataclass(frozen=True)
class ProcessedImage:
    content_type: str
    width: int
    height: int
    data: bytes
    byte_size: int
    sha256: str


def _is_clean(img: PILImage.Image) -> bool:
    if img.getexif() or not set(img.info) <= CLEAN_INFO_KEYS:
        return False
    if img.format == "JPEG":
        for marker, payload in getattr(img, "applist", []):
            if not any(
                marker == m and payload.startswith(p) for m, p in _CLEAN_JPEG_APP
            ):
                return False
    return True


def _reencode(img: PILImage.Image, fmt: str) -> bytes:
    img = ImageOps.exif_transpose(img)
    # Pillow's savers copy some metadata (PNG icc_profile, JPEG comment) from
    # img.info; keep only what the pixels need.
    img.info = {k: v for k, v in img.info.items() if k == "transparency"}
    buf = io.BytesIO()
    if fmt == "JPEG":
        if img.mode not in ("RGB", "L", "CMYK"):
            img = img.convert("RGB")
        img.save(buf, "JPEG", quality=90)
    elif fmt == "PNG":
        img.save(buf, "PNG", optimize=True)
    else:
        img.save(buf, "WEBP", quality=90)
    return buf.getvalue()


def process_upload(raw: bytes) -> ProcessedImage:
    """
    Validate raw image bytes and return what to store. Pure: no database, no I/O.

    The format is the one Pillow detects, never a client's Content-Type or file
    extension (SVG can't be decoded, so it is impossible). Animated images and static
    GIFs are stored byte for byte; a static PNG/JPEG/WebP is stored byte for byte when
    it is clean, and otherwise turned upright and re-encoded without metadata.
    Contract: process_upload(process_upload(x).data).data == process_upload(x).data.
    """
    if not raw:
        raise ImageRejected("The file is empty")
    if len(raw) > MAX_UPLOAD_BYTES:
        raise ImageTooLarge("Image is too large; the limit is 5 MB")

    try:
        # open() reads only the header, so the pixel limit is checked before any
        # decode. Pillow's global MAX_IMAGE_PIXELS is left alone, and its warning is
        # not turned into an error: warnings filters aren't thread-safe, and this
        # runs in a worker thread.
        with PILImage.open(io.BytesIO(raw)) as probe:
            fmt = probe.format
            width, height = probe.size
            if width * height > MAX_IMAGE_PIXELS:
                raise ImageRejected("Image has too many pixels (limit 40 megapixels)")
            probe.verify()
        img = PILImage.open(io.BytesIO(raw))
        img.load()
    except ImageRejected:
        raise
    except PILImage.DecompressionBombError:
        raise ImageRejected("Image has too many pixels (limit 40 megapixels)") from None
    except Exception:
        raise ImageRejected(_UNSUPPORTED) from None

    if fmt not in CONTENT_TYPES:
        raise ImageRejected(_UNSUPPORTED)
    if not all(1 <= side <= MAX_IMAGE_SIDE for side in img.size):
        raise ImageRejected("Image width and height must be from 1 to 20000 pixels")

    animated = getattr(img, "n_frames", 1) > 1
    if animated or fmt == "GIF" or _is_clean(img):
        data = raw
    else:
        data = _reencode(img, fmt)

    with PILImage.open(io.BytesIO(data)) as stored:
        width, height = stored.size
    return ProcessedImage(
        content_type=CONTENT_TYPES[fmt],
        width=width,
        height=height,
        data=data,
        byte_size=len(data),
        sha256=hashlib.sha256(data).hexdigest(),
    )
