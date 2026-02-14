from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.models import Message
from app.db.crud import get_channel_member
from datetime import timezone


def _to_aware(dt):
    """Return a timezone-aware datetime in UTC, or None if dt is None.

    - If `dt` is naive, attach UTC tzinfo (dt.replace(tzinfo=timezone.utc)).
    - If `dt` is already timezone-aware, return as-is.
    """
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


async def get_unread_count(db: AsyncSession, channel_id: int, user_id: int) -> int:
    """Return number of unread messages for a user in a channel.

    A message is unread iff message.created_at > channel_members.last_read_at.
    If last_read_at is None -> all messages are unread.

    Defensive: normalize datetimes to timezone-aware UTC before comparison so
    we never mix offset-naive and offset-aware datetimes.
    """
    member = await get_channel_member(db, channel_id, user_id)
    if not member:
        return 0

    # Normalize ChannelMember.last_read_at to timezone-aware UTC (if present)
    last_read_at = _to_aware(member.last_read_at)

    q = select(func.count(Message.id)).where(Message.channel_id == channel_id, Message.is_deleted == False)
    if last_read_at:
        q = q.where(Message.created_at > last_read_at)

    result = await db.execute(q)
    count = result.scalar_one() or 0
    return int(count)
