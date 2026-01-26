#!/usr/bin/env python3
"""Reset a user's password script."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from passlib.context import CryptContext
import asyncio
from sqlalchemy import text
from app.db.database import async_session

pwd_context = CryptContext(schemes=['bcrypt'], deprecated='auto')

if len(sys.argv) < 3:
    print('Usage: reset_user_pw.py <username> <newpass>')
    sys.exit(1)

username = sys.argv[1]
new = sys.argv[2]

h = pwd_context.hash(new)

async def reset_password():
    async with async_session() as session:
        await session.execute(text("UPDATE users SET hashed_password = :h WHERE username = :u"), {'h': h, 'u': username})
        await session.commit()
        print(f'Password for {username} reset')

asyncio.run(reset_password())
