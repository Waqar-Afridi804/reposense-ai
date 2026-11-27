from uuid import UUID
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.db.models import CodeChunk, CodeEmbedding
from app.services.embedding_service import REQUIRED_EMBEDDING_MODEL, embed_texts


def semantic_search_repository(
    db: Session,
    repository_id: UUID,
    query: str,
    settings: Settings,
    top_k: int = 5,
) -> list[dict]:
    """Search code chunks within a single repository using pgvector cosine similarity."""
    query_vectors = embed_texts([query], model_name=REQUIRED_EMBEDDING_MODEL)
    if not query_vectors:
        return []
    query_vector = query_vectors[0]

    distance_expr = CodeEmbedding.embedding.cosine_distance(query_vector)
    stmt = (
        select(CodeChunk, distance_expr.label("distance"))
        .join(CodeEmbedding, CodeEmbedding.chunk_id == CodeChunk.id)
        .where(
            CodeEmbedding.repository_id == repository_id,
            CodeEmbedding.embedding_model == REQUIRED_EMBEDDING_MODEL,
            CodeChunk.repository_id == repository_id,
        )
        .order_by(distance_expr.asc())
        .limit(top_k)
    )

    rows = db.execute(stmt).all()
    results: list[dict] = []
    for chunk, distance in rows:
        similarity = max(0.0, min(1.0, 1.0 - float(distance)))
        results.append(
            {
                "chunk_id": chunk.id,
                "file_path": chunk.file_path,
                "start_line": chunk.start_line,
                "end_line": chunk.end_line,
                "symbol_name": chunk.symbol_name,
                "chunk_type": chunk.chunk_type,
                "similarity": round(similarity, 4),
                "content": chunk.content,
            }
        )
    return results
