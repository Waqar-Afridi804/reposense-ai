"""Add GitHub metadata timestamps, file content, and AST analysis fields.

Revision ID: 0002_phase3_github_and_ast_fields
Revises: 0001_initial_schema
Create Date: 2026-11-24
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0002_phase3_github_ast"
down_revision: Union[str, Sequence[str], None] = "0001_initial_schema"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("repositories", sa.Column("github_created_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("repositories", sa.Column("github_updated_at", sa.DateTime(timezone=True), nullable=True))

    op.add_column("repository_files", sa.Column("content", sa.Text(), nullable=True))

    op.add_column("analysis_results", sa.Column("python_files_count", sa.Integer(), server_default="0", nullable=False))
    op.add_column(
        "analysis_results",
        sa.Column("other_supported_files_count", sa.Integer(), server_default="0", nullable=False),
    )
    op.add_column("analysis_results", sa.Column("total_classes", sa.Integer(), server_default="0", nullable=False))
    op.add_column("analysis_results", sa.Column("total_functions", sa.Integer(), server_default="0", nullable=False))
    op.add_column("analysis_results", sa.Column("total_methods", sa.Integer(), server_default="0", nullable=False))
    op.add_column(
        "analysis_results",
        sa.Column("ast_details", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
    op.add_column("analysis_results", sa.Column("mermaid_diagram", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("analysis_results", "mermaid_diagram")
    op.drop_column("analysis_results", "ast_details")
    op.drop_column("analysis_results", "total_methods")
    op.drop_column("analysis_results", "total_functions")
    op.drop_column("analysis_results", "total_classes")
    op.drop_column("analysis_results", "other_supported_files_count")
    op.drop_column("analysis_results", "python_files_count")

    op.drop_column("repository_files", "content")

    op.drop_column("repositories", "github_updated_at")
    op.drop_column("repositories", "github_created_at")
