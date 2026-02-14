import pytest
from httpx import AsyncClient
from datetime import datetime, timezone

pytestmark = pytest.mark.integration


@pytest.mark.anyio
async def test_channels_list_includes_unread_count(client: AsyncClient, test_session):
    # Create two users and tokens
    r1 = await client.post('/api/auth/register', json={'email': 'e@example.com', 'password': 'Password123!', 'username': 'e'})
    r2 = await client.post('/api/auth/register', json={'email': 'f@example.com', 'password': 'Password123!', 'username': 'f'})
    assert r1.status_code == 201 and r2.status_code == 201

    login1 = await client.post('/api/auth/login', json={'identifier': 'e@example.com', 'password': 'Password123!'})
    login2 = await client.post('/api/auth/login', json={'identifier': 'f@example.com', 'password': 'Password123!'})
    t1 = login1.json()['access_token']
    t2 = login2.json()['access_token']

    # Make e an admin so they can create a channel
    from app.db.models import User
    res = await test_session.execute(__import__('sqlalchemy').select(User).where(User.username == 'e'))
    u = res.scalar_one()
    u.is_system_admin = True
    test_session.add(u)
    await test_session.commit()

    # Create channel and have user f join
    create = await client.post('/api/channels/', json={'name': 'unread-list', 'display_name': 'Unread List'}, headers={'Authorization': f'Bearer {t1}'})
    channel_id = create.json()['id']
    await client.post(f'/api/channels/{channel_id}/join', headers={'Authorization': f'Bearer {t2}'})

    # Post two messages as e
    await client.post('/api/messages/', json={'content': 'one', 'channel_id': channel_id}, headers={'Authorization': f'Bearer {t1}'})
    await client.post('/api/messages/', json={'content': 'two', 'channel_id': channel_id}, headers={'Authorization': f'Bearer {t1}'})

    # Fetch channels as f and ensure unread_count reflects the two messages
    resp = await client.get('/api/channels/', headers={'Authorization': f'Bearer {t2}'})
    assert resp.status_code == 200
    data = resp.json()
    ch = next((c for c in data if c['id'] == channel_id), None)
    assert ch is not None
    assert ch.get('unread_count') == 2

    # Mark channel as read and ensure unread_count becomes zero
    await client.post(f'/api/channels/{channel_id}/read', headers={'Authorization': f'Bearer {t2}'})
    resp2 = await client.get('/api/channels/', headers={'Authorization': f'Bearer {t2}'})
    ch2 = next((c for c in resp2.json() if c['id'] == channel_id), None)
    assert ch2 and ch2.get('unread_count') == 0


@pytest.mark.anyio
async def test_mark_channel_read_with_message_id_updates_last_read_at_and_emits_unread_update(client: AsyncClient, test_session, monkeypatch):
    # Register two users, create channel, join
    r1 = await client.post('/api/auth/register', json={'email': 'g@example.com', 'password': 'Password123!', 'username': 'g'})
    r2 = await client.post('/api/auth/register', json={'email': 'h@example.com', 'password': 'Password123!', 'username': 'h'})
    assert r1.status_code == 201 and r2.status_code == 201

    login1 = await client.post('/api/auth/login', json={'identifier': 'g@example.com', 'password': 'Password123!'})
    login2 = await client.post('/api/auth/login', json={'identifier': 'h@example.com', 'password': 'Password123!'})
    t1 = login1.json()['access_token']
    t2 = login2.json()['access_token']

    # Make g an admin and create a channel
    from app.db.models import User
    res = await test_session.execute(__import__('sqlalchemy').select(User).where(User.username == 'g'))
    u = res.scalar_one()
    u.is_system_admin = True
    test_session.add(u)
    await test_session.commit()

    create = await client.post('/api/channels/', json={'name': 'read-msgid', 'display_name': 'Read By MsgID'}, headers={'Authorization': f'Bearer {t1}'})
    channel_id = create.json()['id']
    await client.post(f'/api/channels/{channel_id}/join', headers={'Authorization': f'Bearer {t2}'})

    # Post a message and capture its id
    msg = await client.post('/api/messages/', json={'content': 'hello', 'channel_id': channel_id}, headers={'Authorization': f'Bearer {t1}'})
    msg_id = msg.json()['id']

    # Capture unread_update sends
    from app.api import ws as ws_module
    captured = []

    async def fake_send_to_user(user_id, message):
        captured.append((user_id, message))

    monkeypatch.setattr(ws_module.manager, 'send_to_user', fake_send_to_user)

    # h marks channel read by message id
    resp = await client.post(f'/api/channels/{channel_id}/read', json={'last_read_message_id': msg_id}, headers={'Authorization': f'Bearer {t2}'})
    assert resp.status_code == 200

    # Ensure ChannelMember.last_read_at was updated (should be set to now and thus >= message.created_at)
    q = await test_session.execute(__import__('sqlalchemy').select(__import__('app').db.models.ChannelMember).where(__import__('app').db.models.ChannelMember.channel_id == channel_id, __import__('app').db.models.ChannelMember.user_id == 2))
    membership = q.scalar_one()
    assert membership.last_read_at is not None
    msg_created_at = datetime.fromisoformat(msg.json()['created_at'])
    assert membership.last_read_at >= msg_created_at

    # Ensure unread_update emitted to the user with zero
    assert any(u == 2 and m.get('type') == 'unread_update' and m.get('unread_count') == 0 for u, m in captured)


