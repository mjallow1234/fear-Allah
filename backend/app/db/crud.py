from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.db.models import ChannelMember

async def get_channel_member(db: AsyncSession, channel_id: int, user_id: int):
    query = select(ChannelMember).where(ChannelMember.channel_id == channel_id, ChannelMember.user_id == user_id)
    result = await db.execute(query)
    return result.scalar_one_or_none()
