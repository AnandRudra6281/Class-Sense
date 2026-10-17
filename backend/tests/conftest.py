import os
import sys
from pathlib import Path
from typing import AsyncGenerator
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

# Ensure backend root is on sys.path
backend_path = Path(__file__).resolve().parent.parent
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

# Force test database URL and clear test keys
import tempfile
import shutil

TEST_CHROMA_DIR = Path(tempfile.mkdtemp(prefix="test_chroma_"))
TEST_DB_PATH = backend_path / "test_classsense.db"
os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{TEST_DB_PATH.as_posix()}"
os.environ["CHROMA_PERSIST_DIR"] = str(TEST_CHROMA_DIR)
os.environ["DEBUG"] = "true"
os.environ["OPENAI_API_KEY"] = ""
os.environ["SARVAM_API_KEY"] = ""

from app.core.config import settings
from app.core.database import Base, get_db
from app.main import app

# Ensure keys are empty for provider isolation tests and Chroma points to temp dir
settings.OPENAI_API_KEY = ""
settings.SARVAM_API_KEY = ""
settings.CHROMA_PERSIST_DIR = TEST_CHROMA_DIR
settings.DATABASE_URL = f"sqlite+aiosqlite:///{TEST_DB_PATH.as_posix()}"

from sqlalchemy import event

test_engine = create_async_engine(
    f"sqlite+aiosqlite:///{TEST_DB_PATH.as_posix()}",
    connect_args={"check_same_thread": False, "timeout": 30.0},
    future=True,
)

@event.listens_for(test_engine.sync_engine, "connect")
def set_test_sqlite_pragma(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA busy_timeout=5000")
    cursor.close()

TestingSessionLocal = async_sessionmaker(
    bind=test_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)

import app.core.database as db_module
import app.db.session as session_module

db_module.engine = test_engine
db_module.async_session_factory = TestingSessionLocal
session_module.engine = test_engine
session_module.async_session_factory = TestingSessionLocal


@pytest.fixture(scope="session")
def anyio_backend():
    return "asyncio"


@pytest.fixture(scope="session", autouse=True)
def cleanup_test_chroma():
    yield
    shutil.rmtree(TEST_CHROMA_DIR, ignore_errors=True)


@pytest.fixture(autouse=True)
async def setup_test_db():
    from sqlalchemy import text
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.execute(text("DROP TABLE IF EXISTS alembic_version"))



async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
    async with TestingSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


app.dependency_overrides[get_db] = override_get_db


@pytest.fixture
async def client() -> AsyncGenerator[AsyncClient, None]:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    async with TestingSessionLocal() as session:
        yield session
