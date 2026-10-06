"""Course image library (images table, questions.prompt_image_id)

Revision ID: 005
Revises: 004
Create Date: 2026-10-05
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import mysql

revision: str = "005"
down_revision: Union[str, None] = "004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "images",
        sa.Column("id", sa.CHAR(36), primary_key=True),
        sa.Column(
            "course_id", sa.Integer(), sa.ForeignKey("courses.id"), nullable=False
        ),
        sa.Column(
            "uploaded_by",
            sa.String(36),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("filename", sa.String(255), nullable=False),
        sa.Column("content_type", sa.String(32), nullable=False),
        sa.Column("width", sa.Integer(), nullable=False),
        sa.Column("height", sa.Integer(), nullable=False),
        sa.Column("byte_size", sa.Integer(), nullable=False),
        sa.Column("sha256", sa.CHAR(64), nullable=False),
        sa.Column("data", mysql.MEDIUMBLOB(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_index("ix_images_course_sha256", "images", ["course_id", "sha256"])
    op.add_column("questions", sa.Column("prompt_image_id", sa.CHAR(36), nullable=True))
    op.create_foreign_key(
        "fk_questions_prompt_image_id",
        "questions",
        "images",
        ["prompt_image_id"],
        ["id"],
        ondelete="RESTRICT",
    )


def downgrade() -> None:
    op.drop_constraint("fk_questions_prompt_image_id", "questions", type_="foreignkey")
    op.drop_column("questions", "prompt_image_id")
    # The (course_id, sha256) index also backs the course_id FK, so MySQL refuses to
    # drop it on its own; it goes with the table.
    op.drop_table("images")
