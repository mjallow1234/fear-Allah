"""Migration script: Migrate legacy DM channels (Channel.type == direct) into DirectConversation.

Usage (run from repository root, with virtualenv active):
    python -m scripts.migrate_legacy_dms discover
    python -m scripts.migrate_legacy_dms migrate --channel 123
    python -m scripts.migrate_legacy_dms cutover --channel 123
    python -m scripts.migrate_legacy_dms migrate-all
    python -m scripts.migrate_legacy_dms cutover-all

This script is safe, additive and idempotent. It logs skipped items and never deletes data.
"""
import argparse
import asyncio
import logging
from typing import List, Dict

from app.db.database import async_session
from sqlalchemy import select, func
from app.db.models import Channel, ChannelMember, Message, DirectConversation, DirectConversationParticipant
from app.db.crud import get_legacy_dm_mapping_by_channel, create_legacy_dm_mapping, mark_legacy_dm_migrated

logger = logging.getLogger("migrate_legacy_dms")
logging.basicConfig(level=logging.INFO)


async def discover_legacy_dms():
    results = []
    async with async_session() as db:
        q = select(Channel).where(Channel.type == 'direct')
        r = await db.execute(q)
        channels = r.scalars().all()

        for ch in channels:
            # Count members
            m_q = select(ChannelMember).where(ChannelMember.channel_id == ch.id)
            m_r = await db.execute(m_q)
            members = m_r.scalars().all()
            if len(members) != 2:
                logger.warning(f"Skipping channel {ch.id}: expected 2 members, found {len(members)}")
                continue

            # Count messages
            msg_q = select(func.count(Message.id)).where(Message.channel_id == ch.id)
            msg_r = await db.execute(msg_q)
            msg_count = msg_r.scalar_one() or 0
            if msg_count == 0:
                logger.warning(f"Skipping channel {ch.id}: no messages")
                continue

            results.append({
                "channel_id": ch.id,
                "member_ids": [m.user_id for m in members],
                "created_at": ch.created_at,
                "message_count": msg_count,
            })
    return results


async def migrate_channel(legacy_channel_id: int, db=None):
    """Migrate a single legacy DM channel to DirectConversation.
    If an AsyncSession `db` is provided it will be used (useful for tests)."""
    own_session = False
    if db is None:
        own_session = True
        db = async_session()
    # Use a context manager only if we created the session
    if own_session:
        async with db as session:
            return await _migrate_channel_impl(legacy_channel_id, session)
    else:
        return await _migrate_channel_impl(legacy_channel_id, db)


async def _migrate_channel_impl(legacy_channel_id: int, db):
    # Check idempotency
    existing = await get_legacy_dm_mapping_by_channel(db, legacy_channel_id)
    if existing:
        logger.info(f"Mapping already exists for channel {legacy_channel_id}; skipping migration")
        return existing

    # Load channel
    q = select(Channel).where(Channel.id == legacy_channel_id, Channel.type == 'direct')
    r = await db.execute(q)
    ch = r.scalar_one_or_none()
    if not ch:
        logger.warning(f"Channel {legacy_channel_id} not found or not a direct channel; skipping")
        return None

    # Members (expect exactly 2)
    m_q = select(ChannelMember).where(ChannelMember.channel_id == ch.id)
    m_r = await db.execute(m_q)
    members = m_r.scalars().all()
    if len(members) != 2:
        logger.warning(f"Skipping channel {ch.id}: expected 2 members, found {len(members)}")
        return None

    # Determine deterministic created_by (min user id)
    user_ids = sorted([m.user_id for m in members])
    created_by = user_ids[0]
    pair_key = f"{min(user_ids)}:{max(user_ids)}"

    # Create DirectConversation
    conv = DirectConversation(created_by_user_id=created_by, participant_pair=pair_key, created_at=ch.created_at)
    db.add(conv)
    await db.flush()

    # Create DirectConversationParticipant preserving joined_at
    parts = []
    for m in members:
        p = DirectConversationParticipant(direct_conversation_id=conv.id, user_id=m.user_id, joined_at=m.created_at)
        db.add(p)
        parts.append(p)

    # Message count
    msg_q = select(func.count(Message.id)).where(Message.channel_id == ch.id)
    msg_r = await db.execute(msg_q)
    msg_count = msg_r.scalar_one() or 0

    await db.commit()
    await db.refresh(conv)

    # Create mapping record
    mapping = await create_legacy_dm_mapping(db, legacy_channel_id=ch.id, direct_conversation_id=conv.id, message_count=msg_count)
    logger.info(f"Created mapping for legacy channel {ch.id} -> direct_conversation {conv.id} (messages: {msg_count})")
    return mapping


