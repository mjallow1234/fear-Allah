"""Idempotent staging seed script.
Usage (staging only):

APP_ENV=staging python backend/scripts/seed_staging.py
"""
import asyncio
from datetime import datetime, timedelta
from typing import List

from app.core.config import settings, logger
from app.db.database import async_session
from app.db.models import User, Channel, ChannelMember, Message
from app.core.security import get_password_hash


async def get_or_create_user(session, username: str, email: str, password: str, display_name: str = None):
    q = await session.execute("SELECT id FROM users WHERE email = :email", {"email": email})
    row = q.first()
    if row:
        return await session.get(User, row[0])
    user = User(username=username, email=email, hashed_password=get_password_hash(password), display_name=display_name or username, is_active=True)
    session.add(user)
    await session.flush()
    return user


async def get_or_create_channel(session, name: str, display_name: str = None):
    q = await session.execute("SELECT id FROM channels WHERE name = :name", {"name": name})
    row = q.first()
    if row:
        return await session.get(Channel, row[0])
    ch = Channel(name=name, display_name=display_name or name, type='public')
    session.add(ch)
    await session.flush()
    return ch


async def create_messages(session, channel: Channel, authors: List[User], total: int = 120):
    # Idempotent: find existing count, only add missing messages
    q = await session.execute("SELECT COUNT(id) FROM messages WHERE channel_id = :cid AND parent_id IS NULL", {"cid": channel.id})
    existing = q.scalar_one()
    if existing >= total:
        logger.info('Channel %s already has %s messages, skipping', channel.name, existing)
        return
    to_create = total - existing
    now = datetime.utcnow()
    for i in range(to_create):
        # Spread messages over past 5 days
        ts = now - timedelta(seconds=(i * 60)) - timedelta(days=(i % 5))
        author = authors[i % len(authors)]
        msg = Message(content=f'Seed message {existing + i + 1} for {channel.name}', channel_id=channel.id, author_id=author.id, created_at=ts)
        session.add(msg)
    await session.flush()
    logger.info('Added %s messages to channel %s (now %s total)', to_create, channel.name, total)


async def run():
    if settings.APP_ENV == 'production':
        raise RuntimeError('Refusing to seed production database')

    async with async_session() as session:
        # Ensure basic users
        admin = await get_or_create_user(session, 'admin', 'admin@staging.local', 'admin123', 'Admin')
        mod = await get_or_create_user(session, 'mod', 'mod@staging.local', 'mod123', 'Moderator')
        user1 = await get_or_create_user(session, 'user1', 'user1@staging.local', 'user123', 'User1')
        users = [admin, mod, user1]

        # Channels
        channels = []
        for name in ['general', 'announcements', 'support', 'random']:
            ch = await get_or_create_channel(session, name)
            channels.append(ch)

        # Add memberships
        for ch in channels:
            for u in users:
                q = await session.execute("SELECT id FROM channel_members WHERE user_id = :uid AND channel_id = :cid", {"uid": u.id, "cid": ch.id})
                if not q.first():
                    cm = ChannelMember(user_id=u.id, channel_id=ch.id)
                    session.add(cm)
        await session.flush()

        # Messages
        for ch in channels:
            await create_messages(session, ch, users, total=150)

        await session.commit()
        logger.info('Seeding complete.')


if __name__ == '__main__':
    asyncio.run(run())