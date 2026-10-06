"""
Game/question authoring logic shared by routers/admin.py (/admin/*) and
routers/host.py (/host/*).

Each function assumes the caller has already authorised the request — the two
routers differ only in their gate (require_admin vs. assert_host_can_use_*), so
everything past the gate lives here rather than being copied into both.
"""

from __future__ import annotations

import base64
import binascii
import json

import bleach
import structlog
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import undefer

from ..common.exceptions import ConflictError, NotFoundError, ValidationFailedError
from ..models.game import Game, Question
from ..models.image import Image
from ..models.session import SessionScore
from ..schemas.admin import (
    GameCreate,
    QuestionCreate,
    QuestionUpdate,
    validate_image_keys,
    validate_pin_the_spot,
    validate_put_in_order,
)
from . import image_service
from .image_service import ImageRejected, ProcessedImage

logger = structlog.get_logger()

# Version 1: no library images. Version 2 (T8): a top-level "images" array and a
# per-question prompt_image_id. Export writes 2 only when some question uses an image.
SUPPORTED_IMPORT_VERSION = frozenset({1, 2})

_PROMPT_TAGS = ["b", "i", "br", "u"]


class BundleError(ValueError):
    """An uploaded game bundle failed validation. Routers map this to a 422 `detail`."""


def sanitize_prompt(prompt: str) -> str:
    """Strip prompt HTML down to the allowed inline tags before it reaches the DB."""
    return bleach.clean(prompt, tags=_PROMPT_TAGS, attributes={}, strip=True)


# ---------------------------------------------------------------------------
# Questions
# ---------------------------------------------------------------------------


async def list_questions(db: AsyncSession, game_id: int) -> list[Question]:
    result = await db.execute(
        select(Question)
        .where(Question.game_id == game_id)
        .order_by(Question.order_index)
    )
    return list(result.scalars().all())


async def create_question(
    db: AsyncSession, game_id: int, body: QuestionCreate
) -> Question:
    # Auto-assign order_index if not specified
    if body.order_index is None:
        result = await db.execute(
            select(Question.order_index)
            .where(Question.game_id == game_id)
            .order_by(Question.order_index.desc())
            .limit(1)
        )
        max_idx = result.scalar_one_or_none()
        order_index = (max_idx + 1) if max_idx is not None else 0
    else:
        order_index = body.order_index

    config = await _checked_image_config(
        db, game_id, body.prompt_image_id, body.type, body.config
    )
    if body.type == "pin_the_spot" and "image_id" in config:
        # QuestionCreate checked the radii against the client's size; the server has
        # just replaced it with the image's, so check again (design 4.1).
        try:
            validate_pin_the_spot(body.grading_type, config, body.answer_data)
        except ValueError as exc:
            raise ValidationFailedError(str(exc)) from exc

    question = Question(
        game_id=game_id,
        type=body.type,
        grading_type=body.grading_type,
        prompt=sanitize_prompt(body.prompt),
        prompt_image_id=body.prompt_image_id,
        config=config,
        answer_data=body.answer_data,
        time_limit_seconds=body.time_limit_seconds,
        points_value=body.points_value,
        order_index=order_index,
    )
    db.add(question)
    await db.flush()
    await db.refresh(question)
    await db.commit()
    return question


async def _checked_image_config(
    db: AsyncSession,
    game_id: int,
    prompt_image_id: str | None,
    q_type: str,
    config: dict | None,
) -> dict:
    """image_service.validate_question_images for a game id: the config to store."""
    game = await db.get(Game, game_id)
    if game is None:
        raise NotFoundError(f"Game {game_id} not found")
    return await image_service.validate_question_images(
        db, game, prompt_image_id, q_type, config
    )


async def _get_question_in_game(
    db: AsyncSession, game_id: int, question_id: int
) -> Question:
    result = await db.execute(
        select(Question).where(Question.id == question_id, Question.game_id == game_id)
    )
    question = result.scalar_one_or_none()
    if not question:
        raise NotFoundError(f"Question {question_id} not found in game {game_id}")
    return question


