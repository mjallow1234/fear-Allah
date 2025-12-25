import asyncio
import asyncpg

async def main():
    conn = await asyncpg.connect('postgresql://fearallah:fearallah@localhost:5432/fear_allah')
    rows = await conn.fetch("SELECT column_default FROM information_schema.columns WHERE table_name='channels' AND column_name='type';")
    for r in rows:
        print(r['column_default'])
    await conn.close()

if __name__ == '__main__':
    asyncio.run(main())