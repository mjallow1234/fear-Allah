from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.db.models import ChannelMember

async def get_channel_member(db: AsyncSession, channel_id: int, user_id: int):
    query = select(ChannelMember).where(ChannelMember.channel_id == channel_id, ChannelMember.user_id == user_id)
    result = await db.execute(query)
    return result.scalar_one_or_none()


# Legacy DM migration helpers
async def get_legacy_dm_mapping_by_channel(db: AsyncSession, legacy_channel_id: int):
    from app.db.models import LegacyDMMigration
    q = select(LegacyDMMigration).where(LegacyDMMigration.legacy_channel_id == legacy_channel_id)
    r = await db.execute(q)
    return r.scalar_one_or_none()

async def create_legacy_dm_mapping(db: AsyncSession, legacy_channel_id: int, direct_conversation_id: int, message_count: int = 0):
    from app.db.models import LegacyDMMigration
    # Idempotent create
    existing = await get_legacy_dm_mapping_by_channel(db, legacy_channel_id)
    if existing:
        return existing
    m = LegacyDMMigration(legacy_channel_id=legacy_channel_id, direct_conversation_id=direct_conversation_id, message_count=message_count, migrated=False)
    db.add(m)
    await db.commit()
    await db.refresh(m)
    return m

async def mark_legacy_dm_migrated(db: AsyncSession, legacy_channel_id: int):
    from app.db.models import LegacyDMMigration
    m = await get_legacy_dm_mapping_by_channel(db, legacy_channel_id)
    if not m:
        return None
    m.migrated = True
    from datetime import datetime
    m.migrated_at = datetime.utcnow()
    db.add(m)
    await db.commit()
    await db.refresh(m)
    return m

async def is_channel_migrated(db: AsyncSession, channel_id: int) -> bool:
    m = await get_legacy_dm_mapping_by_channel(db, channel_id)
    return bool(m and m.migrated)
