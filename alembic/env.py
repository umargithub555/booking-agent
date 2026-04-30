"""
Alembic migration environment.
Uses a SYNC psycopg2 engine — Alembic does not support async engines.
All models are auto-discovered by importing app.db.models.
"""
from logging.config import fileConfig
from app.core.config import settings
from sqlalchemy import engine_from_config, pool
from alembic import context

# Import Base from models (single source of truth)
from app.db.models import Base

# Import all models so Alembic can detect them for autogenerate
import app.db.models  # noqa: F401


def _sync_url(url: str) -> str:
    """
    Convert an async database URL to a sync one for Alembic.
    e.g. postgresql+asyncpg://... -> postgresql+psycopg2://...
         postgresql+aiopg://...   -> postgresql+psycopg2://...
    Falls back gracefully if the driver scheme is not async.
    """
    return (
        url
        .replace("postgresql+asyncpg", "postgresql+psycopg2")
        .replace("postgresql+aiopg", "postgresql+psycopg2")
    )

# ── Alembic config object ─────────────────────────────────────────────────────
config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Point Alembic at the schema
target_metadata = Base.metadata


# ── OFFLINE mode (generate SQL without connecting) ────────────────────────────
def run_migrations_offline() -> None:
    """Emit SQL to stdout without a live DB connection."""
    # url = config.get_main_option("sqlalchemy.url")
    url = _sync_url(settings.DATABASE_URL)
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        compare_server_default=True,
    )
    with context.begin_transaction():
        context.run_migrations()


# ── ONLINE mode (connect and run migrations) ──────────────────────────────────
def run_migrations_online() -> None:
    """Run migrations against a live database using a sync connection."""
    instance_url = _sync_url(settings.DATABASE_URL)
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,   # No pooling for migration runs
        url=instance_url
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,              # Detect column type changes
            compare_server_default=True,    # Detect default value changes
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
