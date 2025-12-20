import json
import anyio
import pytest
from starlette.testclient import TestClient

pytestmark = pytest.mark.integration

from app.main import app
from app.api import ws as ws_module


@pytest.mark.anyio
async def test_ws_message_roundtrip_and_persistence(client, test_session):
    # Register users
    r1 = await client.post('/api/auth/register', json={'email': 'u1@example.com', 'password': 'Password123!', 'username': 'u1'})
    assert r1.status_code == 201
    r2 = await client.post('/api/auth/register', json={'email': 'u2@example.com', 'password': 'Password123!', 'username': 'u2'})
    assert r2.status_code == 201

    # Login
    login1 = await client.post('/api/auth/login', json={'identifier': 'u1@example.com', 'password': 'Password123!'})
    login2 = await client.post('/api/auth/login', json={'identifier': 'u2@example.com', 'password': 'Password123!'})
    assert login1.status_code == 200
    assert login2.status_code == 200
    t1 = login1.json()['access_token']
    t2 = login2.json()['access_token']
    u1_id = login1.json()['user']['id']
    u2_id = login2.json()['user']['id']

    # Make u1 a system admin so they can create channels, then create channel as u1
    from app.db.models import User
    res = await test_session.execute(__import__('sqlalchemy').select(User).where(User.username == 'u1'))
    user = res.scalar_one()
    user.is_system_admin = True
    test_session.add(user)
    await test_session.commit()

    create = await client.post('/api/channels/', json={'name': 'realtime', 'display_name': 'Realtime'}, headers={'Authorization': f'Bearer {t1}'})
    assert create.status_code == 201
    channel_id = create.json()['id']

    # u2 joins
    join = await client.post(f'/api/channels/{channel_id}/join', headers={'Authorization': f'Bearer {t2}'})
    assert join.status_code in (200, 201)

    # Connect using manager directly with fake websockets to avoid TestClient concurrency issues
    class FakeWS:
        def __init__(self):
            self.received = []
            self.closed = False
        async def accept(self):
            return
        async def send_json(self, obj):
            self.received.append(obj)
        async def close(self, code=1000):
            self.closed = True

    # Monkeypatch redis client to avoid external Redis usage
    class FakeRedisLocal:
        def __init__(self):
            self.instance_id = 'fake'
        async def set_user_status(self, user_id, status):
            return

    ws_module.redis_client = FakeRedisLocal()

    ws1 = FakeWS()
    ws2 = FakeWS()
    await ws_module.manager.connect(ws1, channel_id, u1_id, 'u1')
    await ws_module.manager.connect(ws2, channel_id, u2_id, 'u2')

    # Emulate u1 sending a message by saving to DB and broadcasting
    msg = await ws_module.save_message(test_session, channel_id, u1_id, 'hello everyone')
    await ws_module.manager.broadcast_to_channel(channel_id, {
        "type": "message",
        "id": msg.id,
        "content": msg.content,
        "user_id": u1_id,
        "username": 'u1',
        "channel_id": channel_id,
        "timestamp": msg.created_at.isoformat(),
        "reactions": [],
    })
    assert any(m['content'] == 'hello everyone' for m in ws2.received)

    # Verify persistence via messages endpoint
    msgs = await client.get(f'/api/messages/channel/{channel_id}', headers={'Authorization': f'Bearer {t1}'})
    assert msgs.status_code == 200
    data = msgs.json()
    assert any(m['content'] == 'hello everyone' for m in data)


@pytest.mark.anyio
async def test_redis_publish_simulation_monkeypatch(client, monkeypatch, test_session):
    # Basic setup: register users and create/join channel
    r1 = await client.post('/api/auth/register', json={'email': 's1@example.com', 'password': 'Password123!', 'username': 's1'})
    assert r1.status_code == 201
    login1 = await client.post('/api/auth/login', json={'identifier': 's1@example.com', 'password': 'Password123!'})
    t1 = login1.json()['access_token']
    # Make s1 a system admin so they can create channels
    from app.db.models import User
    res = await test_session.execute(__import__('sqlalchemy').select(User).where(User.username == 's1'))
    user = res.scalar_one()
    user.is_system_admin = True
    test_session.add(user)
    await test_session.commit()

    create = await client.post('/api/channels/', json={'name': 'sim', 'display_name': 'Sim'}, headers={'Authorization': f'Bearer {t1}'})
    channel_id = create.json()['id']

    # Create a fake websocket client and connect via manager to avoid TestClient concurrency issues
    class FakeWS:
        def __init__(self):
            self.received = []
            self.closed = False
        async def accept(self):
            return
        async def send_json(self, obj):
            self.received.append(obj)
        async def close(self, code=1000):
            self.closed = True

    # Monkeypatch redis client to avoid external Redis calls during test
    class FakeRedisLocal:
        def __init__(self):
            self.instance_id = 'fake'
        async def set_user_status(self, user_id, status):
            return

    ws_module.redis_client = FakeRedisLocal()

    fake_ws = FakeWS()
    # Connect the fake websocket using manager directly
    await ws_module.manager.connect(fake_ws, channel_id, 1, 's1')

    # Simulate redis publish by calling manager.broadcast_to_channel directly (as if from another pod)
    payload = {
        "type": "message",
        "id": 9999,
        "content": "from-other-pod",
        "user_id": 1,
        "username": "system",
        "channel_id": channel_id,
        "timestamp": "2025-01-01T00:00:00Z",
    }
    # Use manager to broadcast as simulation of pubsub delivery
    await ws_module.manager.broadcast_to_channel(channel_id, payload)

    # Give time for in-process manager to deliver
    await anyio.sleep(0.1)
    assert any(m['content'] == 'from-other-pod' for m in fake_ws.received)
