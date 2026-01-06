"""Idempotent staging seed script.
Usage (staging only):

APP_ENV=staging python backend/scripts/seed_staging.py
"""
import asyncio
import random
from datetime import datetime, timedelta
from typing import List
from sqlalchemy import text

from app.core.config import settings, logger
from app.db.database import async_session
from app.db.models import User, Channel, ChannelMember, Message
from app.db.enums import UserRole
from app.core.security import get_password_hash

# Realistic chat messages for different channels
REALISTIC_MESSAGES = {
    "general": [
        "Assalamu alaikum everyone 👋",
        "Wa alaikum assalam! How's everyone doing today?",
        "Alhamdulillah, all good here. Just finished my morning tasks.",
        "Has anyone seen the latest project updates?",
        "Yes, I reviewed them yesterday. Looking great!",
        "JazakAllah khair for the quick response 🙏",
        "Can someone help me with the new feature?",
        "Sure, what do you need help with?",
        "I'll check and get back to you in a bit.",
        "Thanks team, really appreciate the support!",
        "Don't forget we have a meeting at 3pm.",
        "Oh right, thanks for the reminder!",
        "Is everyone able to join?",
        "I should be there inshaAllah.",
        "Same here, see you all then.",
        "Quick update: the deployment went smoothly.",
        "MashaAllah, great work everyone!",
        "Let's keep up the momentum 💪",
        "Any blockers we should discuss?",
        "Nothing major on my end.",
        "All clear here too.",
        "Perfect, let's keep moving forward.",
        "Who's handling the code review?",
        "I can take that on.",
        "Thanks, I'll assign it to you.",
        "The documentation is now updated.",
        "Excellent, I'll take a look.",
        "Let me know if anything needs clarification.",
        "Will do, JazakAllah khair!",
        "Alhamdulillah for another productive day.",
    ],
    "announcements": [
        "📢 Welcome to the announcements channel!",
        "Important: Please read the channel guidelines.",
        "New feature release coming next week inshaAllah.",
        "System maintenance scheduled for Friday.",
        "Please save your work before the maintenance window.",
        "Update: The maintenance is now complete.",
        "JazakAllah khair for your patience.",
        "Reminder: Submit your weekly reports by Thursday.",
        "Team meeting rescheduled to 4pm.",
        "New team member joining next week, welcome them!",
        "Policy update: Please review the new guidelines.",
        "Security reminder: Update your passwords regularly.",
        "Holiday schedule has been posted.",
        "Office hours extended this week.",
        "Training session available for new tools.",
        "Feedback survey is now open.",
        "Please complete by end of week.",
        "Results from last survey are in.",
        "Thank you all for participating!",
        "Quarterly review meeting next Monday.",
    ],
    "support": [
        "Need help with login issues.",
        "What error are you seeing?",
        "It says 'Invalid credentials'.",
        "Try resetting your password.",
        "That worked, JazakAllah khair!",
        "How do I update my profile?",
        "Go to Settings > Profile.",
        "Found it, thanks!",
        "Is there a way to export data?",
        "Yes, check the Export button in Reports.",
        "Perfect, got it working.",
        "Having trouble with notifications.",
        "Are they enabled in your settings?",
        "Oh, they were turned off. Fixed now!",
        "The app is running slow for me.",
        "Try clearing your cache.",
        "That helped a lot, thanks!",
        "Where can I find the user guide?",
        "It's in the Help section.",
        "JazakAllah khair for the quick help!",
    ],
    "random": [
        "Friday vibes! 🎉",
        "Who else is ready for the weekend?",
        "Can't wait inshaAllah!",
        "Any good book recommendations?",
        "Try 'Reclaim Your Heart' by Yasmin Mogahed.",
        "Adding it to my list, thanks!",
        "What's everyone having for lunch?",
        "Biryani here 🍚",
        "MashaAllah, that sounds delicious!",
        "Coffee break anyone? ☕",
        "Always up for coffee!",
        "Same here 😄",
        "Nice weather today alhamdulillah.",
        "Perfect for a walk after work.",
        "Great idea!",
        "Anyone watching the match tonight?",
        "Definitely, should be exciting!",
        "Let's discuss tomorrow 😁",
        "Happy Friday everyone!",
        "Jummah Mubarak! 🤲",
    ],
}


async def get_or_create_user(session, username: str, email: str, password: str, display_name: str = None, role: UserRole = UserRole.member):
    q = await session.execute(
        text("SELECT id FROM users WHERE email = :email"),
        {"email": email}
    )
    row = q.first()
    if row:
        # Update role for existing user
        await session.execute(
            text("UPDATE users SET role = :role WHERE id = :id"),
            {"role": role.value, "id": row[0]}
        )
        return await session.get(User, row[0])
    user = User(
        username=username, 
        email=email, 
        hashed_password=get_password_hash(password), 
        display_name=display_name or username, 
        is_active=True,
        role=role
    )
    session.add(user)
    await session.flush()
    return user


