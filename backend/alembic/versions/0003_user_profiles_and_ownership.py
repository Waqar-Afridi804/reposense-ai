"""Add user_profiles table and repository user_id ownership.

Revision ID: 0003_user_profiles_ownership
Revises: 0002_phase3_github_ast
Create Date: 2026-11-25
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0003_user_profiles_ownership"
down_revision: Union[str, Sequence[str], None] = "0002_phase3_github_ast"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "user_profiles",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("display_name", sa.String(length=255), nullable=True),
        sa.Column("avatar_url", sa.String(length=1000), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email"),
    )

    op.add_column("repositories", sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.create_foreign_key(
        "fk_repositories_user_id",
        "repositories",
        "user_profiles",
        ["user_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_index("ix_repositories_user_id", "repositories", ["user_id"], unique=False)

    op.execute("ALTER TABLE repositories DROP CONSTRAINT IF EXISTS repositories_github_url_key")
    op.execute("ALTER TABLE repositories DROP CONSTRAINT IF EXISTS uq_repositories_owner_name")
    op.create_unique_constraint("uq_repositories_user_owner_name", "repositories", ["user_id", "owner", "name"])
    op.create_unique_constraint("uq_repositories_user_github_url", "repositories", ["user_id", "github_url"])


def downgrade() -> None:
    op.drop_constraint("uq_repositories_user_github_url", "repositories", type_="unique")
    op.drop_constraint("uq_repositories_user_owner_name", "repositories", type_="unique")
    op.create_unique_constraint("uq_repositories_owner_name", "repositories", ["owner", "name"])
    op.create_unique_constraint("repositories_github_url_key", "repositories", ["github_url"])

    op.drop_index("ix_repositories_user_id", table_name="repositories")
    op.drop_constraint("fk_repositories_user_id", "repositories", type_="foreignkey")
    op.drop_column("repositories", "user_id")

    op.drop_table("user_profiles")
