"""
Database connection — async engine for FastAPI + sync engine for Alembic.
"""
import os
from app.core.config import settings
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

# ── URLs ──────────────────────────────────────────────────────────────────────
# asyncpg driver for the application (async)
ASYNC_DATABASE_URL = settings.DATABASE_URL

# psycopg2 driver for Alembic migrations (sync)
# SYNC_DATABASE_URL = ASYNC_DATABASE_URL.replace("postgresql+asyncpg://", "postgresql+psycopg2://")

# ── ASYNC ENGINE (used by FastAPI) ────────────────────────────────────────────
async_engine = create_async_engine(
    ASYNC_DATABASE_URL,
    echo=False,
    pool_size=20,
    max_overflow=10,
    pool_pre_ping=True,   # validates connection before use
)

AsyncSessionLocal = async_sessionmaker(
    bind=async_engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

# ── FastAPI dependency ─────────────────────────────────────────────────────────
async def get_db():
    """Inject an async DB session into route handlers."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()