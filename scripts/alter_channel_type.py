import asyncio
import asyncpg

async def main():
    conn = await asyncpg.connect('postgresql://fearallah:fearallah@localhost:5432/fear_allah')
    try:
        await conn.execute("ALTER TABLE channels ALTER COLUMN type TYPE channeltype USING type::channeltype;")
        print('Altered channels.type to channeltype enum successfully')
    except Exception as e:
        print('Error altering column:', e)
    finally:
        await conn.close()

if __name__ == '__main__':
    asyncio.run(main())