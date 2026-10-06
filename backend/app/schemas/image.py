from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class ImageUse(BaseModel):
    """One question using a library image (image_service.where_used, minus counts)."""

    game_id: int
    game_title: str
    question_id: int
    order_index: int
    question_number: int  # 1-based position in the game, as the editor numbers it
    roles: list[str]  # subset of prompt, option, canvas
    played: bool


class ImageResponse(BaseModel):
    """A library image's metadata. Never carries the bytes: those are at `url`."""

    id: str
    course_id: int
    filename: str
    content_type: str
    width: int
    height: int
    byte_size: int
    uploaded_by_name: str | None
    created_at: datetime
    updated_at: datetime
    url: str
    used_by: list[ImageUse]


class ImageReplaceResponse(ImageResponse):
    size_changed: bool
    resized_question_ids: list[int]
    clamped_question_ids: list[int]
