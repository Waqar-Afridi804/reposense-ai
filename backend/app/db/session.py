from collections.abc import Generator
from functools import lru_cache
from fastapi import status
from sqlalchemy import create_engine, Engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings
from app.core.errors import AppError


@lru_cache
def get_engine() -> Engine:
    """Create and cache the SQLAlchemy engine using backend/.env DATABASE_URL."""
    settings = get_settings()
    if not settings.is_database_configured:
        raise AppError(
            message="Database is not configured. Set a valid DATABASE_URL in backend/.env.",
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            code="database_not_configured",
        )

    return create_engine(
        settings.sqlalchemy_database_uri,
        pool_pre_ping=True,
        pool_size=5,
        max_overflow=10,
        connect_args={"connect_timeout": 30},
    )


def get_session_factory() -> sessionmaker[Session]:
    """Return a sessionmaker bound to the configured engine."""
    return sessionmaker(autocommit=False, autoflush=False, bind=get_engine())


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency yielding a scoped SQLAlchemy database session."""
    session_local = get_session_factory()
    db = session_local()
    try:
        yield db
    finally:
        db.close()
