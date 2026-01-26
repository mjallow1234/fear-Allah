import asyncio
import sys
from pathlib import Path
# Ensure project root is on sys.path when running from scripts/ directory
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.db.database import async_session
from app.services.task_engine import create_order

async def main():
    async with async_session() as s:
        try:
            o = await create_order(s, 'AGENT_RESTOCK', items='[]', created_by_id=1)
            print('ok', o.id)
        except Exception as e:
            import traceback
            traceback.print_exc()

if __name__ == '__main__':
    asyncio.run(main())
