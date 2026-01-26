import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import asyncio
from sqlalchemy import select
from app.db.database import async_session
from app.db.models import TaskAssignment, Task

async def main():
    async with async_session() as s:
        # Join assignments to tasks
        res = await s.execute(select(TaskAssignment).order_by(TaskAssignment.id))
        assigns = res.scalars().all()
        for a in assigns:
            print('assign', a.id, a.task_id, a.user_id, a.role_hint, a.status)

asyncio.run(main())
