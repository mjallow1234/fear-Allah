import os
import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
# Use a shared in-memory SQLite database for tests so multiple connections see the same DB
# Note the 'file::memory:?cache=shared' URI and uri=True in connect args below
# Default DATABASE_URL (not used by tests that use the per-fixture engine)
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
from app.main import app
from app.db.database import Base, get_db

# Note: tests will create a temporary on-disk SQLite file per `test_engine` fixture to avoid
# in-memory connection isolation on Windows/SQLite and to allow concurrent connections.
# We intentionally do not set a global TEST_DATABASE_URL here.
TEST_DATABASE_URL = None


@pytest.fixture(scope="session")
def anyio_backend():
    return "asyncio"


@pytest.fixture(scope="session")
async def test_engine():
    engine = create_async_engine(
        "sqlite+aiosqlite:///./test_concurrency.db",
        connect_args={"check_same_thread": False},
    )

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    await engine.dispose()

@pytest.fixture
async def test_session(test_engine):
    async_session = sessionmaker(
        test_engine, class_=AsyncSession, expire_on_commit=False
    )
    async with async_session() as session:
        yield session


@pytest.fixture
async def client(test_session):
    # After each HTTP response in tests, expire all objects on the test_session so
    # the test session sees DB changes made by the app's request-handling sessions.
    async def _on_response(response):
        # Refresh all loaded instances in the test session so attribute access doesn't
        # trigger synchronous DB IO (MissingGreenlet) later on.
        try:
            # Make a snapshot of identity map to avoid modification during iteration
            instances = list(test_session.identity_map.values())
            for inst in instances:
                try:
                    await test_session.refresh(inst)
                except Exception:
                    # Ignore refresh errors for detached/expired objects
                    pass
        except Exception:
            pass

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        event_hooks={"response": [_on_response]},
    ) as ac:
        yield ac


@pytest.fixture(scope="session", autouse=True)
async def override_get_db_for_app(test_engine):
    """Override app's get_db dependency once per test session to use the session-scoped engine.
    This yields a fresh session per request while keeping a single AsyncEngine for the app and tests.
    """
    from sqlalchemy.ext.asyncio import AsyncSession
    from sqlalchemy.orm import sessionmaker

    async_session = sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)

    async def _override_get_db():
        async with async_session() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    app.dependency_overrides[get_db] = _override_get_db
    yield
    app.dependency_overrides.clear()


@pytest.fixture(autouse=True)
async def clean_tables(test_engine):
    """Ensure DB is empty before each test by deleting from all tables (keep schema intact)."""
    async with test_engine.begin() as conn:
        # delete in reverse order to respect FK constraints
        for table in reversed(Base.metadata.sorted_tables):
            await conn.execute(table.delete())
    yield
    # No teardown step needed (tables remain, rows should be empty)
