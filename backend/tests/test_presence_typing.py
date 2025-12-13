import json
import pytest
import anyio
from app.api import ws as ws_module

pytestmark = pytest.mark.integration


class FakeRedis:
    def __init__(self):
        self.instance_id = 'fake'
        self.kv = {}
        self.expires = {}
        self.published = []
        self.sets = {}

    def set(self, key, val):
        self.kv[key] = val

    def get(self, key):
        if key in self.expires and self.expires[key] < anyio.current_time():
            self.kv.pop(key, None)
            return None
        return self.kv.get(key)

    def expire(self, key, ttl):
        # store absolute expiry
        self.expires[key] = anyio.current_time() + ttl

    def publish(self, channel, payload):
        self.published.append((channel, payload))

    async def set_user_status(self, user_id, status):
        key = f'presence:user:{user_id}'
        payload = {"status": status, "last_seen": anyio.current_time()}
        self.set(key, json.dumps(payload))
        self.expire(key, 60)
        self.publish('presence', json.dumps({"type": "presence_update", "user_id": user_id, **payload, "origin": self.instance_id}))

    async def set_typing(self, channel_id, user_id):
        key = f'typing:channel:{channel_id}'
        self.sadd(key, user_id)
        self.expire(key, 5)
        self.publish(f'channel:{channel_id}', json.dumps({"type": "typing_update", "channel_id": channel_id, "user_id": user_id, "action": "start", "origin": self.instance_id}))

    async def clear_typing(self, channel_id, user_id):
        key = f'typing:channel:{channel_id}'
        self.srem(key, user_id)
        self.publish(f'channel:{channel_id}', json.dumps({"type": "typing_update", "channel_id": channel_id, "user_id": user_id, "action": "stop", "origin": self.instance_id}))

    def sadd(self, key, member):
        s = self.sets.setdefault(key, set())
        s.add(str(member))

    def srem(self, key, member):
        s = self.sets.get(key, set())
        s.discard(str(member))

    def smembers(self, key):
        return self.sets.get(key, set())

    def ping(self):
        return True


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


@pytest.mark.anyio
async def test_presence_set_on_connect(client, test_session):
    # Monkeypatch redis client
    fake = FakeRedis()
    ws_module.redis_client = fake

    # Create channel & register
    r1 = await client.post('/api/auth/register', json={'email': 'p1@example.com', 'password': 'Password123!', 'username': 'p1'})
    login = await client.post('/api/auth/login', json={'identifier': 'p1@example.com', 'password': 'Password123!'})
    token = login.json()['access_token']
    create = await client.post('/api/channels/', json={'name': 'presence', 'display_name': 'Presence'}, headers={'Authorization': f'Bearer {token}'})
    channel_id = create.json()['id']

    ws = FakeWS()
    # Connect using manager directly to avoid real websocket server
    await ws_module.manager.connect(ws, channel_id, 1, 'p1')
    # Ensure presence key was set and publish occurred
    assert any('presence' == ch or ch.startswith('presence') for ch, _ in fake.published)
    key = f'presence:user:1'
    assert key in fake.kv


@pytest.mark.anyio
async def test_typing_start_stop_fanout():
    fake = FakeRedis()
    ws_module.redis_client = fake
    # Start typing
    await ws_module.redis_client.set_typing(42, 1)
    # Ensure typing key exists and publish recorded
    key = 'typing:channel:42'
    assert '1' in fake.sets.get(key, set())
    assert any(ch == 'channel:42' for ch, _ in fake.published)
    # Stop typing
    await ws_module.redis_client.clear_typing(42, 1)
    assert '42' not in fake.sets.get(key, set())
    assert any(ch == 'channel:42' for ch, _ in fake.published)
