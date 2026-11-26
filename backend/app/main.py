from contextlib import asynccontextmanager
import threading
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes.auth import router as auth_router
from app.api.routes.health import router as health_router
from app.api.routes.repositories import router as repositories_router
from app.core.config import get_settings
from app.core.errors import register_exception_handlers


def _prewarm_embedding_model() -> None:
    """Load sentence-transformers/all-MiniLM-L6-v2 in the background so first search is fast."""
    try:
        from app.services.embedding_service import _load_sentence_transformer

        settings = get_settings()
        model_name = settings.EMBEDDING_MODEL.strip() or "sentence-transformers/all-MiniLM-L6-v2"
        _load_sentence_transformer(model_name)
    except Exception:
        pass


@asynccontextmanager
async def lifespan(_app: FastAPI):
    thread = threading.Thread(target=_prewarm_embedding_model, daemon=True)
    thread.start()
    yield


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    settings = get_settings()

    app = FastAPI(
        title=settings.APP_NAME,
        debug=settings.DEBUG,
        version="0.1.0",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type"],
    )

    register_exception_handlers(app)

    app.include_router(health_router)
    app.include_router(health_router, prefix="/api")
    app.include_router(auth_router, prefix="/api")
    app.include_router(repositories_router, prefix="/api")

    @app.get("/", tags=["Root"])
    async def root() -> dict:
        return {
            "name": settings.APP_NAME,
            "status": "running",
            "docs": "/docs",
            "health": "/health",
        }

    return app


app = create_app()
