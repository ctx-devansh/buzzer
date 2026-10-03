"""
Game/question authoring logic shared by routers/admin.py (/admin/*) and
routers/host.py (/host/*).

Each function assumes the caller has already authorised the request — the two
routers differ only in their gate (require_admin vs. assert_host_can_use_*), so
everything past the gate lives here rather than being copied into both.
"""

from __future__ import annotations

import json

import bleach
import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..common.exceptions import ConflictError, NotFoundError
from ..models.game import Game, Question
from ..schemas.admin import GameCreate, QuestionCreate, QuestionUpdate

logger = structlog.get_logger()

SUPPORTED_IMPORT_VERSION = 1

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

    question = Question(
        game_id=game_id,
        type=body.type,
        grading_type=body.grading_type,
        prompt=sanitize_prompt(body.prompt),
        config=body.config,
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


async def update_question(
    db: AsyncSession, game_id: int, question_id: int, body: QuestionUpdate
) -> Question:
    question = await _get_question_in_game(db, game_id, question_id)

    if body.type is not None:
        question.type = body.type
    if body.grading_type is not None:
        question.grading_type = body.grading_type
    if body.prompt is not None:
        question.prompt = sanitize_prompt(body.prompt)
    if body.config is not None:
        question.config = body.config
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
    question = await _get_question_in_game(db, game_id, question_id)
    await db.delete(question)


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


async def build_export_bundle(db: AsyncSession, game: Game) -> tuple[str, bytes]:
    """Return (filename, JSON bytes). The bundle never carries course_id."""
    questions = await list_questions(db, game.id)

    bundle = {
        "format": "buzzer/game",
        "version": SUPPORTED_IMPORT_VERSION,
        "game": {
            "title": game.title,
            "description": game.description,
            "max_players": game.max_players,
        },
        "questions": [
            {
                "type": q.type,
                "grading_type": q.grading_type,
                "prompt": q.prompt,
                "config": q.config,
                "answer_data": q.answer_data,
                "time_limit_seconds": q.time_limit_seconds,
                "points_value": q.points_value,
            }
            for q in questions
        ],
    }

    # ASCII only: header values are latin-1, and str.isalnum() accepts CJK letters,
    # which would make the response a 500. The bundle itself keeps the real title.
    safe_title = "".join(
        c if (c.isascii() and c.isalnum()) or c in " _-" else "_" for c in game.title
    ).strip(" _")
    filename = f"{safe_title or 'game'}.json"
    content = json.dumps(bundle, indent=2, ensure_ascii=False).encode()
    return filename, content


async def import_game_bundle(
    db: AsyncSession, raw: bytes, course_id: int | None
) -> Game:
    """
    Validate and import a buzzer/game bundle. The game's course comes only from the
    `course_id` argument (the host route's form field); any course_id in the file is
    discarded, so a hand-edited bundle cannot attach a game to a course the uploader
    may not host. The admin route passes None (the game lands unattached).
    """
    try:
        bundle = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise BundleError(f"Invalid JSON: {exc}") from exc

    if not isinstance(bundle, dict) or bundle.get("format") != "buzzer/game":
        raise BundleError("Unrecognised file format")
    version = bundle.get("version")
    if version != SUPPORTED_IMPORT_VERSION:
        raise BundleError(
            f"Unsupported version {version!r}; server supports version {SUPPORTED_IMPORT_VERSION}"
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
    validated_questions: list[QuestionCreate] = []
    for i, q in enumerate(questions_raw):
        try:
            validated_questions.append(QuestionCreate(**q))
        except Exception as exc:
            raise BundleError(f"Question {i + 1} invalid: {exc}") from exc

    game = Game(
        title=game_meta.title,
        description=game_meta.description,
        max_players=game_meta.max_players,
        course_id=course_id,
    )
    db.add(game)
    await db.flush()

    for idx, q in enumerate(validated_questions):
        db.add(
            Question(
                game_id=game.id,
                type=q.type,
                grading_type=q.grading_type,
                prompt=sanitize_prompt(q.prompt),
                config=q.config,
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
    )
    return game