async def _score_count(db: AsyncSession, question_id: int) -> int:
    result = await db.execute(
        select(func.count())
        .select_from(SessionScore)
        .where(SessionScore.question_id == question_id)
    )
    return result.scalar_one()


async def update_question(
    db: AsyncSession, game_id: int, question_id: int, body: QuestionUpdate
) -> Question:
    """
    Apply a partial update. For put_in_order (stored or requested type) the merged values
    are checked before anything is assigned: a played question's items, correct_order and
    type are frozen (409), because stored orderedIndices point into config.items as it was
    at play time; then the merged question must pass validate_put_in_order (422).
    pin_the_spot follows the same shape: a played question's config (the image) and type
    are frozen (409), then validate_pin_the_spot must pass (422).

    Image references (T8) are checked first, for every type, right after the merge:
    validate_image_keys, then validate_question_images, which also overwrites a
    pin_the_spot image_id's size, so a stale size can't cause a false 409. An image
    error is therefore always a 422 that comes before any guard's 409. Leaving
    prompt_image_id out keeps the stored value; an explicit null clears it.
    """
    question = await _get_question_in_game(db, game_id, question_id)

    new_type = body.type if body.type is not None else question.type
    new_grading_type = (
        body.grading_type if body.grading_type is not None else question.grading_type
    )
    old_config = question.config or {}
    old_answer_data = question.answer_data or {}
    new_config = (body.config if body.config is not None else old_config) or {}
    new_answer_data = (
        body.answer_data if body.answer_data is not None else old_answer_data
    ) or {}
    new_prompt_image_id = (
        body.prompt_image_id
        if "prompt_image_id" in body.model_fields_set
        else question.prompt_image_id
    )

    try:
        validate_image_keys(new_type, new_prompt_image_id, new_config)
    except ValueError as exc:
        raise ValidationFailedError(str(exc)) from exc
    new_config = await _checked_image_config(
        db, game_id, new_prompt_image_id, new_type, new_config
    )

    if question.type == "put_in_order" or new_type == "put_in_order":
        frozen_changed = (
            new_type != question.type
            or new_config.get("items") != old_config.get("items")
            or new_answer_data.get("correct_order")
            != old_answer_data.get("correct_order")
        )
        if frozen_changed and await _score_count(db, question_id):
            raise ConflictError(
                "This question has recorded answers from a past session, so its items "
                "cannot be changed. Create a new question instead."
            )

    if question.type == "pin_the_spot" or new_type == "pin_the_spot":
        # Only the image (and type) is frozen: stored taps are fractions of that image.
        # Target, radii and grading type stay editable, with no rescoring.
        frozen_changed = new_type != question.type or new_config != old_config
        if frozen_changed and await _score_count(db, question_id):
            raise ConflictError(
                "This question has recorded answers from a past session, so its image "
                "cannot be changed. Create a new question instead."
            )

    if new_type == "put_in_order":
        try:
            validate_put_in_order(new_grading_type, new_config, new_answer_data)
        except ValueError as exc:
            raise ValidationFailedError(str(exc)) from exc
    if new_type == "pin_the_spot":
        try:
            validate_pin_the_spot(new_grading_type, new_config, new_answer_data)
        except ValueError as exc:
            raise ValidationFailedError(str(exc)) from exc

    if body.type is not None:
        question.type = body.type
    if body.grading_type is not None:
        question.grading_type = body.grading_type
    if body.prompt is not None:
        question.prompt = sanitize_prompt(body.prompt)
    if "prompt_image_id" in body.model_fields_set:
        question.prompt_image_id = body.prompt_image_id
    if body.config is not None or new_config != old_config:
        # A new dict, never an in-place edit (design 3.3, "Writing config").
        question.config = new_config
    if body.answer_data is not None:
        question.answer_data = body.answer_data
    if body.time_limit_seconds is not None:
        question.time_limit_seconds = body.time_limit_seconds
    if body.points_value is not None:
        question.points_value = body.points_value
    if body.order_index is not None:
        question.order_index = body.order_index
    return question


