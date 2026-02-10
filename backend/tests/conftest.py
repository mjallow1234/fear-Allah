import os
import sys
import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

# Make sure backend package is importable when running pytest from repo root
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

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


@pytest.fixture()
async def user_token(test_session):
    """Create a DB-backed user and return an Authorization header.

    Tests can use this fixture to avoid calling the rate-limited /api/auth endpoints.
    """
    from app.db.models import User
    from app.core.security import create_access_token, get_password_hash

    # Create user directly in the DB to avoid hitting auth endpoints
    user = User(
        email="testuser@example.com",
        username="testuser",
        display_name="testuser",
        hashed_password=get_password_hash("testpass123"),
        is_active=True,
    )
    test_session.add(user)
    await test_session.commit()
    await test_session.refresh(user)

    token = create_access_token({"sub": str(user.id), "username": user.username, "is_system_admin": user.is_system_admin})
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
async def async_client_authenticated(client, test_session):
    """Create a user and attach Authorization header to the provided test client.

    Returns a tuple of (client, user_data) where client has default auth header set and
    user_data contains user_id/token for convenience.
    """
    from app.db.models import User
    from app.core.security import create_access_token, get_password_hash

    user = User(
        email="auto_user@example.com",
        username="auto_user",
        display_name="Auto User",
        hashed_password=get_password_hash("autopass"),
        is_active=True,
    )
    test_session.add(user)
    await test_session.commit()
    await test_session.refresh(user)

    token = create_access_token({"sub": str(user.id), "username": user.username})

    # Ensure an operational role exists and assign the test user to an 'agent' operational role
    from app.db.models import Role, UserRole
    # Create or get 'agent' role
    role = Role(name='agent', is_system=False)
    test_session.add(role)
    await test_session.commit()
    await test_session.refresh(role)

    user_role = UserRole(user_id=user.id, role_id=role.id)
    test_session.add(user_role)
    await test_session.commit()

    # Set default Authorization header on the client used by tests
    client.headers.update({"Authorization": f"Bearer {token}"})

    return client, {"user_id": user.id, "username": user.username, "token": token}


@pytest.fixture(scope="session")
def test_engine():
    import asyncio

    engine = create_async_engine(
        "sqlite+aiosqlite:///./test_concurrency.db",
        connect_args={"check_same_thread": False},
    )

    async def _setup():
        async with engine.begin() as conn:
            # Ensure we recreate schema for each test session so models and tests stay in sync
            try:
                await conn.run_sync(Base.metadata.drop_all)
            except Exception:
                pass
            await conn.run_sync(Base.metadata.create_all)

    loop = asyncio.get_event_loop()
    loop.run_until_complete(_setup())

    try:
        yield engine
    finally:
        async def _teardown():
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.drop_all)
            await engine.dispose()

        loop.run_until_complete(_teardown())

@pytest.fixture
async def test_session(test_engine, request):
    async_session = sessionmaker(
        test_engine, class_=AsyncSession, expire_on_commit=False
    )
    # Construct an AsyncSession instance and return it directly so tests receive a resolved session
    session = async_session()

    # Schedule session close when the test finishes
    import asyncio
    def _schedule_close():
        try:
            loop = asyncio.get_event_loop()
            loop.create_task(session.close())
        except Exception:
            pass

    request.addfinalizer(_schedule_close)
    return session


# Backwards compatible alias used across many tests
@pytest.fixture
async def db_session(test_session):
    """Provide a database session fixture aliasing `test_session` for tests that
    reference `db_session` directly."""
    yield test_session


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

    # Ensure modules that use the global async_session (e.g., realtime socket helpers)
    # use the same AsyncEngine/session factory as the tests so DB lookups inside
    # those helpers see the same test data.
    import app.db.database as _db_mod
    _db_mod.async_engine = test_engine
    _db_mod.async_session = async_session

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