async def cutover_channel(legacy_channel_id: int, db=None):
    """Perform cutover: set messages.direct_conversation_id and NULL channel_id in one transaction, mark mapping migrated.
    Accepts optional `db` AsyncSession for test reentrancy."""
    own_session = False
    if db is None:
        own_session = True
        db = async_session()

    if own_session:
        async with db as session:
            return await _cutover_channel_impl(legacy_channel_id, session)
    else:
        return await _cutover_channel_impl(legacy_channel_id, db)


async def _cutover_channel_impl(legacy_channel_id: int, db):
    mapping = await get_legacy_dm_mapping_by_channel(db, legacy_channel_id)
    if not mapping:
        logger.warning(f"No mapping found for channel {legacy_channel_id}; cannot cutover")
        return None
    if mapping.migrated:
        logger.info(f"Channel {legacy_channel_id} already cutover")
        return mapping

    # Update messages atomically: set direct_conversation_id and null channel_id
    # Use the provided session (which may be in a transaction in tests)
    # We perform an atomic UPDATE and then update the mapping
    count_q = select(func.count(Message.id)).where(Message.channel_id == legacy_channel_id)
    count_res = await db.execute(count_q)
    count = count_res.scalar_one() or 0

    await db.execute(
        Message.__table__.update().where(Message.channel_id == legacy_channel_id).values(direct_conversation_id=mapping.direct_conversation_id, channel_id=None)
    )

    mapping.message_count = count
    mapping.migrated = True
    from datetime import datetime
    mapping.migrated_at = datetime.utcnow()
    db.add(mapping)
    await db.commit()
    # Expire session state so callers (tests) see updated values
    try:
        await db.expire_all()
    except Exception:
        pass
    await db.refresh(mapping)

    logger.info(f"Cutover complete for channel {legacy_channel_id}: {count} messages migrated to direct conversation {mapping.direct_conversation_id}")
    return mapping


async def migrate_all():
    ds = await discover_legacy_dms()
    logger.info(f"Found {len(ds)} candidate legacy DM channels to migrate")
    for d in ds:
        await migrate_channel(d['channel_id'])


async def cutover_all():
    async with async_session() as db:
        q = select(func.count(LegacyDMMigration.id))
        from app.db.models import LegacyDMMigration
        r = await db.execute(select(LegacyDMMigration).where(LegacyDMMigration.migrated.is_(False)))
        rows = r.scalars().all()
        logger.info(f"Found {len(rows)} mappings to cutover")
        for m in rows:
            await cutover_channel(m.legacy_channel_id)


def main():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest='cmd')
    sub.add_parser('discover')
    p_m = sub.add_parser('migrate')
    p_m.add_argument('--channel', type=int, required=False)
    sub.add_parser('migrate-all')
    p_c = sub.add_parser('cutover')
    p_c.add_argument('--channel', type=int, required=False)
    sub.add_parser('cutover-all')

    args = parser.parse_args()

    cmd = args.cmd
    if cmd == 'discover':
        res = asyncio.run(discover_legacy_dms())
        for r in res:
            logger.info(r)
    elif cmd == 'migrate':
        if not args.channel:
            print('Please specify --channel ID')
            return
        asyncio.run(migrate_channel(args.channel))
    elif cmd == 'migrate-all':
        asyncio.run(migrate_all())
    elif cmd == 'cutover':
        if not args.channel:
            print('Please specify --channel ID')
            return
        asyncio.run(cutover_channel(args.channel))
    elif cmd == 'cutover-all':
        asyncio.run(cutover_all())
    else:
        parser.print_help()


if __name__ == '__main__':
    main()
