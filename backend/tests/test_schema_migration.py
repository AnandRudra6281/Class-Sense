import tempfile
from pathlib import Path
import pytest
from sqlalchemy import inspect, text
from sqlalchemy.ext.asyncio import create_async_engine

from alembic import command
from alembic.config import Config


@pytest.mark.asyncio
async def test_alembic_migration_covers_all_12_entities():
    """Verify that Alembic migration upgrades an empty database to head and creates all 12 domain tables."""
    temp_dir = Path(tempfile.mkdtemp(prefix="test_alembic_db_"))
    test_db_path = temp_dir / "migration_test.db"
    db_url = f"sqlite+aiosqlite:///{test_db_path}"

    backend_dir = Path(__file__).resolve().parent.parent
    alembic_ini = backend_dir / "alembic.ini"
    alembic_cfg = Config(str(alembic_ini))
    alembic_cfg.set_main_option("script_location", str(backend_dir / "alembic"))
    alembic_cfg.set_main_option("sqlalchemy.url", db_url)

    import asyncio
    # Run upgrade to head in separate thread so env.py's asyncio.run succeeds
    await asyncio.to_thread(command.upgrade, alembic_cfg, "head")

    engine = create_async_engine(db_url)
    try:
        async with engine.connect() as conn:
            tables = await conn.run_sync(lambda sync_conn: inspect(sync_conn).get_table_names())

        expected_tables = {
            "jobs",
            "lectures",
            "transcript_segments",
            "topics",
            "confusion_events",
            "evidence",
            "misconceptions",
            "prerequisite_nodes",
            "interventions",
            "student_catchups",
            "quiz_questions",
            "reports",
            "alembic_version",
        }

        for table in expected_tables:
            assert table in tables, f"Expected table '{table}' missing from Alembic migration schema: {tables}"

    finally:
        await engine.dispose()
        import shutil
        shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.mark.asyncio
async def test_sqlite_wal_and_busy_timeout_active():
    """Verify that SQLite connections have WAL journal mode and busy_timeout configured."""
    from app.db.session import engine

    if not str(engine.url).startswith("sqlite"):
        pytest.skip("Test only applicable to SQLite engines")

    async with engine.connect() as conn:
        journal_mode = (await conn.execute(text("PRAGMA journal_mode"))).scalar()
        busy_timeout = (await conn.execute(text("PRAGMA busy_timeout"))).scalar()

        assert str(journal_mode).lower() == "wal"
        assert int(busy_timeout) >= 5000
