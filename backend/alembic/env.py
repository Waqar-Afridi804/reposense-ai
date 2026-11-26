from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from app.core.config import get_settings
from app.db.base import Base
import app.db.models  # noqa: F401  Ensure all models are registered on Base.metadata

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def get_database_url() -> str:
    """Resolve database URL from Pydantic settings (backend/.env)."""
    settings = get_settings()
    if settings.is_database_configured:
        return settings.sqlalchemy_database_uri
    return "postgresql+psycopg://localhost/reposense_ai"


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode (SQL generation without live DB)."""
    url = get_database_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode against Supabase PostgreSQL."""
    settings = get_settings()
    if not settings.is_database_configured:
        raise RuntimeError(
            "DATABASE_URL is not configured in backend/.env. "
            "Set a valid Supabase PostgreSQL connection string before running online migrations."
        )

    section = config.get_section(config.config_ini_section, {})
    section["sqlalchemy.url"] = settings.sqlalchemy_database_uri

    connectable = engine_from_config(
        section,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
