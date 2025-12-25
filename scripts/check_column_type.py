import asyncio
import asyncpg

async def main():
    conn = await asyncpg.connect('postgresql://fearallah:fearallah@localhost:5432/fear_allah')
    rows = await conn.fetch("SELECT column_name, data_type, udt_name FROM information_schema.columns WHERE table_name='channels' AND column_name='type';")
    for r in rows:
        print(dict(r))
    await conn.close()

if __name__ == '__main__':
    asyncio.run(main())