async def delete_question(db: AsyncSession, game_id: int, question_id: int) -> None:
    """
    Delete an unplayed question. A question with recorded scores is a 409:
    session_scores.question_id is NOT NULL with no ON DELETE, and those rows are
    grade data, so they are neither nulled nor cascaded away.
    """
    question = await _get_question_in_game(db, game_id, question_id)
    if await _score_count(db, question_id):
        raise ConflictError(
            "This question has recorded answers from a past session, so it cannot "
            "be deleted"
        )
    await db.delete(question)
    # Flush here, not in get_db: get_db commits only after the 204 is sent, so a
    # score recorded between the check above and the commit would otherwise be a
    # silent failure that the client saw as success.
    try:
        await db.flush()
    except IntegrityError as exc:
        raise ConflictError(
            "This question has recorded answers and cannot be deleted"
        ) from exc


async def reorder_questions(db: AsyncSession, game_id: int, order: list[int]) -> None:
    result = await db.execute(select(Question).where(Question.game_id == game_id))
    questions = {q.id: q for q in result.scalars().all()}

    if set(order) != set(questions.keys()):
        raise ConflictError(
            "order list must contain exactly the IDs of all questions in this game"
        )

    for idx, qid in enumerate(order):
        questions[qid].order_index = idx


# ---------------------------------------------------------------------------
# Game export / import (buzzer/game bundle, version 1)
# ---------------------------------------------------------------------------


def _question_refs(q) -> list[tuple[str, str, str]]:
    return image_service.question_image_refs(q.type, q.prompt_image_id, q.config)


async def build_export_bundle(db: AsyncSession, game: Game) -> tuple[str, bytes]:
    """
    Return (filename, JSON bytes). The bundle never carries course_id. A game whose
    questions use no library image exports exactly as before (version 1); otherwise
    version 2 embeds each referenced image once, base64-encoded. A reference to a
    deleted image (the accepted delete race) is a 409, never a file that can't be
    re-imported.
    """
    questions = await list_questions(db, game.id)
    image_ids = list(
        dict.fromkeys(
            image_id for q in questions for _, image_id, _ in _question_refs(q)
        )
    )

    bundle: dict = {
        "format": "buzzer/game",
        "version": 2 if image_ids else 1,
        "game": {
            "title": game.title,
            "description": game.description,
            "max_players": game.max_players,
        },
        "questions": [],
    }
    for q in questions:
        entry = {
            "type": q.type,
            "grading_type": q.grading_type,
            "prompt": q.prompt,
            "config": q.config,
            "answer_data": q.answer_data,
            "time_limit_seconds": q.time_limit_seconds,
            "points_value": q.points_value,
        }
        if image_ids:
            entry["prompt_image_id"] = q.prompt_image_id
        bundle["questions"].append(entry)

    if image_ids:
        rows = {
            img.id: img
            for img in (
                await db.execute(
                    select(Image)
                    .options(undefer(Image.data))
                    .where(Image.id.in_(image_ids))
                )
            ).scalars()
        }
        for q in questions:
            if any(image_id not in rows for _, image_id, _ in _question_refs(q)):
                raise ConflictError(
                    f"Question {q.order_index + 1} refers to an image that was "
                    "deleted; re-pick or remove it before exporting"
                )
        bundle["images"] = [
            {
                "id": img.id,
                "filename": img.filename,
                "content_type": img.content_type,
                "width": img.width,
                "height": img.height,
                "sha256": img.sha256,
                "data_base64": base64.b64encode(img.data).decode("ascii"),
            }
            for img in (rows[i] for i in image_ids)
        ]

    # ASCII only: header values are latin-1, and str.isalnum() accepts CJK letters,
    # which would make the response a 500. The bundle itself keeps the real title.
    safe_title = "".join(
        c if (c.isascii() and c.isalnum()) or c in " _-" else "_" for c in game.title
    ).strip(" _")
    filename = f"{safe_title or 'game'}.json"
    content = json.dumps(bundle, indent=2, ensure_ascii=False).encode()
    return filename, content


