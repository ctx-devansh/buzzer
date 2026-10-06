"""
Host-scoped authoring, roster and session routes (/host/*).

Every route is gated by require_user plus assert_host_can_use_course and/or
assert_host_can_use_game on the resource; ADMIN passes every check. Response shapes
match the /admin/* equivalents, and everything past the gate is the same service
call the admin router makes (services/authoring_service.py, roster_service.py,
session_list_service.py) — do not copy logic in here.

Deliberately absent: game delete (grade data; admin-only), course reassignment
(HostGameUpdate has no course_id), and the multipart roster upload (no consumer).
"""

from __future__ import annotations

import io
from typing import Annotated

import structlog
from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import Response, StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from ..common.dependencies import require_user
from ..common.exceptions import ForbiddenError, NotFoundError
from ..database import get_db
from ..models.course import CourseRoster
from ..models.game import Game, Question, UserGameAccess
from ..models.session import GameSession
from ..models.user import User
from ..schemas.admin import (
    AdminSessionItem,
    GameResponse,
    HostGameCreate,
    HostGameUpdate,
    QuestionCreate,
    QuestionReorder,
    QuestionResponse,
    QuestionUpdate,
    RosterEntryPatch,
    RosterEntryResponse,
    RosterImportPayload,
    RosterUploadResult,
)
from ..schemas.image import ImageReplaceResponse, ImageResponse
from ..services import authoring_service as authoring
from ..services import image_service, roster_service
from ..services.game_service import (
    assert_host_can_use_course,
    assert_host_can_use_game,
    visible_games_query,
)
from ..services.report_service import build_session_report
from ..services.session_list_service import list_session_rows

router = APIRouter(prefix="/host", tags=["host"])
logger = structlog.get_logger()

_SESSION_STATUS_PATTERN = "^(LOBBY|IN_PROGRESS|COMPLETED|ABANDONED)$"


# ---------------------------------------------------------------------------
# Games
# ---------------------------------------------------------------------------


