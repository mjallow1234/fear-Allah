import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import asyncio
from sqlalchemy import select
from app.db.database import async_session
from app.db.models import Task

async def main():
    async with async_session() as session:
        res = await session.execute(select(Task).where(Task.step_key=='assemble_items', Task.status=='active'))
        rows = res.scalars().all()
        for t in rows:
            print(t.id, t.order_id, t.step_key, t.title, t.status)

asyncio.run(main())