@pytest.mark.anyio
async def test_unread_counts_replies(client: AsyncClient, test_session):
    # Create users and channel
    r1 = await client.post('/api/auth/register', json={'email': 'r1@example.com', 'password': 'Password123!', 'username': 'r1'})
    r2 = await client.post('/api/auth/register', json={'email': 'r2@example.com', 'password': 'Password123!', 'username': 'r2'})
    login1 = await client.post('/api/auth/login', json={'identifier': 'r1@example.com', 'password': 'Password123!'})
    login2 = await client.post('/api/auth/login', json={'identifier': 'r2@example.com', 'password': 'Password123!'})
    t1 = login1.json()['access_token']
    t2 = login2.json()['access_token']

    from app.db.models import User
    res = await test_session.execute(__import__('sqlalchemy').select(User).where(User.username == 'r1'))
    u = res.scalar_one()
    u.is_system_admin = True
    test_session.add(u)
    await test_session.commit()

    create = await client.post('/api/channels/', json={'name': 'replies-unread', 'display_name': 'Replies Unread'}, headers={'Authorization': f'Bearer {t1}'})
    channel_id = create.json()['id']
    await client.post(f'/api/channels/{channel_id}/join', headers={'Authorization': f'Bearer {t2}'})

    # Post a top-level message then a reply
    top = await client.post('/api/messages/', json={'content': 'top', 'channel_id': channel_id}, headers={'Authorization': f'Bearer {t1}'})
    top_id = top.json()['id']
    await client.post(f'/api/messages/{top_id}/reply', json={'content': 'reply1'}, headers={'Authorization': f'Bearer {t1}'})

    # Fetch channels as r2 and ensure unread_count==2 (top + reply)
    resp = await client.get('/api/channels/', headers={'Authorization': f'Bearer {t2}'})
    data = resp.json()
    ch = next((c for c in data if c['id'] == channel_id), None)
    assert ch is not None
    assert ch.get('unread_count') == 2


@pytest.mark.anyio
async def test_channels_list_sorted_by_last_activity(client: AsyncClient, test_session):
    # Create admin + member
    r1 = await client.post('/api/auth/register', json={'email': 's1@example.com', 'password': 'Password123!', 'username': 's1'})
    r2 = await client.post('/api/auth/register', json={'email': 's2@example.com', 'password': 'Password123!', 'username': 's2'})
    login1 = await client.post('/api/auth/login', json={'identifier': 's1@example.com', 'password': 'Password123!'})
    login2 = await client.post('/api/auth/login', json={'identifier': 's2@example.com', 'password': 'Password123!'})
    t1 = login1.json()['access_token']
    t2 = login2.json()['access_token']

    from app.db.models import User
    res = await test_session.execute(__import__('sqlalchemy').select(User).where(User.username == 's1'))
    u = res.scalar_one()
    u.is_system_admin = True
    test_session.add(u)
    await test_session.commit()

    # Create two channels and have s2 join both
    c1 = await client.post('/api/channels/', json={'name': 'ch-old', 'display_name': 'Old'}, headers={'Authorization': f'Bearer {t1}'})
    c2 = await client.post('/api/channels/', json={'name': 'ch-new', 'display_name': 'New'}, headers={'Authorization': f'Bearer {t1}'})
    c1_id = c1.json()['id']
    c2_id = c2.json()['id']
    await client.post(f'/api/channels/{c1_id}/join', headers={'Authorization': f'Bearer {t2}'})
    await client.post(f'/api/channels/{c2_id}/join', headers={'Authorization': f'Bearer {t2}'})

    # Post in c1 (older) then c2 (newer)
    await client.post('/api/messages/', json={'content': 'old-msg', 'channel_id': c1_id}, headers={'Authorization': f'Bearer {t1}'})
    await client.post('/api/messages/', json={'content': 'new-msg', 'channel_id': c2_id}, headers={'Authorization': f'Bearer {t1}'})

    # Fetch channels as s2; server must return channels sorted by last_activity_at
    resp = await client.get('/api/channels/', headers={'Authorization': f'Bearer {t2}'})
    assert resp.status_code == 200
    data = resp.json()

    # Ensure overall list is sorted by last_activity_at (newest first)
    def _parse(dt):
            return datetime.fromisoformat(dt) if dt else datetime.min.replace(tzinfo=timezone.utc)
    lasts = [_parse(c.get('last_activity_at')) for c in data]
    assert lasts == sorted(lasts, reverse=True)

    # Also ensure the specific channels reflect expected ordering (c2 newer than c1)
    c1_obj = next(c for c in data if c['id'] == c1_id)
    c2_obj = next(c for c in data if c['id'] == c2_id)
    assert _parse(c2_obj.get('last_activity_at')) >= _parse(c1_obj.get('last_activity_at'))
