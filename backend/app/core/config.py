from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from backend/.env."""

    APP_NAME: str = "RepoSense AI"
    DEBUG: bool = True

    # Database & Supabase (kept strictly on backend)
    DATABASE_URL: str = ""
    SUPABASE_URL: str = ""
    SUPABASE_PUBLISHABLE_KEY: str = ""
    SUPABASE_SECRET_KEY: str = ""

    # GitHub & AI Configuration
    GITHUB_TOKEN: str = ""
    GITHUB_TIMEOUT_SECONDS: float = 20.0
    MAX_REPO_SIZE_KB: int = 100_000
    MAX_FILE_SIZE_BYTES: int = 200_000
    MAX_FILES_PER_REPO: int = 250
    GEMINI_API_KEY: str = ""
    GEMINI_MODEL: str = "gemini-3-flash-preview"
    EMBEDDING_MODEL: str = "sentence-transformers/all-MiniLM-L6-v2"
    HF_TOKEN: str = ""

    # CORS
    CORS_ORIGINS: str = "http://localhost:5173"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def cors_origins_list(self) -> list[str]:
        """Parse comma-separated CORS origins into a clean list."""
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]

    @property
    def is_database_configured(self) -> bool:
        """Return True when DATABASE_URL is set to a non-placeholder Postgres URI."""
        url = self.DATABASE_URL.strip()
        if not url or "YOUR_SUPABASE" in url:
            return False
        return url.startswith(("postgres://", "postgresql://", "postgresql+psycopg://"))

    @property
    def sqlalchemy_database_uri(self) -> str:
        """Return SQLAlchemy-compatible PostgreSQL URI using the psycopg 3 driver."""
        url = self.DATABASE_URL.strip()
        if url.startswith("postgres://"):
            return "postgresql+psycopg://" + url[len("postgres://"):]
        if url.startswith("postgresql://"):
            return "postgresql+psycopg://" + url[len("postgresql://"):]
        return url


@lru_cache
def get_settings() -> Settings:
    """Return cached application settings instance."""
    return Settings()