async def _check_bundle_images(
    images_raw: object,
) -> dict[str, tuple[str, ProcessedImage]]:
    """
    Version 2 step 1: every entry, used or not, decodes and passes process_upload
    (the file's width, height and sha256 are ignored and recomputed). One worker
    thread at a time, so a large import never occupies more than one.
    """
    if not isinstance(images_raw, list):
        raise BundleError("Invalid images: 'images' must be a list")
    checked: dict[str, tuple[str, ProcessedImage]] = {}
    for i, entry in enumerate(images_raw):
        if not isinstance(entry, dict) or not isinstance(entry.get("id"), str):
            raise BundleError(f"Image {i + 1} invalid: needs a string 'id'")
        if entry["id"] in checked:
            raise BundleError(f"Image {i + 1} invalid: duplicate id {entry['id']!r}")
        try:
            raw = base64.b64decode(entry.get("data_base64") or "", validate=True)
            processed = await image_service.process_upload_async(raw)
        except (binascii.Error, ImageRejected) as exc:
            raise BundleError(f"Image {i + 1} invalid: {exc}") from exc
        filename = entry.get("filename")
        checked[entry["id"]] = (
            filename if isinstance(filename, str) else "",
            processed,
        )
    return checked


def _has_image_key(q: object) -> bool:
    if not isinstance(q, dict):
        return False
    config = q.get("config")
    config = config if isinstance(config, dict) else {}
    return (
        q.get("prompt_image_id") is not None
        or "option_image_ids" in config
        or "image_id" in config
    )


def _remap(q: QuestionCreate, id_map: dict[str, str]) -> QuestionCreate:
    """Rewrite a validated question's image references (file id → course id) into
    a new config dict, never an in-place edit."""
    config = dict(q.config)
    if q.type in ("multiple_choice", "multi_select") and isinstance(
        config.get("option_image_ids"), list
    ):
        config["option_image_ids"] = [
            id_map[i] if i is not None else None for i in config["option_image_ids"]
        ]
    if q.type == "pin_the_spot" and "image_id" in config:
        config["image_id"] = id_map[config["image_id"]]
    prompt_image_id = id_map[q.prompt_image_id] if q.prompt_image_id else None
    return q.model_copy(update={"config": config, "prompt_image_id": prompt_image_id})


async def _import_images(
    db: AsyncSession,
    course_id: int,
    uploaded_by: str | None,
    checked: dict[str, tuple[str, ProcessedImage]],
    used: list[str],
) -> dict[str, str]:
    """
    Version 2 step 3: for each used entry, reuse the course's oldest image with the
    same processed sha256, or insert a new row. Returns file id → course image id.
    """
    id_map: dict[str, str] = {}
    for file_id in dict.fromkeys(used):
        filename, processed = checked[file_id]
        existing = (
            await db.execute(
                select(Image.id)
                .where(Image.course_id == course_id, Image.sha256 == processed.sha256)
                .order_by(Image.created_at, Image.id)
                .limit(1)
            )
        ).scalar_one_or_none()
        if existing is None:
            img = image_service.new_image_row(
                course_id, uploaded_by, filename, processed
            )
            db.add(img)
            await db.flush()
            existing = img.id
        id_map[file_id] = existing
    return id_map


