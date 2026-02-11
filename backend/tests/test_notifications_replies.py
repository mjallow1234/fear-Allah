import pytest
from app.core.security import create_access_token
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import User, Channel, ChannelMember, Message, DirectConversation, DirectConversationParticipant, Notification
from app.db.enums import NotificationType

pytestmark = pytest.mark.anyio


@pytest.mark.anyio
async def test_channel_reply_creates_notification(client, test_session: AsyncSession):
    # Create users and channel
    a = User(username='a_user', email='a@example.com', hashed_password='x')
    b = User(username='b_user', email='b@example.com', hashed_password='x')
    ch = Channel(name='notif-ch', display_name='Notif Ch', type='public')
    test_session.add_all([a, b, ch])
    await test_session.flush()

    # Create parent message by A
    parent = Message(content='parent', channel_id=ch.id, author_id=a.id)
    test_session.add(parent)
    await test_session.commit()

    # B posts a reply to parent
    token = create_access_token({'sub': str(b.id), 'username': b.username})
    resp = await client.post('/api/messages/', json={'content': 'reply', 'channel_id': ch.id, 'parent_id': parent.id}, headers={'Authorization': f'Bearer {token}'})
    assert resp.status_code == 201
    data = resp.json()
    reply_id = data['id']

    # Ensure notification exists for A
    q = select(Notification).where(Notification.user_id == a.id, Notification.type == NotificationType.channel_reply)
    res = await test_session.execute(q)
    notif = res.scalar_one_or_none()
    assert notif is not None
    assert notif.message_id == reply_id
    assert notif.sender_id == b.id
    assert notif.type == NotificationType.channel_reply
    assert notif.extra_data is not None
    import json
    meta = json.loads(notif.extra_data)
    assert int(meta.get('parent_id')) == parent.id
    assert int(meta.get('channel_id')) == ch.id


@pytest.mark.anyio
async def test_dm_reply_creates_notification(client, test_session: AsyncSession):
    # Create users and direct conversation
    a = User(username='a_dm', email='a_dm@example.com', hashed_password='x')
    b = User(username='b_dm', email='b_dm@example.com', hashed_password='x')
    test_session.add_all([a, b])
    await test_session.flush()

    conv = DirectConversation(created_by_user_id=a.id, participant_pair=f"{min(a.id,b.id)}:{max(a.id,b.id)}")
    test_session.add(conv)
    await test_session.flush()
    p1 = DirectConversationParticipant(direct_conversation_id=conv.id, user_id=a.id)
    p2 = DirectConversationParticipant(direct_conversation_id=conv.id, user_id=b.id)
    test_session.add_all([p1, p2])
    await test_session.flush()

    # Parent message by A
    parent = Message(content='dm parent', direct_conversation_id=conv.id, author_id=a.id)
    test_session.add(parent)
    await test_session.commit()

    # B replies
    token = create_access_token({'sub': str(b.id), 'username': b.username})
    resp = await client.post(f'/api/direct-conversations/{conv.id}/messages', json={'content': 'reply', 'parent_id': parent.id}, headers={'Authorization': f'Bearer {token}'})
    assert resp.status_code == 201
    data = resp.json()
    reply_id = data['id']

    # Check notification
    q = select(Notification).where(Notification.user_id == a.id, Notification.type == NotificationType.dm_reply)
    res = await test_session.execute(q)
    notif = res.scalar_one_or_none()
    assert notif is not None
    assert notif.message_id == reply_id
    assert notif.sender_id == b.id
    assert notif.type == NotificationType.dm_reply
    import json
    meta = json.loads(notif.extra_data)
    assert int(meta.get('parent_id')) == parent.id
    assert int(meta.get('direct_conversation_id')) == conv.id


@pytest.mark.anyio
async def test_no_notification_for_deleted_parent_channel_reply(client, test_session: AsyncSession):
    # Create users and channel
    a = User(username='a_del', email='a_del@example.com', hashed_password='x')
    b = User(username='b_del', email='b_del@example.com', hashed_password='x')
    ch = Channel(name='notif-ch-del', display_name='Notif Ch Del', type='public')
    test_session.add_all([a, b, ch])
    await test_session.flush()

    # Parent message by A (deleted)
    parent = Message(content='parent', channel_id=ch.id, author_id=a.id, is_deleted=True)
    test_session.add(parent)
    await test_session.commit()

    # B posts a reply to parent
    token = create_access_token({'sub': str(b.id), 'username': b.username})
    resp = await client.post('/api/messages/', json={'content': 'reply', 'channel_id': ch.id, 'parent_id': parent.id}, headers={'Authorization': f'Bearer {token}'})
    assert resp.status_code == 201

    # Ensure no channel_reply notification was created for A
    q = select(Notification).where(Notification.user_id == a.id, Notification.type == NotificationType.channel_reply)
    res = await test_session.execute(q)
    notif = res.scalar_one_or_none()
    assert notif is None
