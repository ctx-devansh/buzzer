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
import math
from dataclasses import dataclass

from PIL import Image as PILImage
from PIL import ImageOps
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.concurrency import run_in_threadpool

from ..common.exceptions import (
    BuzzerError,
    ConflictError,
    NotFoundError,
    ValidationFailedError,
)
from ..models.game import Game, Question
from ..models.image import Image
from ..models.session import SessionScore
from ..schemas.admin import is_image_id, validate_pin_the_spot

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
        "version",  # GIF87a / GIF89a
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
    elif fmt == "GIF":
        img.save(buf, "GIF")
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
    it is clean, and otherwise turned upright and re-encoded without metadata. A static
    GIF goes through the same allowlist (it can carry comments and XMP).
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
    if animated or _is_clean(img):
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


# ---------------------------------------------------------------------------
# Pin the Spot radius clamp (replace step 4)
# ---------------------------------------------------------------------------


def clamp_radii(answer_data: dict, width: int, height: int) -> dict:
    """
    Fit a pin_the_spot answer_data to a new image size: r_zero to the new diagonal
    (rounded down to 2 dp, as the editor's slider maximum), then r_full at least
    0.01 below it (the editor's gap). A question without a target is returned as is.
    """
    if not answer_data:
        return answer_data
    cap = math.floor(math.hypot(1.0, height / width) * 100) / 100
    r_zero = min(answer_data["r_zero"], cap)
    r_full = min(answer_data["r_full"], round(r_zero - 0.01, 10))
    return {**answer_data, "r_full": r_full, "r_zero": r_zero}


# ---------------------------------------------------------------------------
# References and where-used
# ---------------------------------------------------------------------------


def question_image_refs(
    q_type: str, prompt_image_id: str | None, config: dict | None
) -> list[tuple[str, str, str]]:
    """Every (field, image_id, role) a question refers to, in field order."""
    config = config if isinstance(config, dict) else {}
    refs: list[tuple[str, str, str]] = []
    if prompt_image_id:
        refs.append(("prompt_image_id", prompt_image_id, "prompt"))
    if q_type in ("multiple_choice", "multi_select"):
        option_ids = config.get("option_image_ids")
        for i, image_id in enumerate(
            option_ids if isinstance(option_ids, list) else []
        ):
            if isinstance(image_id, str):
                refs.append((f"option_image_ids[{i}]", image_id, "option"))
    if q_type == "pin_the_spot" and isinstance(config.get("image_id"), str):
        refs.append(("image_id", config["image_id"], "canvas"))
    return refs


_ROLE_ORDER = ("prompt", "option", "canvas")


async def usage_map(db: AsyncSession, course_id: int) -> dict[str, list[dict]]:
    """
    One scan of the course's questions: image id → one entry per using question,
    {game_id, game_title, question_id, order_index, question_number, roles,
    answer_count}. question_number is the 1-based position in its game, as the editor
    numbers questions: order_index can have gaps (a delete doesn't renumber). There is
    no link table (design A4); answer counts come from one grouped query.
    """
    rows = (
        await db.execute(
            select(
                Question.id,
                Question.type,
                Question.prompt_image_id,
                Question.config,
                Question.order_index,
                Game.id,
                Game.title,
            )
            .join(Game, Question.game_id == Game.id)
            .where(Game.course_id == course_id)
            .order_by(Game.title, Game.id, Question.order_index)
        )
    ).all()

    per_question: list[tuple[tuple, dict[str, set[str]]]] = []
    position: dict[int, int] = {}
    for q_id, q_type, prompt_id, config, order_index, game_id, title in rows:
        # Rows come ordered by game, then order_index, so this counts positions.
        position[game_id] = number = position.get(game_id, 0) + 1
        roles: dict[str, set[str]] = {}
        for _field, image_id, role in question_image_refs(q_type, prompt_id, config):
            roles.setdefault(image_id, set()).add(role)
        if roles:
            per_question.append(((q_id, order_index, number, game_id, title), roles))

    counts: dict[int, int] = {}
    used_ids = [info[0] for info, _ in per_question]
    if used_ids:
        counts = dict(
            (
                await db.execute(
                    select(SessionScore.question_id, func.count())
                    .where(SessionScore.question_id.in_(used_ids))
                    .group_by(SessionScore.question_id)
                )
            ).all()
        )

    usage: dict[str, list[dict]] = {}
    for (q_id, order_index, number, game_id, title), roles in per_question:
        for image_id, image_roles in roles.items():
            usage.setdefault(image_id, []).append(
                {
                    "game_id": game_id,
                    "game_title": title,
                    "question_id": q_id,
                    "order_index": order_index,
                    "question_number": number,
                    "roles": [r for r in _ROLE_ORDER if r in image_roles],
                    "answer_count": counts.get(q_id, 0),
                }
            )
    return usage


