"""Add ai_chat_logs table for 7-day AI chat and word quota enforcement.

Revision ID: 0004_ai_chat_logs
Revises: 0003_user_profiles_ownership
Create Date: 2026-11-26
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0004_ai_chat_logs"
down_revision: Union[str, Sequence[str], None] = "0003_user_profiles_ownership"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "ai_chat_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("repository_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("word_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["user_profiles.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_ai_chat_logs_user_created", "ai_chat_logs", ["user_id", "created_at"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_ai_chat_logs_user_created", table_name="ai_chat_logs")
    op.drop_table("ai_chat_logs")
