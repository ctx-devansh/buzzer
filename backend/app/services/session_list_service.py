"""
Session-list row builder shared by GET /admin/sessions and GET /host/sessions.

AdminSessionItem is from_attributes=False, so rows are assembled by hand here.
The per-session lookups (game, course, host, player count) are an N+1 carried
over unchanged from the original admin.list_sessions loop.
"""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.course import Course
from ..models.game import Game
from ..models.session import GameSession, SessionScore
from ..models.user import User


async def list_session_rows(
    db: AsyncSession, status: str | None, host_user_id: str | None
) -> list[dict]:
    """
    List sessions newest first. `status` is one exact session_status value or None
    for all; `host_user_id` restricts to one host's sessions, or None for every host.
    """
    query = select(GameSession).order_by(GameSession.created_at.desc())
    if status:
        query = query.where(GameSession.status == status)
    if host_user_id is not None:
        query = query.where(GameSession.host_user_id == host_user_id)
    result = await db.execute(query)
    sessions = result.scalars().all()

    rows = []
    for s in sessions:
        game = await db.get(Game, s.game_id)
        course = await db.get(Course, s.course_id)
        host = await db.get(User, s.host_user_id) if s.host_user_id else None

        count_result = await db.execute(
            select(func.count(SessionScore.user_id.distinct())).where(
                SessionScore.session_id == s.id
            )
        )
        player_count = count_result.scalar_one() or 0

        rows.append(
            {
                "session_id": s.id,
                "room_code": s.room_code,
                "status": s.status,
                "game_id": s.game_id,
                "game_title": game.title if game else "Unknown",
                "course_id": s.course_id,
                "course_name": course.name if course else "Unknown",
                "course_semester": course.semester if course else "",
                "host_display_name": (host.display_name or host.username or host.netid)
                if host
                else None,
                "created_at": s.created_at,
                "completed_at": s.completed_at,
                "player_count": player_count,
            }
        )
    return rows
