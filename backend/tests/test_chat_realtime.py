import json
import anyio
import pytest
from starlette.testclient import TestClient

from app.main import app
from app.api import ws as ws_module


@pytest.mark.anyio
async def test_ws_message_roundtrip_and_persistence(client):
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

    # Create channel as u1
    create = await client.post('/api/channels', json={'name': 'realtime', 'display_name': 'Realtime'}, headers={'Authorization': f'Bearer {t1}'})
    assert create.status_code == 201
    channel_id = create.json()['id']

    # u2 joins
    join = await client.post(f'/api/channels/{channel_id}/join', headers={'Authorization': f'Bearer {t2}'})
    assert join.status_code in (200, 201)

    # Use TestClient to open websockets synchronously in a thread
    def ws_interaction():
        with TestClient(app) as tc:
            with tc.websocket_connect(f"/ws/chat/{channel_id}?token={t1}") as ws1, tc.websocket_connect(f"/ws/chat/{channel_id}?token={t2}") as ws2:
                # u1 sends a message
                ws1.send_json({"type": "message", "content": "hello everyone"})

                # u2 should receive message
                msg = ws2.receive_json(timeout=3)
                assert msg['type'] == 'message'
                assert msg['content'] == 'hello everyone'

    await anyio.to_thread.run_sync(ws_interaction)

    # Verify persistence via messages endpoint
    msgs = await client.get(f'/api/messages/channel/{channel_id}', headers={'Authorization': f'Bearer {t1}'})
    assert msgs.status_code == 200
    data = msgs.json()
    assert any(m['content'] == 'hello everyone' for m in data)


@pytest.mark.anyio
async def test_redis_publish_simulation_monkeypatch(client, monkeypatch):
    # Basic setup: register users and create/join channel
    r1 = await client.post('/api/auth/register', json={'email': 's1@example.com', 'password': 'Password123!', 'username': 's1'})
    assert r1.status_code == 201
    login1 = await client.post('/api/auth/login', json={'identifier': 's1@example.com', 'password': 'Password123!'})
    t1 = login1.json()['access_token']
    create = await client.post('/api/channels', json={'name': 'sim', 'display_name': 'Sim'}, headers={'Authorization': f'Bearer {t1}'})
    channel_id = create.json()['id']

    # Connect one websocket client
    def ws_run(received_list):
        with TestClient(app) as tc:
            with tc.websocket_connect(f"/ws/chat/{channel_id}?token={t1}") as ws1:
                # Wait for a simulated incoming pubsub message to be broadcast
                msg = ws1.receive_json(timeout=3)
                received_list.append(msg)

    received = []
    # Start the ws listener in a thread
    await anyio.to_thread.run_sync(ws_run, received)

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

    # Give time for thread to receive
    await anyio.sleep(0.5)
    assert any(m['content'] == 'from-other-pod' for m in received)
