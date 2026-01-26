import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import asyncio
from sqlalchemy import text
from app.db.database import async_engine

async def main():
    async with async_engine.begin() as conn:
        res = await conn.execute(text("select id, slug, service_target, field_mapping from forms where slug='orders'"))
        rows = res.fetchall()
        for r in rows:
            print(r)

asyncio.run(main())
