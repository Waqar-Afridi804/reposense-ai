"""Initial schema for RepoSense AI (5 core tables + pgvector).

Revision ID: 0001_initial_schema
Revises:
Create Date: 2026-11-24
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects import postgresql

revision: str = "0001_initial_schema"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table(
        "repositories",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("github_url", sa.String(length=500), nullable=False),
        sa.Column("owner", sa.String(length=255), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("default_branch", sa.String(length=100), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("primary_language", sa.String(length=100), nullable=True),
        sa.Column("stars_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("forks_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("status", sa.String(length=50), nullable=False, server_default="pending"),
        sa.Column("last_analyzed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("github_url"),
        sa.UniqueConstraint("owner", "name", name="uq_repositories_owner_name"),
    )
    op.create_index("ix_repositories_status", "repositories", ["status"], unique=False)

    op.create_table(
        "repository_files",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("repository_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("file_path", sa.String(length=1000), nullable=False),
        sa.Column("file_name", sa.String(length=255), nullable=False),
        sa.Column("extension", sa.String(length=50), nullable=True),
        sa.Column("language", sa.String(length=100), nullable=True),
        sa.Column("size_bytes", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("line_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("content_hash", sa.String(length=64), nullable=True),
        sa.Column("is_supported", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["repository_id"], ["repositories.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("repository_id", "file_path", name="uq_repository_files_repo_path"),
    )
    op.create_index("ix_repository_files_repo_id", "repository_files", ["repository_id"], unique=False)
    op.create_index(
        "ix_repository_files_repo_lang", "repository_files", ["repository_id", "language"], unique=False
    )

    op.create_table(
        "analysis_results",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("repository_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("total_files", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("supported_files", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_lines", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("language_stats", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("architecture_notes", sa.Text(), nullable=True),
        sa.Column("dependency_graph", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("status", sa.String(length=50), nullable=False, server_default="pending"),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["repository_id"], ["repositories.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_analysis_results_repo_created", "analysis_results", ["repository_id", "created_at"], unique=False
    )

    op.create_table(
        "code_chunks",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("repository_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("file_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("file_path", sa.String(length=1000), nullable=False),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("start_line", sa.Integer(), nullable=False),
        sa.Column("end_line", sa.Integer(), nullable=False),
        sa.Column("symbol_name", sa.String(length=255), nullable=True),
        sa.Column("chunk_type", sa.String(length=50), nullable=True),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("token_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("content_hash", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["file_id"], ["repository_files.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["repository_id"], ["repositories.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("file_id", "chunk_index", name="uq_code_chunks_file_chunk_idx"),
    )
    op.create_index("ix_code_chunks_repo_id", "code_chunks", ["repository_id"], unique=False)
    op.create_index("ix_code_chunks_repo_path", "code_chunks", ["repository_id", "file_path"], unique=False)

    op.create_table(
        "code_embeddings",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("repository_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("chunk_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "embedding_model",
            sa.String(length=255),
            nullable=False,
            server_default="sentence-transformers/all-MiniLM-L6-v2",
        ),
        sa.Column("embedding", Vector(384), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["chunk_id"], ["code_chunks.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["repository_id"], ["repositories.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("chunk_id"),
    )
    op.create_index("ix_code_embeddings_repo_id", "code_embeddings", ["repository_id"], unique=False)
    op.create_index(
        "ix_code_embeddings_vector_hnsw",
        "code_embeddings",
        ["embedding"],
        unique=False,
        postgresql_using="hnsw",
        postgresql_with={"m": 16, "ef_construction": 64},
        postgresql_ops={"embedding": "vector_cosine_ops"},
    )


def downgrade() -> None:
    op.drop_index("ix_code_embeddings_vector_hnsw", table_name="code_embeddings")
    op.drop_index("ix_code_embeddings_repo_id", table_name="code_embeddings")
    op.drop_table("code_embeddings")

    op.drop_index("ix_code_chunks_repo_path", table_name="code_chunks")
    op.drop_index("ix_code_chunks_repo_id", table_name="code_chunks")
    op.drop_table("code_chunks")

    op.drop_index("ix_analysis_results_repo_created", table_name="analysis_results")
    op.drop_table("analysis_results")

    op.drop_index("ix_repository_files_repo_lang", table_name="repository_files")
    op.drop_index("ix_repository_files_repo_id", table_name="repository_files")
    op.drop_table("repository_files")

    op.drop_index("ix_repositories_status", table_name="repositories")
    op.drop_table("repositories")
