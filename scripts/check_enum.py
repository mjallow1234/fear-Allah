import asyncio
import asyncpg

async def main():
    conn = await asyncpg.connect('postgresql://fearallah:fearallah@localhost:5432/fear_allah')
    rows = await conn.fetch("SELECT typname FROM pg_type WHERE typname='channeltype' OR typname='userstatus' OR typname='userrole';")
    for r in rows:
        print(dict(r))
    await conn.close()

if __name__ == '__main__':
    asyncio.run(main())