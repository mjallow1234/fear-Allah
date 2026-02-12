"""Sales HQ helpers: ensure channel exists and post system messages to it."""
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.db.models import Channel, ChannelMember, Message
from app.db.enums import ChannelType
from app.services.notifications import get_admins_and_managers


async def ensure_sales_hq_channel(db: AsyncSession) -> Channel:
    """Ensure a private 'sales-hq' channel exists and add admins as members."""
    q = select(Channel).where(Channel.name == 'sales-hq')
    res = await db.execute(q)
    ch = res.scalar_one_or_none()
    # If channel exists, ensure admin membership is up-to-date (sync on every call)
    if ch:
        try:
            admin_ids = await get_admins_and_managers(db)
            for uid in admin_ids:
                cm_q = select(ChannelMember).where(ChannelMember.channel_id == ch.id, ChannelMember.user_id == uid)
                cm_res = await db.execute(cm_q)
                if not cm_res.scalar_one_or_none():
                    db.add(ChannelMember(channel_id=ch.id, user_id=uid))
            await db.commit()
            await db.refresh(ch)
        except Exception:
            # best-effort sync; do not fail caller
            pass
        return ch

    # Create channel and add admins
    ch = Channel(
        name='sales-hq',
        display_name='Sales HQ',
        description='Central Sales channel for system alerts',
        type=ChannelType.private.value,
        team_id=None,
    )
    db.add(ch)
    await db.flush()

    admin_ids = await get_admins_and_managers(db)
    for uid in admin_ids:
        # avoid duplicates
        cm_q = select(ChannelMember).where(ChannelMember.channel_id == ch.id, ChannelMember.user_id == uid)
        cm_res = await db.execute(cm_q)
        if not cm_res.scalar_one_or_none():
            db.add(ChannelMember(channel_id=ch.id, user_id=uid))

    await db.commit()
    await db.refresh(ch)
    return ch


async def post_system_message(db: AsyncSession, channel_id: int, content: str) -> Optional[Message]:
    """Post a system-generated message to a channel (author is first admin if available)."""
    admin_ids = await get_admins_and_managers(db)
    author_id = admin_ids[0] if admin_ids else None
    if author_id is None:
        # No admin to attribute message to; do not post
        return None

    msg = Message(content=content, channel_id=channel_id, author_id=author_id)
    db.add(msg)
    await db.commit()
    await db.refresh(msg)

    # Broadcast minimal system message to WS manager (avoid circular import at module level)
    try:
        from app.api.ws import manager
        payload = {
            "type": "message",
            "system": True,
            "message": {
                "id": msg.id,
                "content": msg.content,
                "author_id": msg.author_id,
                "channel_id": msg.channel_id,
                "created_at": msg.created_at.isoformat() if msg.created_at else None,
            }
        }
        await manager.broadcast_to_channel(channel_id, payload)
    except Exception:
        # Best-effort broadcast
        pass

    return msg
