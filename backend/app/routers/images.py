"""
Public image serving (T8): GET /api/images/{id}, deliberately with no auth
dependency. The random UUID is the only protection (docs/design-image-support.md
decision 1); management routes live in routers/host.py.

No get_db either: its cleanup runs after the response is sent, which would keep a
pooled connection checked out while bytes stream to a slow phone. A class fetching
option images at question start would then starve record_answer, which shares the
pool (design 4.3, "A short session, not get_db").
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Header, Request
from fastapi.responses import Response

from ..common.exceptions import NotFoundError
from ..database import AsyncSessionLocal
from ..schemas.admin import is_image_id
from ..services import image_service

router = APIRouter(tags=["images"])


def _etag_matches(if_none_match: str | None, etag: str) -> bool:
    if not if_none_match:
        return False
    return any(
        tag.strip().removeprefix("W/") in (etag, "*")
        for tag in if_none_match.split(",")
    )


@router.api_route("/images/{image_id}", methods=["GET", "HEAD"])
async def serve_image(
    image_id: str,
    request: Request,
    if_none_match: Annotated[str | None, Header()] = None,
) -> Response:
    if not is_image_id(image_id):
        raise NotFoundError("Image not found")
    # no-cache + ETag: a replaced image shows on the next load, an unchanged one
    # costs only a 304, and a 304 never reads the bytes.
    async with AsyncSessionLocal() as db:
        head = await image_service.read_image_head(db, image_id)
        if head is None:
            raise NotFoundError("Image not found")
        etag = f'"{head.sha256}"'
        row = None
        if request.method == "HEAD" and not _etag_matches(if_none_match, etag):
            # The GET's headers from the head query alone; HEAD never reads the bytes.
            return Response(
                headers={
                    "Cache-Control": "no-cache",
                    "X-Content-Type-Options": "nosniff",
                    "ETag": etag,
                    "Content-Disposition": "inline",
                    "Content-Type": head.content_type,
                    "Content-Length": str(head.byte_size),
                }
            )
        if not _etag_matches(if_none_match, etag):
            row = await image_service.read_image_data(db, image_id)
            if row is None:
                raise NotFoundError("Image not found")
    # The session is closed and its connection back in the pool before any byte
    # is sent.
    headers = {"Cache-Control": "no-cache", "X-Content-Type-Options": "nosniff"}
    if row is None:
        return Response(status_code=304, headers={**headers, "ETag": etag})
    return Response(
        content=row.data,
        media_type=row.content_type,
        headers={
            **headers,
            "ETag": f'"{row.sha256}"',
            "Content-Disposition": "inline",
        },
    )
