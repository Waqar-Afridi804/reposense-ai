from datetime import datetime, timezone
from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.core.auth import AuthenticatedUser, get_current_user
from app.core.cache import health_cache
from app.core.config import Settings, get_settings
from app.db.session import get_engine
from app.schemas.repository import DatabaseHealthResponse

router = APIRouter(tags=["Health"])


@router.get("/health")
async def health_check(settings: Settings = Depends(get_settings)) -> dict:
    """Return service health status and non-sensitive configuration metadata."""
    return {
        "status": "ok",
        "service": settings.APP_NAME,
        "debug": settings.DEBUG,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/health/db", response_model=DatabaseHealthResponse)
async def database_health_check(
    _current_user: AuthenticatedUser = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> DatabaseHealthResponse:
    """Check Supabase PostgreSQL connectivity and pgvector extension status."""
    if not settings.is_database_configured:
        return DatabaseHealthResponse(
            status="unconfigured",
            configured=False,
            connected=False,
            pgvector_enabled=False,
            pgvector_version=None,
            detail="DATABASE_URL is missing or still set to a placeholder in backend/.env.",
        )

    cached = health_cache.get("db_health")
    if cached is not None:
        return cached

    try:
        engine = get_engine()
        with engine.connect() as conn:
            vector_version = conn.execute(
                text("SELECT (SELECT extversion FROM pg_extension WHERE extname = 'vector')")
            ).scalar()

        result = DatabaseHealthResponse(
            status="ok" if vector_version else "degraded",
            configured=True,
            connected=True,
            pgvector_enabled=bool(vector_version),
            pgvector_version=vector_version,
            detail=(
                "Connected to PostgreSQL and pgvector is enabled."
                if vector_version
                else "Connected to PostgreSQL, but pgvector extension is not enabled. Run: CREATE EXTENSION IF NOT EXISTS vector;"
            ),
        )
        health_cache.set("db_health", result, ttl=30.0)
        return result
    except SQLAlchemyError:
        return DatabaseHealthResponse(
            status="error",
            configured=True,
            connected=False,
            pgvector_enabled=False,
            pgvector_version=None,
            detail="Failed to connect to PostgreSQL. Verify DATABASE_URL and network access.",
        )
