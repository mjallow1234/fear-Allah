"""Script to run assignment backfill once."""
import asyncio
from app.db.database import async_session
from app.automation.backfill import backfill_assignments


async def main():
    async with async_session() as db:
        updated = await backfill_assignments(db)
        print(f"Backfill completed. Updated {updated} assignment(s).")


if __name__ == "__main__":
    asyncio.run(main())
