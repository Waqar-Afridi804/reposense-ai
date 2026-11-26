from functools import lru_cache
from uuid import UUID
from fastapi import status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.errors import AppError
from app.db.models import CodeChunk, CodeEmbedding, EMBEDDING_DIMENSION
from app.services.chunking_service import create_or_update_repository_chunks

REQUIRED_EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"


@lru_cache(maxsize=1)
def _load_sentence_transformer(model_name: str):
    """Load and cache the SentenceTransformer model."""
    from sentence_transformers import SentenceTransformer

    model = SentenceTransformer(model_name)
    dim = model.get_sentence_embedding_dimension()
    if dim != EMBEDDING_DIMENSION:
        raise AppError(
            message=f"Embedding dimension mismatch: expected {EMBEDDING_DIMENSION}, got {dim}.",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            code="embedding_dimension_mismatch",
        )
    return model


def embed_texts(texts: list[str], model_name: str = REQUIRED_EMBEDDING_MODEL) -> list[list[float]]:
    """Generate normalized 384-dimensional embeddings for a list of strings."""
    if not texts:
        return []
    try:
        model = _load_sentence_transformer(model_name)
        vectors = model.encode(
            texts,
            batch_size=32,
            normalize_embeddings=True,
            show_progress_bar=False,
        )
        return [vec.tolist() for vec in vectors]
    except AppError:
        raise
    except Exception as exc:
        raise AppError(
            message="Failed to generate embeddings with sentence-transformers.",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            code="embedding_generation_failed",
        ) from exc


def generate_repository_embeddings(db: Session, repository_id: UUID, settings: Settings) -> dict:
    """Chunk repository files (if needed) and generate missing pgvector embeddings."""
    model_name = settings.EMBEDDING_MODEL.strip() or REQUIRED_EMBEDDING_MODEL
    if model_name != REQUIRED_EMBEDDING_MODEL:
        raise AppError(
            message=f"Unsupported embedding model '{model_name}'. Expected '{REQUIRED_EMBEDDING_MODEL}'.",
            status_code=status.HTTP_400_BAD_REQUEST,
            code="invalid_embedding_model",
        )

    chunk_stats = create_or_update_repository_chunks(db, repository_id)

    # Fetch only chunks that do not yet have a CodeEmbedding
    pending_chunks = db.execute(
        select(CodeChunk)
        .outerjoin(CodeEmbedding, CodeEmbedding.chunk_id == CodeChunk.id)
        .where(
            CodeChunk.repository_id == repository_id,
            CodeEmbedding.id.is_(None),
        )
        .order_by(CodeChunk.file_path.asc(), CodeChunk.chunk_index.asc())
    ).scalars().all()

    newly_embedded = 0
    if pending_chunks:
        texts = [
            f"File: {ch.file_path} (lines {ch.start_line}-{ch.end_line})\n{ch.content}"
            for ch in pending_chunks
        ]
        vectors = embed_texts(texts, model_name=model_name)

        new_embeddings = [
            CodeEmbedding(
                repository_id=repository_id,
                chunk_id=ch.id,
                embedding_model=model_name,
                embedding=vec,
            )
            for ch, vec in zip(pending_chunks, vectors)
        ]
        db.add_all(new_embeddings)
        newly_embedded = len(new_embeddings)
        db.commit()

    counts = db.execute(
        select(
            select(func.count())
            .select_from(CodeChunk)
            .where(CodeChunk.repository_id == repository_id)
            .scalar_subquery(),
            select(func.count())
            .select_from(CodeEmbedding)
            .where(CodeEmbedding.repository_id == repository_id)
            .scalar_subquery(),
        )
    ).one()
    total_chunks, total_embeddings = counts[0] or 0, counts[1] or 0

    return {
        "repository_id": repository_id,
        "embedding_model": model_name,
        "vector_dimension": EMBEDDING_DIMENSION,
        "files_processed": chunk_stats["files_processed"],
        "total_chunks": total_chunks,
        "total_embeddings": total_embeddings,
        "newly_embedded": newly_embedded,
        "skipped_existing": max(total_chunks - newly_embedded, 0),
        "status": "completed" if total_chunks > 0 and total_embeddings == total_chunks else "empty",
    }


def get_embedding_status(db: Session, repository_id: UUID, settings: Settings) -> dict:
    """Return current chunk and pgvector embedding counts for a repository in a single DB query."""
    model_name = settings.EMBEDDING_MODEL.strip() or REQUIRED_EMBEDDING_MODEL
    counts = db.execute(
        select(
            select(func.count())
            .select_from(CodeChunk)
            .where(CodeChunk.repository_id == repository_id)
            .scalar_subquery(),
            select(func.count())
            .select_from(CodeEmbedding)
            .where(CodeEmbedding.repository_id == repository_id)
            .scalar_subquery(),
        )
    ).one()
    total_chunks, total_embeddings = counts[0] or 0, counts[1] or 0

    if total_chunks == 0:
        status_label = "not_started"
    elif total_embeddings >= total_chunks:
        status_label = "completed"
    else:
        status_label = "partial"

    return {
        "repository_id": repository_id,
        "embedding_model": model_name,
        "vector_dimension": EMBEDDING_DIMENSION,
        "total_chunks": total_chunks,
        "total_embeddings": total_embeddings,
        "status": status_label,
    }