async def get_or_create_channel(session, name: str, display_name: str = None):
    q = await session.execute(
        text("SELECT id FROM channels WHERE name = :name"),
        {"name": name}
    )
    row = q.first()
    if row:
        return await session.get(Channel, row[0])
    ch = Channel(name=name, display_name=display_name or name, type='public')
    session.add(ch)
    await session.flush()
    return ch


async def update_messages_with_realistic_content(session, channel: Channel, authors: List[User]):
    """Update existing placeholder messages with realistic content."""
    # Get existing messages for this channel
    q = await session.execute(
        text("SELECT id, content FROM messages WHERE channel_id = :cid AND parent_id IS NULL ORDER BY created_at ASC"),
        {"cid": channel.id}
    )
    rows = q.fetchall()
    
    if not rows:
        logger.info('No messages found in channel %s to update', channel.name)
        return
    
    # Get realistic messages for this channel
    channel_messages = REALISTIC_MESSAGES.get(channel.name, REALISTIC_MESSAGES["general"])
    
    updated_count = 0
    for i, row in enumerate(rows):
        msg_id, content = row
        # Only update placeholder messages
        if content.startswith("Seed message") or content.startswith("Message"):
            # Pick a realistic message (cycle through the list)
            new_content = channel_messages[i % len(channel_messages)]
            # Rotate author assignment
            new_author = authors[i % len(authors)]
            await session.execute(
                text("UPDATE messages SET content = :content, author_id = :author_id WHERE id = :id"),
                {"content": new_content, "author_id": new_author.id, "id": msg_id}
            )
            updated_count += 1
    
    if updated_count > 0:
        logger.info('Updated %s placeholder messages in channel %s with realistic content', updated_count, channel.name)
    else:
        logger.info('No placeholder messages to update in channel %s', channel.name)


async def create_messages(session, channel: Channel, authors: List[User], total: int = 30):
    """Create realistic messages if channel is empty."""
    # Check existing count
    q = await session.execute(
        text("SELECT COUNT(id) FROM messages WHERE channel_id = :cid AND parent_id IS NULL"),
        {"cid": channel.id}
    )
    existing = q.scalar_one()
    
    if existing >= total:
        logger.info('Channel %s already has %s messages', channel.name, existing)
        return
    
    to_create = total - existing
    now = datetime.utcnow()
    channel_messages = REALISTIC_MESSAGES.get(channel.name, REALISTIC_MESSAGES["general"])
    
    for i in range(to_create):
        # Spread messages over past 2 days with realistic gaps
        ts = now - timedelta(minutes=(i * 15 + random.randint(0, 10)))
        author = authors[i % len(authors)]
        content = channel_messages[i % len(channel_messages)]
        msg = Message(content=content, channel_id=channel.id, author_id=author.id, created_at=ts)
        session.add(msg)
    
    await session.flush()
    logger.info('Added %s realistic messages to channel %s (now %s total)', to_create, channel.name, existing + to_create)


async def run():
    if settings.APP_ENV == 'production':
        raise RuntimeError('Refusing to seed production database')

    async with async_session() as session:
        # Team users with appropriate roles
        ahmad = await get_or_create_user(session, 'ahmad', 'ahmad@staging.local', 'ahmad123', 'Ahmad', UserRole.system_admin)
        musa = await get_or_create_user(session, 'musa', 'musa@staging.local', 'musa123', 'Musa', UserRole.team_admin)
        alieu = await get_or_create_user(session, 'alieu', 'alieu@staging.local', 'alieu123', 'Alieu', UserRole.member)
        modou = await get_or_create_user(session, 'modou', 'modou@staging.local', 'modou123', 'Modou', UserRole.member)
        junior = await get_or_create_user(session, 'junior', 'junior@staging.local', 'junior123', 'Junior', UserRole.member)
        users = [ahmad, musa, alieu, modou, junior]

        # Channels
        channels = []
        for name in ['general', 'announcements', 'support', 'random']:
            ch = await get_or_create_channel(session, name)
            channels.append(ch)

        # Add memberships
        for ch in channels:
            for u in users:
                q = await session.execute(
                    text("SELECT id FROM channel_members WHERE user_id = :uid AND channel_id = :cid"),
                    {"uid": u.id, "cid": ch.id}
                )
                if not q.first():
                    cm = ChannelMember(user_id=u.id, channel_id=ch.id)
                    session.add(cm)
        await session.flush()

        # Update existing placeholder messages with realistic content
        for ch in channels:
            await update_messages_with_realistic_content(session, ch, users)
        
        # Create new messages if needed (reduced count for cleaner testing)
        for ch in channels:
            await create_messages(session, ch, users, total=30)

        await session.commit()
        logger.info('Seeding complete with team users: ahmad (system_admin), musa (team_admin), alieu, modou, junior (members).')


if __name__ == '__main__':
    asyncio.run(run())