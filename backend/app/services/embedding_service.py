from functools import lru_cache
import math
from uuid import UUID
import httpx
from fastapi import status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.errors import AppError
from app.db.models import CodeChunk, CodeEmbedding, EMBEDDING_DIMENSION
from app.services.chunking_service import create_or_update_repository_chunks

REQUIRED_EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
HF_INFERENCE_URL = (
    "https://router.huggingface.co/hf-inference/models/"
    "sentence-transformers/all-MiniLM-L6-v2/pipeline/feature-extraction"
)


def _normalize_vector(vec: list[float]) -> list[float]:
    norm = math.sqrt(sum(x * x for x in vec))
    if norm <= 0.0:
        return vec
    return [x / norm for x in vec]


def _embed_via_hf_inference(texts: list[str], hf_token: str) -> list[list[float]]:
    """Generate normalized 384-dim embeddings via Hugging Face Inference API."""
    results: list[list[float]] = []
    headers = {
        "Authorization": f"Bearer {hf_token}",
        "Content-Type": "application/json",
    }
    with httpx.Client(timeout=45.0) as client:
        for idx in range(0, len(texts), 32):
            batch = texts[idx : idx + 32]
            try:
                resp = client.post(
                    HF_INFERENCE_URL,
                    headers=headers,
                    json={"inputs": batch, "options": {"wait_for_model": True}},
                )
            except httpx.TimeoutException as exc:
                raise AppError(
                    message="Hugging Face embedding request timed out.",
                    status_code=status.HTTP_504_GATEWAY_TIMEOUT,
                    code="embedding_timeout",
                ) from exc
            except httpx.RequestError as exc:
                raise AppError(
                    message="Network error while communicating with Hugging Face Inference API.",
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    code="embedding_network_error",
                ) from exc

            if resp.status_code == 401:
                raise AppError(
                    message="Invalid HF_TOKEN for Hugging Face Inference API.",
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    code="embedding_auth_error",
                )
            if resp.status_code == 429:
                raise AppError(
                    message="Hugging Face Inference API rate limit exceeded. Please try again shortly.",
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    code="embedding_rate_limited",
                )
            if resp.status_code >= 400:
                raise AppError(
                    message=f"Hugging Face Inference API returned status {resp.status_code}.",
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    code="embedding_generation_failed",
                )

            data = resp.json()
            if not isinstance(data, list) or len(data) != len(batch):
                raise AppError(
                    message="Unexpected embedding response format from Hugging Face Inference API.",
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    code="embedding_generation_failed",
                )

            for raw_vec in data:
                if not isinstance(raw_vec, list) or len(raw_vec) != EMBEDDING_DIMENSION:
                    raise AppError(
                        message=f"Embedding dimension mismatch: expected {EMBEDDING_DIMENSION}.",
                        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                        code="embedding_dimension_mismatch",
                    )
                results.append(_normalize_vector([float(v) for v in raw_vec]))
    return results


@lru_cache(maxsize=1)
def _load_sentence_transformer(model_name: str):
    """Load and cache the SentenceTransformer model for local fallback."""
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
    settings = get_settings()
    hf_token = settings.HF_TOKEN.strip()
    if hf_token and "YOUR_HF" not in hf_token:
        return _embed_via_hf_inference(texts, hf_token)

    try:
        model = _load_sentence_transformer(model_name)
        vectors = model.encode(
            texts,
            batch_size=32,
            normalize_embeddings=True,
            show_progress_bar=False,
        )
        return [vec.tolist() for vec in vectors]
    except ImportError as exc:
        raise AppError(
            message="HF_TOKEN is not configured for remote embeddings.",
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            code="embedding_not_configured",
        ) from exc
    except AppError:
        raise
    except Exception as exc:
        raise AppError(
            message="Failed to generate embeddings.",
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
