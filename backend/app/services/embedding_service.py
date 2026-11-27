import math
from uuid import UUID
import httpx
from fastapi import status
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.errors import AppError
from app.db.models import CodeChunk, CodeEmbedding, EMBEDDING_DIMENSION
from app.services.chunking_service import create_or_update_repository_chunks

REQUIRED_EMBEDDING_MODEL = "gemini-embedding-001"
GEMINI_BATCH_EMBED_URL = (
    "https://generativelanguage.googleapis.com/v1beta/models/gemini-embedding-001:batchEmbedContents"
)


def _normalize_vector(vec: list[float]) -> list[float]:
    norm = math.sqrt(sum(x * x for x in vec))
    if norm <= 0.0:
        return vec
    return [x / norm for x in vec]


def _embed_via_gemini(texts: list[str], api_key: str) -> list[list[float]]:
    """Generate normalized 384-dim embeddings via Gemini batchEmbedContents API."""
    results: list[list[float]] = []
    with httpx.Client(timeout=45.0) as client:
        for idx in range(0, len(texts), 50):
            batch = texts[idx : idx + 50]
            requests_payload = [
                {
                    "model": "models/gemini-embedding-001",
                    "content": {"parts": [{"text": text}]},
                    "outputDimensionality": EMBEDDING_DIMENSION,
                }
                for text in batch
            ]
            try:
                resp = client.post(
                    GEMINI_BATCH_EMBED_URL,
                    params={"key": api_key},
                    headers={"Content-Type": "application/json"},
                    json={"requests": requests_payload},
                )
            except httpx.TimeoutException as exc:
                raise AppError(
                    message="Gemini embedding request timed out.",
                    status_code=status.HTTP_504_GATEWAY_TIMEOUT,
                    code="embedding_timeout",
                ) from exc
            except httpx.RequestError as exc:
                raise AppError(
                    message="Network error while communicating with Gemini Embedding API.",
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    code="embedding_network_error",
                ) from exc

            if resp.status_code == 429:
                raise AppError(
                    message="Gemini API rate limit exceeded. Please try again shortly.",
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    code="embedding_rate_limited",
                )
            if resp.status_code >= 400:
                raise AppError(
                    message=f"Gemini Embedding API returned status {resp.status_code}. Check GEMINI_API_KEY.",
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    code="embedding_generation_failed",
                )

            data = resp.json()
            embeddings = data.get("embeddings") or []
            if len(embeddings) != len(batch):
                raise AppError(
                    message="Unexpected embedding response count from Gemini API.",
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    code="embedding_generation_failed",
                )

            for item in embeddings:
                raw_vec = item.get("values") or []
                if len(raw_vec) != EMBEDDING_DIMENSION:
                    raise AppError(
                        message=f"Embedding dimension mismatch: expected {EMBEDDING_DIMENSION}, got {len(raw_vec)}.",
                        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                        code="embedding_dimension_mismatch",
                    )
                results.append(_normalize_vector([float(v) for v in raw_vec]))
    return results


def embed_texts(texts: list[str], model_name: str = REQUIRED_EMBEDDING_MODEL) -> list[list[float]]:
    """Generate normalized 384-dimensional embeddings for a list of strings via Gemini."""
    if not texts:
        return []
    settings = get_settings()
    api_key = settings.GEMINI_API_KEY.strip()
    if not api_key or "YOUR_GEMINI" in api_key:
        raise AppError(
            message="GEMINI_API_KEY is not configured.",
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            code="gemini_not_configured",
        )
    return _embed_via_gemini(texts, api_key)


def generate_repository_embeddings(db: Session, repository_id: UUID, settings: Settings) -> dict:
    """Chunk repository files (if needed) and generate missing 384-dim Gemini pgvector embeddings."""
    model_name = REQUIRED_EMBEDDING_MODEL

    # Remove any legacy embeddings from a different model so vector space stays consistent
    db.execute(
        delete(CodeEmbedding).where(
            CodeEmbedding.repository_id == repository_id,
            CodeEmbedding.embedding_model != model_name,
        )
    )
    db.commit()

    chunk_stats = create_or_update_repository_chunks(db, repository_id)

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
            .where(
                CodeEmbedding.repository_id == repository_id,
                CodeEmbedding.embedding_model == model_name,
            )
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
    model_name = REQUIRED_EMBEDDING_MODEL
    counts = db.execute(
        select(
            select(func.count())
            .select_from(CodeChunk)
            .where(CodeChunk.repository_id == repository_id)
            .scalar_subquery(),
            select(func.count())
            .select_from(CodeEmbedding)
            .where(
                CodeEmbedding.repository_id == repository_id,
                CodeEmbedding.embedding_model == model_name,
            )
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
