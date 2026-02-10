from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base
from sqlalchemy import create_engine
from app.core.config import settings

# Convert sync URL to async
DATABASE_URL = settings.DATABASE_URL
if DATABASE_URL.startswith("postgresql://"):
    ASYNC_DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://", 1)
else:
    ASYNC_DATABASE_URL = DATABASE_URL

# Sync engine for migrations
sync_engine = create_engine(DATABASE_URL)

# Async engine for application
# If running tests and a test_concurrency.db exists, prefer it so module-level async_session
# can see the same DB as the test fixtures that use a separate engine.
if settings.TESTING:
    import os
    test_db_path = os.path.join(os.getcwd(), 'test_concurrency.db')
    if os.path.exists(test_db_path):
        ASYNC_DATABASE_URL = f"sqlite+aiosqlite:///{test_db_path}"
async_engine = create_async_engine(ASYNC_DATABASE_URL, echo=settings.DEBUG)

# Session factory
async_session = async_sessionmaker(async_engine, class_=AsyncSession, expire_on_commit=False)

# Base class for models
Base = declarative_base()


async def get_db():
    async with async_session() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def create_tables():
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