async def import_game_bundle(
    db: AsyncSession,
    raw: bytes,
    course_id: int | None,
    uploaded_by: str | None = None,
) -> Game:
    """
    Validate and import a buzzer/game bundle. The game's course comes only from the
    `course_id` argument (the host route's form field); any course_id in the file is
    discarded, so a hand-edited bundle cannot attach a game to a course the uploader
    may not host. The admin route passes None (the game lands unattached), so a
    version 2 file with images is refused here, before any image is processed.

    Version 2 images are all checked first, then the referenced ones are reused by
    sha256 within the course or inserted, and the questions' references rewritten to
    the course's ids. Nothing is committed here: a BundleError propagates through the
    router, and get_db rolls everything back, flushed rows included.
    """
    try:
        bundle = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise BundleError(f"Invalid JSON: {exc}") from exc

    if not isinstance(bundle, dict) or bundle.get("format") != "buzzer/game":
        raise BundleError("Unrecognised file format")
    version = bundle.get("version")
    if type(version) is not int or version not in SUPPORTED_IMPORT_VERSION:
        raise BundleError(
            f"Unsupported version {version!r}; server supports versions 1 and 2"
        )

    game_data = bundle.get("game", {})
    if not isinstance(game_data, dict):
        raise BundleError("Invalid game metadata: 'game' must be an object")
    game_data = {k: v for k, v in game_data.items() if k != "course_id"}
    try:
        game_meta = GameCreate(**game_data)
    except Exception as exc:
        raise BundleError(f"Invalid game metadata: {exc}") from exc

    questions_raw = bundle.get("questions", [])
    if not isinstance(questions_raw, list):
        raise BundleError("Invalid questions: 'questions' must be a list")

    checked_images: dict[str, tuple[str, ProcessedImage]] = {}
    if version == 1:
        for i, q in enumerate(questions_raw):
            if _has_image_key(q):
                raise BundleError(
                    f"Question {i + 1} invalid: image references need a version 2 file"
                )
    else:
        images_raw = bundle.get("images", [])
        if images_raw and course_id is None:
            raise BundleError(
                "A game with images must be imported into a course; use the host "
                "app's import"
            )
        checked_images = await _check_bundle_images(images_raw)

    validated_questions: list[QuestionCreate] = []
    for i, q in enumerate(questions_raw):
        try:
            validated_questions.append(QuestionCreate(**q))
        except Exception as exc:
            raise BundleError(f"Question {i + 1} invalid: {exc}") from exc

    used: list[str] = []
    for i, q in enumerate(validated_questions):
        for _field, image_id, _role in _question_refs(q):
            if image_id not in checked_images:
                raise BundleError(
                    f"Question {i + 1} invalid: unknown image id {image_id!r}"
                )
            used.append(image_id)
    id_map: dict[str, str] = {}
    if used:
        id_map = await _import_images(db, course_id, uploaded_by, checked_images, used)

    game = Game(
        title=game_meta.title,
        description=game_meta.description,
        max_players=game_meta.max_players,
        course_id=course_id,
    )
    db.add(game)
    await db.flush()

    for idx, q in enumerate(validated_questions):
        q = _remap(q, id_map)
        try:
            config = await image_service.validate_question_images(
                db, game, q.prompt_image_id, q.type, q.config
            )
            if q.type == "pin_the_spot" and "image_id" in config:
                validate_pin_the_spot(q.grading_type, config, q.answer_data)
        except (ValidationFailedError, ValueError) as exc:
            message = exc.message if isinstance(exc, ValidationFailedError) else exc
            raise BundleError(f"Question {idx + 1} invalid: {message}") from exc
        db.add(
            Question(
                game_id=game.id,
                type=q.type,
                grading_type=q.grading_type,
                prompt=sanitize_prompt(q.prompt),
                prompt_image_id=q.prompt_image_id,
                config=config,
                answer_data=q.answer_data,
                time_limit_seconds=q.time_limit_seconds,
                points_value=q.points_value,
                order_index=idx,
            )
        )

    logger.info(
        "game_imported",
        game_id=game.id,
        title=game.title,
        course_id=course_id,
        question_count=len(validated_questions),
        images_reused_or_added=len(id_map),
    )
    return game
