import asyncio
import asyncpg

async def main():
    conn = await asyncpg.connect('postgresql://fearallah:fearallah@localhost:5432/fear_allah')
    try:
        await conn.execute("BEGIN;")
        await conn.execute("ALTER TABLE channels ALTER COLUMN type SET DEFAULT 'public'::channeltype;")
        await conn.execute("ALTER TABLE channels ALTER COLUMN type TYPE channeltype USING type::channeltype;")
        await conn.execute("COMMIT;")
        print('Migration succeeded')
    except Exception as e:
        await conn.execute("ROLLBACK;")
        print('Migration failed:', e)
    finally:
        await conn.close()

if __name__ == '__main__':
    asyncio.run(main())