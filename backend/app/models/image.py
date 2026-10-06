from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import CHAR, DateTime, ForeignKey, Index, Integer, String, func
from sqlalchemy.dialects.mysql import MEDIUMBLOB
from sqlalchemy.orm import Mapped, deferred, mapped_column, relationship

from ..database import Base

if TYPE_CHECKING:
    from .user import User


class Image(Base):
    """
    A course-library image (T8, docs/design-image-support.md). The random UUID is
    also the public handle in GET /api/images/{id}. `data` is deferred so listing
    never loads the bytes; every reader of the bytes must load them explicitly
    (`undefer(Image.data)`), because a lazy load on an async session raises
    MissingGreenlet.
    """

    __tablename__ = "images"
    __table_args__ = (Index("ix_images_course_sha256", "course_id", "sha256"),)

    id: Mapped[str] = mapped_column(
        CHAR(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    course_id: Mapped[int] = mapped_column(ForeignKey("courses.id"), nullable=False)
    uploaded_by: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    content_type: Mapped[str] = mapped_column(String(32), nullable=False)
    width: Mapped[int] = mapped_column(Integer, nullable=False)
    height: Mapped[int] = mapped_column(Integer, nullable=False)
    byte_size: Mapped[int] = mapped_column(Integer, nullable=False)
    sha256: Mapped[str] = mapped_column(CHAR(64), nullable=False)
    data: Mapped[bytes] = deferred(mapped_column(MEDIUMBLOB, nullable=False))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    uploader: Mapped[User | None] = relationship("User", lazy="selectin")
