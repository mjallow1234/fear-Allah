"""Utility script to reset admin password"""
from passlib.context import CryptContext
import asyncio
from sqlalchemy import text
import sys
sys.path.insert(0, '/app')
from app.db.database import async_engine

pwd_context = CryptContext(schemes=['bcrypt'], deprecated='auto')
hashed = pwd_context.hash('Password123!')

async def update_password():
    async with async_engine.connect() as conn:
        await conn.execute(
            text("UPDATE users SET hashed_password = :hash WHERE username = 'admin'"),
            {'hash': hashed}
        )
        await conn.commit()
        print('Password updated successfully')
        print('New hash:', hashed[:30] + '...')

if __name__ == '__main__':
    asyncio.run(update_password())
