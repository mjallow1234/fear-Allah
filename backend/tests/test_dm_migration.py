import pytest
from datetime import datetime, timedelta
from app.core.security import create_access_token
from app.db.models import User, Channel, ChannelMember, Message, DirectConversation, DirectConversationParticipant
from app.db.enums import ChannelType

pytestmark = pytest.mark.integration


@pytest.mark.anyio
async def test_legacy_dm_discovery_and_migration_and_cutover(client, test_session):
    # Create two users
    a = User(username='m1', email='m1@example.com', hashed_password='x')
    b = User(username='m2', email='m2@example.com', hashed_password='x')
    test_session.add_all([a, b])
    await test_session.commit()

    # Cache values to avoid ORM lazy-loads after migration operations
    a_id = a.id
    a_username = a.username
    token_a = create_access_token({'sub': str(a_id), 'username': a_username})

    # Create legacy DM channel
    ch = Channel(name='dm-1-2', display_name='dm 1-2', type=ChannelType.direct.value, created_at=datetime.utcnow() - timedelta(days=1))
    test_session.add(ch)
    await test_session.flush()

    # Add two members with specific created_at (joined_at preservation)
    m1 = ChannelMember(user_id=a.id, channel_id=ch.id, created_at=datetime.utcnow() - timedelta(hours=1))
    m2 = ChannelMember(user_id=b.id, channel_id=ch.id, created_at=datetime.utcnow() - timedelta(hours=1))
    test_session.add_all([m1, m2])

    # Add messages in channel
    msgs = [Message(content=f'msg{i}', channel_id=ch.id, author_id=a.id) for i in range(3)]
    test_session.add_all(msgs)
    await test_session.commit()

    # Discover
    from scripts.migrate_legacy_dms import discover_legacy_dms, migrate_channel, cutover_channel
    res = await discover_legacy_dms()
    assert any(r['channel_id'] == ch.id for r in res)

    # Migrate (use independent DB session inside migration func for isolation)
    mapping = await migrate_channel(ch.id)
    assert mapping is not None
    # Ensure mapping exists and message count matches
    assert mapping.message_count == 3

    # Cache ids to avoid expired attribute lazy loads
    ch_id = ch.id

    # The DirectConversation should exist; fetch using a fresh session to avoid session identity issues
    from app.db.database import async_session
    from sqlalchemy import select
    async with async_session() as db:
        r = await db.execute(select(DirectConversation).where(DirectConversation.id == mapping.direct_conversation_id))
        conv = r.scalar_one_or_none()
    assert conv is not None

    # Participants preserved (checked via DB query using fresh session)
    async with async_session() as db:
        p_q = select(DirectConversationParticipant).where(DirectConversationParticipant.direct_conversation_id == conv.id)
        pr = await db.execute(p_q)
        parts = pr.scalars().all()
    assert len(parts) == 2

    # Run cutover step (migration operation uses its own session)
    mapping2 = await cutover_channel(ch.id)
    assert mapping2 is not None
    assert mapping2.migrated is True

    # Messages should now have direct_conversation_id set and channel_id null; verify using a fresh session
    from sqlalchemy import select
    from app.db.database import async_session
    async with async_session() as db:
        rows = (await db.execute(select(Message.id, Message.channel_id, Message.direct_conversation_id).where(Message.direct_conversation_id == conv.id))).all()
    assert len(rows) == 3
    for _id, channel_id, direct_id in rows:
        assert channel_id is None
        assert direct_id == conv.id

    # Legacy DM channels should no longer appear in DM lists (call function directly with fresh session)
    from app.api.channels import list_dm_channels
    async with async_session() as db:
        dm_list = await list_dm_channels(current_user={"user_id": a_id}, db=db)
    assert all(c['id'] != ch_id for c in dm_list)

    # Posting to legacy channel must be rejected (call create_message directly with fresh session)
    from app.api.messages import MessageCreateRequest, create_message
    req = MessageCreateRequest(content='hi', channel_id=ch_id)
    from fastapi import HTTPException
    async with async_session() as db:
        try:
            await create_message(req, None, current_user={"user_id": a_id}, db=db)
        except HTTPException as e:
            assert e.status_code == 403
        else:
            pytest.fail('Expected posting to legacy channel to be rejected')

    # Final assertions: mapping marked migrated and counts preserved
    assert mapping2.migrated is True
    assert mapping2.message_count == 3