async def where_used(db: AsyncSession, course_id: int, image_id: str) -> list[dict]:
    return (await usage_map(db, course_id)).get(image_id, [])


async def validate_question_images(
    db: AsyncSession,
    game: Game,
    prompt_image_id: str | None,
    q_type: str,
    config: dict | None,
) -> dict:
    """
    The ownership rule (design 3.4): every image a question refers to exists and
    belongs to the question's game's course. Raises a 422 naming the field. Returns
    the config to store, always a new dict: for pin_the_spot with image_id,
    image_width/image_height are overwritten with the image row's measured size.
    Call after validate_image_keys.
    """
    if not isinstance(config, dict):
        # Not ours to judge (legacy or malformed shapes keep their old update path);
        # it can hold no image reference, so only a prompt image is checked below.
        config_out: object = config
        config = {}
    else:
        config = config_out = dict(config)
    refs = question_image_refs(q_type, prompt_image_id, config)
    if not refs:
        return config_out
    if game.course_id is None:
        raise ValidationFailedError(
            f"{refs[0][0]}: images can only be used in a game attached to a course"
        )
    rows = {
        row.id: row
        for row in (
            await db.execute(
                select(Image.id, Image.course_id, Image.width, Image.height).where(
                    Image.id.in_({image_id for _, image_id, _ in refs})
                )
            )
        ).all()
    }
    for field, image_id, _role in refs:
        row = rows.get(image_id)
        if row is None or row.course_id != game.course_id:
            raise ValidationFailedError(f"{field}: image not found in this course")
    if q_type == "pin_the_spot" and "image_id" in config:
        row = rows[config["image_id"]]
        config["image_width"], config["image_height"] = row.width, row.height
    return config_out


def _is_played_canvas(use: dict) -> bool:
    return "canvas" in use["roles"] and use["answer_count"] > 0


def image_response(img: Image, uses: list[dict]) -> dict:
    uploader = img.uploader
    return {
        "id": img.id,
        "course_id": img.course_id,
        "filename": img.filename,
        "content_type": img.content_type,
        "width": img.width,
        "height": img.height,
        "byte_size": img.byte_size,
        "uploaded_by_name": (
            (uploader.display_name or uploader.username) if uploader else None
        ),
        "created_at": img.created_at,
        "updated_at": img.updated_at,
        "url": f"/api/images/{img.id}",
        "used_by": [
            {
                **{k: v for k, v in use.items() if k != "answer_count"},
                "played": use["answer_count"] > 0,
            }
            for use in uses
        ],
    }


def describe_uses(uses: list[dict]) -> str:
    """'Party Night, question 3 (option); …' for up to five uses, then a count."""
    parts = [
        f"{u['game_title']}, question {u['question_number']} ({', '.join(u['roles'])})"
        for u in uses[:5]
    ]
    more = len(uses) - len(parts)
    text = "; ".join(parts)
    return f"{text}; and {more} more" if more else text


# ---------------------------------------------------------------------------
# Library operations (callers authorise the course first)
# ---------------------------------------------------------------------------


def http_error(exc: ImageRejected) -> BuzzerError:
    if isinstance(exc, ImageTooLarge):
        return BuzzerError("PAYLOAD_TOO_LARGE", str(exc), 413)
    return ValidationFailedError(str(exc))


async def process_upload_async(raw: bytes) -> ProcessedImage:
    """process_upload in a worker thread: it is CPU-bound, and this process also
    serves every live game's Socket.IO traffic (design 4.1, "Off the event loop")."""
    return await run_in_threadpool(process_upload, raw)


async def _process_or_raise(raw: bytes) -> ProcessedImage:
    try:
        return await process_upload_async(raw)
    except ImageRejected as exc:
        raise http_error(exc) from exc


def clean_filename(filename: str | None) -> str:
    name = (filename or "").replace("\\", "/").rsplit("/", 1)[-1].strip()
    return (name or "image")[:255]


async def get_image_in_course(db: AsyncSession, course_id: int, image_id: str) -> Image:
    """404 for an unknown or malformed id, and for another course's image."""
    img = await db.get(Image, image_id) if is_image_id(image_id) else None
    if img is None or img.course_id != course_id:
        raise NotFoundError("Image not found in this course")
    return img


async def list_images(db: AsyncSession, course_id: int) -> list[dict]:
    images = (
        await db.execute(
            select(Image)
            .where(Image.course_id == course_id)
            .order_by(Image.created_at.desc(), Image.id)
        )
    ).scalars()
    usage = await usage_map(db, course_id)
    return [image_response(img, usage.get(img.id, [])) for img in images]


async def get_image(db: AsyncSession, course_id: int, image_id: str) -> dict:
    img = await get_image_in_course(db, course_id, image_id)
    return image_response(img, await where_used(db, course_id, image_id))


