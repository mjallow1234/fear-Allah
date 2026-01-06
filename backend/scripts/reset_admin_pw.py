#!/usr/bin/env python3
"""Reset admin password script."""
import sys
import os

# Ensure the app module can be imported
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from passlib.context import CryptContext
import asyncio
from sqlalchemy import text
from app.db.database import async_session

pwd_context = CryptContext(schemes=['bcrypt'], deprecated='auto')
h = pwd_context.hash('Admin123!')

async def reset_password():
    async with async_session() as session:
        await session.execute(text("UPDATE users SET hashed_password = :h WHERE username = 'admin'"), {'h': h})
        await session.commit()
        
asyncio.run(reset_password())
print('Password reset successfully!')
