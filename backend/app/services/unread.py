from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.models import Message
from app.db.crud import get_channel_member


async def get_unread_count(db: AsyncSession, channel_id: int, user_id: int) -> int:
    """Return number of unread messages for a user in a channel.

    A message is unread iff message.created_at > channel_members.last_read_at.
    If last_read_at is None -> all messages are unread.
    """
    member = await get_channel_member(db, channel_id, user_id)
    if not member:
        return 0

    q = select(func.count(Message.id)).where(Message.channel_id == channel_id, Message.is_deleted == False)
    if member.last_read_at:
        q = q.where(Message.created_at > member.last_read_at)

    result = await db.execute(q)
    count = result.scalar_one() or 0
    return int(count)