def new_image_row(
    course_id: int, uploaded_by: str | None, filename: str | None, p: ProcessedImage
) -> Image:
    return Image(
        course_id=course_id,
        uploaded_by=uploaded_by,
        filename=clean_filename(filename),
        content_type=p.content_type,
        width=p.width,
        height=p.height,
        byte_size=p.byte_size,
        sha256=p.sha256,
        data=p.data,
    )


async def upload_image(
    db: AsyncSession, course_id: int, user_id: str, filename: str | None, raw: bytes
) -> dict:
    img = new_image_row(course_id, user_id, filename, await _process_or_raise(raw))
    db.add(img)
    # Commit here, not in get_db (which commits after the response is sent): the
    # library page reloads the list as soon as this returns (mean review R10).
    await db.commit()
    await db.refresh(img, ["created_at", "updated_at", "uploader"])
    return image_response(img, [])


async def replace_image(
    db: AsyncSession,
    course_id: int,
    image_id: str,
    user_id: str,
    filename: str | None,
    raw: bytes,
) -> dict:
    """
    Replace the bytes, keeping the id (design 4.3, replace rules). 409 if the image
    is the canvas of a played pin_the_spot question; unplayed canvases get the new
    size, with radii clamped to the new diagonal.
    """
    img = await get_image_in_course(db, course_id, image_id)
    processed = await _process_or_raise(raw)
    uses = await where_used(db, course_id, image_id)
    if any(_is_played_canvas(u) for u in uses):
        raise ConflictError(
            "This image is the canvas of a Pin the Spot question that has been "
            "played, so it can't be replaced. Upload it as a new image instead."
        )

    size_changed = (img.width, img.height) != (processed.width, processed.height)
    img.data = processed.data
    img.content_type = processed.content_type
    img.width = processed.width
    img.height = processed.height
    img.byte_size = processed.byte_size
    img.sha256 = processed.sha256
    img.filename = clean_filename(filename)
    img.uploaded_by = user_id
    img.updated_at = func.now()

    resized: list[int] = []
    clamped: list[int] = []
    canvas_ids = [u["question_id"] for u in uses if "canvas" in u["roles"]]
    if size_changed and canvas_ids:
        questions = (
            await db.execute(select(Question).where(Question.id.in_(canvas_ids)))
        ).scalars()
        for q in questions:
            # New dicts, never in-place edits: SQLAlchemy doesn't track changes
            # inside a JSON column (design 3.3, "Writing config").
            config = {
                **q.config,
                "image_width": processed.width,
                "image_height": processed.height,
            }
            answer_data = clamp_radii(
                q.answer_data or {}, processed.width, processed.height
            )
            # Backstop: clamp_radii must leave every question valid.
            validate_pin_the_spot(q.grading_type, config, answer_data)
            q.config = config
            resized.append(q.id)
            if answer_data != (q.answer_data or {}):
                q.answer_data = answer_data
                clamped.append(q.id)

    # Commit before responding: the library page reloads right after the 200, and
    # get_db would commit only after the response (mean review R10).
    await db.commit()
    await db.refresh(img, ["updated_at", "uploader"])
    return {
        **image_response(img, uses),
        "size_changed": size_changed,
        "resized_question_ids": resized,
        "clamped_question_ids": clamped,
    }


async def delete_image(db: AsyncSession, course_id: int, image_id: str) -> None:
    img = await get_image_in_course(db, course_id, image_id)
    uses = await where_used(db, course_id, image_id)
    if uses:
        raise ConflictError(
            f"This image is used in {len(uses)} question(s), so it can't be deleted: "
            + describe_uses(uses)
        )
    await db.delete(img)
    # Commit here, not in get_db (which commits after the 204): a prompt reference
    # added since the scan is caught by the FK and must be a 409, not a silent
    # failure, and the page's reload must not still see the row (mean review R10).
    try:
        await db.commit()
    except IntegrityError as exc:
        raise ConflictError(
            "This image was just used by a question. Reload the library to see where."
        ) from exc


async def read_image_head(db: AsyncSession, image_id: str):
    """The public GET's first query: (content_type, byte_size, sha256), no bytes."""
    return (
        await db.execute(
            select(Image.content_type, Image.byte_size, Image.sha256).where(
                Image.id == image_id
            )
        )
    ).one_or_none()


async def read_image_data(db: AsyncSession, image_id: str):
    """
    The public GET's second query, only for a 200: (content_type, sha256, data).
    The type and hash come back with the bytes, so a replace between the two
    queries can't pair new bytes with the old ETag.
    """
    return (
        await db.execute(
            select(Image.content_type, Image.sha256, Image.data).where(
                Image.id == image_id
            )
        )
    ).one_or_none()
