import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.integration


@pytest.mark.anyio
async def test_unread_increments_for_other_user(client: AsyncClient, test_session, monkeypatch):
    # Register two users
    r1 = await client.post('/api/auth/register', json={'email': 'a@example.com', 'password': 'Password123!', 'username': 'a'})
    r2 = await client.post('/api/auth/register', json={'email': 'b@example.com', 'password': 'Password123!', 'username': 'b'})
    assert r1.status_code == 201
    assert r2.status_code == 201

    # Login
    login1 = await client.post('/api/auth/login', json={'identifier': 'a@example.com', 'password': 'Password123!'})
    login2 = await client.post('/api/auth/login', json={'identifier': 'b@example.com', 'password': 'Password123!'})
    t1 = login1.json()['access_token']
    t2 = login2.json()['access_token']

    # Make user a@example.com a system admin so they can create channels
    from app.db.models import User
    res = await test_session.execute(__import__('sqlalchemy').select(User).where(User.username == 'a'))
    user = res.scalar_one()
    user.is_system_admin = True
    test_session.add(user)
    await test_session.commit()

    # Create channel as user a
    create = await client.post('/api/channels/', json={'name': 'unread-test', 'display_name': 'Unread Test'}, headers={'Authorization': f'Bearer {t1}'})
    assert create.status_code == 201
    channel_id = create.json()['id']

    # user b joins
    join = await client.post(f'/api/channels/{channel_id}/join', headers={'Authorization': f'Bearer {t2}'})
    assert join.status_code in (200, 201)

    # Monkeypatch manager.send_to_user to capture calls
    from app.api import ws as ws_module
    captured = []

    async def fake_send_to_user(user_id, message):
        captured.append((user_id, message))

    monkeypatch.setattr(ws_module.manager, 'send_to_user', fake_send_to_user)

    # user a sends a message
    resp = await client.post('/api/messages/', json={'content': 'Hello', 'channel_id': channel_id}, headers={'Authorization': f'Bearer {t1}'})
    assert resp.status_code == 201

    # Ensure send_to_user was called for user b with unread_update
    assert any(u == 2 and m.get('type') == 'unread_update' for u, m in captured)
    # Ensure sender did NOT receive unread_update
    assert not any(u == 1 and m.get('type') == 'unread_update' for u, m in captured)


@pytest.mark.anyio
async def test_mark_read_emits_zero_unread(client: AsyncClient, test_session, monkeypatch):
    # Register two users
    r1 = await client.post('/api/auth/register', json={'email': 'c@example.com', 'password': 'Password123!', 'username': 'c'})
    r2 = await client.post('/api/auth/register', json={'email': 'd@example.com', 'password': 'Password123!', 'username': 'd'})
    assert r1.status_code == 201
    assert r2.status_code == 201

    # Login
    login1 = await client.post('/api/auth/login', json={'identifier': 'c@example.com', 'password': 'Password123!'})
    login2 = await client.post('/api/auth/login', json={'identifier': 'd@example.com', 'password': 'Password123!'})
    t1 = login1.json()['access_token']
    t2 = login2.json()['access_token']

    # Make user c a system admin so they can create channels
    from app.db.models import User
    res = await test_session.execute(__import__('sqlalchemy').select(User).where(User.username == 'c'))
    user = res.scalar_one()
    user.is_system_admin = True
    test_session.add(user)
    await test_session.commit()

    # Create channel and have d join
    create = await client.post('/api/channels/', json={'name': 'unread-test-2', 'display_name': 'Unread Test 2'}, headers={'Authorization': f'Bearer {t1}'})
    channel_id = create.json()['id']
    join = await client.post(f'/api/channels/{channel_id}/join', headers={'Authorization': f'Bearer {t2}'})

    # c sends a message to make d have unread > 0
    await client.post('/api/messages/', json={'content': 'Hey d', 'channel_id': channel_id}, headers={'Authorization': f'Bearer {t1}'})

    # Monkeypatch manager.send_to_user to capture mark-read emission
    from app.api import ws as ws_module
    captured = []

    async def fake_send_to_user(user_id, message):
        captured.append((user_id, message))

    monkeypatch.setattr(ws_module.manager, 'send_to_user', fake_send_to_user)

    # d marks channel as read
    resp = await client.post(f'/api/channels/{channel_id}/read', headers={'Authorization': f'Bearer {t2}'})
    assert resp.status_code == 200

    # Ensure we emitted unread_update with zero to d
    assert any(u == 2 and m.get('type') == 'unread_update' and m.get('unread_count') == 0 for u, m in captured)