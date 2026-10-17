import logging
from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy import event
from app.core.config import settings
from app.db.base import Base

logger = logging.getLogger("classsense.db")

connect_args = {}
if settings.DATABASE_URL.startswith("sqlite"):
    connect_args["check_same_thread"] = False
    connect_args["timeout"] = 30.0

engine: AsyncEngine = create_async_engine(
    settings.DATABASE_URL,
    echo=False,
    connect_args=connect_args,
    future=True,
)

if settings.DATABASE_URL.startswith("sqlite"):
    @event.listens_for(engine.sync_engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA busy_timeout=5000")
        cursor.close()

async_session_factory = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency that yields an active async database session."""
    async with async_session_factory() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


def get_alembic_config():
    from pathlib import Path
    from alembic.config import Config

    backend_dir = Path(__file__).resolve().parent.parent.parent
    alembic_ini = backend_dir / "alembic.ini"
    alembic_cfg = Config(str(alembic_ini))
    alembic_cfg.set_main_option("script_location", str(backend_dir / "alembic"))
    alembic_cfg.set_main_option("sqlalchemy.url", settings.DATABASE_URL)
    return alembic_cfg


def get_head_alembic_revision() -> str | None:
    from alembic.script import ScriptDirectory
    cfg = get_alembic_config()
    script = ScriptDirectory.from_config(cfg)
    return script.get_current_head()


def run_alembic_upgrade() -> None:
    from alembic import command
    cfg = get_alembic_config()
    command.upgrade(cfg, "head")


def run_alembic_stamp() -> None:
    from alembic import command
    cfg = get_alembic_config()
    command.stamp(cfg, "head")


async def init_db() -> None:
    """Migrate database schema to head using Alembic migrations on startup."""
    import asyncio
    from sqlalchemy import inspect, text

    async with engine.connect() as conn:
        table_names = await conn.run_sync(lambda sync_conn: inspect(sync_conn).get_table_names())
        has_jobs = "jobs" in table_names
        has_alembic = "alembic_version" in table_names
        current_rev = None
        if has_alembic:
            res = await conn.execute(text("SELECT version_num FROM alembic_version LIMIT 1"))
            current_rev = res.scalar_one_or_none()

    head_rev = await asyncio.to_thread(get_head_alembic_revision)
    logger.info(f"init_db check: has_jobs={has_jobs}, current_rev={current_rev}, head_rev={head_rev}")

    if has_jobs and current_rev is None:
        logger.info("Existing database schema detected without alembic version. Stamping as head...")
        await asyncio.to_thread(run_alembic_stamp)
    elif current_rev == head_rev:
        logger.info(f"Database schema is already at head revision ({head_rev}).")
    else:
        logger.info("Applying Alembic database migrations on startup...")
        await asyncio.to_thread(run_alembic_upgrade)
    logger.info("Alembic database migrations applied successfully.")