@router.get("/games", response_model=list[GameResponse])
async def list_games(
    user: Annotated[User, Depends(require_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    course_id: int | None = Query(
        None, description="Only games attached to this course"
    ),
) -> list[Game]:
    """
    Games the user may edit. `course_id` is a gate, not only a filter: a non-admin
    without HOST on it gets 403 (also for a nonexistent course — existence is not
    leaked); ADMIN gets 404 for a nonexistent course. Unattached games appear for
    ADMIN only when `course_id` is omitted.
    """
    if course_id is not None:
        await assert_host_can_use_course(db, user, course_id)
    result = await db.execute(visible_games_query(user, course_id))
    return result.scalars().all()


def _grant_creator(db: AsyncSession, user: User, game: Game) -> None:
    """Host-created games are auto-granted to their creator (admin routes do not)."""
    db.add(UserGameAccess(user_id=user.id, game_id=game.id))


@router.post("/games", response_model=GameResponse, status_code=201)
async def create_game(
    body: HostGameCreate,
    user: Annotated[User, Depends(require_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Game:
    await assert_host_can_use_course(db, user, body.course_id)
    game = Game(
        title=body.title,
        description=body.description,
        max_players=body.max_players,
        course_id=body.course_id,
    )
    db.add(game)
    await db.flush()
    _grant_creator(db, user, game)
    # Attribute-scoped refresh: the INSERT does not load `course`, and lazy="selectin"
    # only fires on a SELECT — without this, course_name lazy-loads → MissingGreenlet.
    await db.refresh(game, ["created_at", "course"])
    await db.commit()
    logger.info(
        "host_game_created", game_id=game.id, course_id=body.course_id, user_id=user.id
    )
    return game


@router.post("/games/import", status_code=201)
async def import_game(
    file: Annotated[UploadFile, File(description="buzzer/game JSON bundle")],
    course_id: Annotated[int, Form(description="Course to attach the game to")],
    user: Annotated[User, Depends(require_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    """The game's course comes only from the form field; a bundle's own is discarded."""
    await assert_host_can_use_course(db, user, course_id)
    try:
        game = await authoring.import_game_bundle(
            db, await file.read(), course_id, user.id
        )
    except authoring.BundleError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    _grant_creator(db, user, game)
    await db.commit()
    return {"game_id": game.id}


@router.get("/games/{game_id}", response_model=GameResponse)
async def get_game(
    game_id: int,
    user: Annotated[User, Depends(require_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Game:
    return await assert_host_can_use_game(db, user, game_id)


@router.put("/games/{game_id}", response_model=GameResponse)
async def update_game(
    game_id: int,
    body: HostGameUpdate,
    user: Annotated[User, Depends(require_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Game:
    game = await assert_host_can_use_game(db, user, game_id)
    if body.title is not None:
        game.title = body.title
    if body.description is not None:
        game.description = body.description
    if body.max_players is not None:
        game.max_players = body.max_players
    return game


@router.get("/games/{game_id}/export")
async def export_game(
    game_id: int,
    user: Annotated[User, Depends(require_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> StreamingResponse:
    game = await assert_host_can_use_game(db, user, game_id)
    filename, content = await authoring.build_export_bundle(db, game)
    return StreamingResponse(
        io.BytesIO(content),
        media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# ---------------------------------------------------------------------------
# Questions
# ---------------------------------------------------------------------------


@router.get("/games/{game_id}/questions", response_model=list[QuestionResponse])
async def list_questions(
    game_id: int,
    user: Annotated[User, Depends(require_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[Question]:
    await assert_host_can_use_game(db, user, game_id)
    return await authoring.list_questions(db, game_id)


@router.post(
    "/games/{game_id}/questions", response_model=QuestionResponse, status_code=201
)
async def create_question(
    game_id: int,
    body: QuestionCreate,
    user: Annotated[User, Depends(require_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Question:
    await assert_host_can_use_game(db, user, game_id)
    return await authoring.create_question(db, game_id, body)


@router.post("/games/{game_id}/questions/reorder", status_code=204)
async def reorder_questions(
    game_id: int,
    body: QuestionReorder,
    user: Annotated[User, Depends(require_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    await assert_host_can_use_game(db, user, game_id)
    await authoring.reorder_questions(db, game_id, body.order)


@router.put("/games/{game_id}/questions/{question_id}", response_model=QuestionResponse)
async def update_question(
    game_id: int,
    question_id: int,
    body: QuestionUpdate,
    user: Annotated[User, Depends(require_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Question:
    await assert_host_can_use_game(db, user, game_id)
    return await authoring.update_question(db, game_id, question_id, body)


@router.delete("/games/{game_id}/questions/{question_id}", status_code=204)
async def delete_question(
    game_id: int,
    question_id: int,
    user: Annotated[User, Depends(require_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    await assert_host_can_use_game(db, user, game_id)
    await authoring.delete_question(db, game_id, question_id)


# ---------------------------------------------------------------------------
# Roster
# ---------------------------------------------------------------------------


@router.get("/courses/{course_id}/roster", response_model=list[RosterEntryResponse])
async def list_roster(
    course_id: int,
    user: Annotated[User, Depends(require_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[CourseRoster]:
    await assert_host_can_use_course(db, user, course_id)
    return await roster_service.list_roster(db, course_id)


@router.post("/courses/{course_id}/roster/import", response_model=RosterUploadResult)
async def import_roster_rows(
    course_id: int,
    payload: RosterImportPayload,
    user: Annotated[User, Depends(require_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> RosterUploadResult:
    await assert_host_can_use_course(db, user, course_id)
    rows = [
        {"netid": r.netid, "full_name": r.full_name, "email": r.email}
        for r in payload.rows
    ]
    result = await roster_service.process_roster_rows(db, course_id, rows)
    await db.commit()
    return result


@router.patch(
    "/courses/{course_id}/roster/{roster_id}", response_model=RosterEntryResponse
)
async def patch_roster_entry(
    course_id: int,
    roster_id: int,
    body: RosterEntryPatch,
    user: Annotated[User, Depends(require_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> CourseRoster:
    await assert_host_can_use_course(db, user, course_id)
    return await roster_service.patch_roster_entry(db, course_id, roster_id, body)


# ---------------------------------------------------------------------------
# Image library (T8). Course-wide: every HOST of the course manages its images
# (design decision 6). An image in another course is a 404 through this path.
# ---------------------------------------------------------------------------

_IMAGE_FILE = File(description="PNG, JPEG, GIF or WebP, at most 5 MB")


async def _read_upload(file: UploadFile) -> bytes:
    # One byte over the limit is enough for process_upload to answer 413.
    return await file.read(image_service.MAX_UPLOAD_BYTES + 1)


@router.get("/courses/{course_id}/images", response_model=list[ImageResponse])
async def list_images(
    course_id: int,
    user: Annotated[User, Depends(require_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[dict]:
    await assert_host_can_use_course(db, user, course_id)
    return await image_service.list_images(db, course_id)


@router.post(
    "/courses/{course_id}/images", response_model=ImageResponse, status_code=201
)
async def upload_image(
    course_id: int,
    file: Annotated[UploadFile, _IMAGE_FILE],
    user: Annotated[User, Depends(require_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    await assert_host_can_use_course(db, user, course_id)
    return await image_service.upload_image(
        db, course_id, user.id, file.filename, await _read_upload(file)
    )


@router.get("/courses/{course_id}/images/{image_id}", response_model=ImageResponse)
async def get_image(
    course_id: int,
    image_id: str,
    user: Annotated[User, Depends(require_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    await assert_host_can_use_course(db, user, course_id)
    return await image_service.get_image(db, course_id, image_id)


@router.put(
    "/courses/{course_id}/images/{image_id}", response_model=ImageReplaceResponse
)
async def replace_image(
    course_id: int,
    image_id: str,
    file: Annotated[UploadFile, _IMAGE_FILE],
    user: Annotated[User, Depends(require_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    await assert_host_can_use_course(db, user, course_id)
    return await image_service.replace_image(
        db, course_id, image_id, user.id, file.filename, await _read_upload(file)
    )


@router.delete("/courses/{course_id}/images/{image_id}", status_code=204)
async def delete_image(
    course_id: int,
    image_id: str,
    user: Annotated[User, Depends(require_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    await assert_host_can_use_course(db, user, course_id)
    await image_service.delete_image(db, course_id, image_id)


# ---------------------------------------------------------------------------
# Sessions
# ---------------------------------------------------------------------------


@router.get("/sessions", response_model=list[AdminSessionItem])
async def list_sessions(
    user: Annotated[User, Depends(require_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    status: str | None = Query(
        None,
        pattern=_SESSION_STATUS_PATTERN,
        description="One exact status (LOBBY, IN_PROGRESS, COMPLETED, ABANDONED)",
    ),
) -> list[dict]:
    """
    ADMIN sees every host's sessions; anyone else only those they hosted
    (host_user_id == me — no course-access predicate, so revoking HOST access does
    not hide a host's own past sessions, and co-hosts do not see each other's).
    """
    host_user_id = None if user.role == "ADMIN" else user.id
    return await list_session_rows(db, status=status, host_user_id=host_user_id)


@router.get("/sessions/{session_id}/report")
async def session_report(
    session_id: str,
    user: Annotated[User, Depends(require_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Response:
    """Standalone HTML summary (aggregate stats, no PII). Session host or ADMIN."""
    session = await db.get(GameSession, session_id)
    if not session:
        raise NotFoundError(f"Session {session_id} not found")
    if user.role != "ADMIN" and session.host_user_id != user.id:
        raise ForbiddenError("Only the session host can download this report")
    filename, content = await build_session_report(db, session_id)
    return Response(
        content=content,
        media_type="text/html",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
