import pytest
from httpx import AsyncClient


@pytest.mark.anyio
async def test_chat_roundtrip(client: AsyncClient):
    # Register two users
    r1 = await client.post('/api/auth/register', json={
<<<<<<< HEAD
        'email': 'chat_user1@example.com', 'password': 'Password123!', 'username': 'chat_user1'
    })
    assert r1.status_code == 201
    r2 = await client.post('/api/auth/register', json={
        'email': 'chat_user2@example.com', 'password': 'Password123!', 'username': 'chat_user2'
=======
        'email': 'user1@example.com', 'password': 'Password123!', 'username': 'user1'
    })
    assert r1.status_code == 201
    r2 = await client.post('/api/auth/register', json={
        'email': 'user2@example.com', 'password': 'Password123!', 'username': 'user2'
>>>>>>> ae666358 (Phase 8: Chat scaffolding (models shim, alembic migration, ws wrapper, tests, frontend stubs, docs))
    })
    assert r2.status_code == 201

    # Login to get tokens
<<<<<<< HEAD
    login1 = await client.post('/api/auth/login', json={'identifier': 'chat_user1@example.com', 'password': 'Password123!'})
    login2 = await client.post('/api/auth/login', json={'identifier': 'chat_user2@example.com', 'password': 'Password123!'})
=======
    login1 = await client.post('/api/auth/login', json={'email': 'user1@example.com', 'password': 'Password123!'})
    login2 = await client.post('/api/auth/login', json={'email': 'user2@example.com', 'password': 'Password123!'})
>>>>>>> ae666358 (Phase 8: Chat scaffolding (models shim, alembic migration, ws wrapper, tests, frontend stubs, docs))
    assert login1.status_code == 200
    assert login2.status_code == 200
    token1 = login1.json()['access_token']
    token2 = login2.json()['access_token']

    headers1 = {'Authorization': f'Bearer {token1}'}
    headers2 = {'Authorization': f'Bearer {token2}'}

    # Create channel as user1
<<<<<<< HEAD
    create_channel = await client.post('/api/channels/', json={'name': 'test-channel', 'display_name': 'Test Channel'}, headers=headers1)
=======
    create_channel = await client.post('/api/channels', json={'name': 'test-channel', 'display_name': 'Test Channel'}, headers=headers1)
>>>>>>> ae666358 (Phase 8: Chat scaffolding (models shim, alembic migration, ws wrapper, tests, frontend stubs, docs))
    assert create_channel.status_code == 201
    channel = create_channel.json()
    channel_id = channel['id']

    import pytest
    from httpx import AsyncClient


    @pytest.mark.anyio
    async def test_chat_roundtrip(client: AsyncClient):
        # Register two users
        r1 = await client.post('/api/auth/register', json={
            'email': 'user1@example.com', 'password': 'Password123!', 'username': 'user1'
        })
        assert r1.status_code == 201
        r2 = await client.post('/api/auth/register', json={
            'email': 'user2@example.com', 'password': 'Password123!', 'username': 'user2'
        })
        assert r2.status_code == 201

        # Login to get tokens (identifier supports username or email)
        login1 = await client.post('/api/auth/login', json={'identifier': 'user1@example.com', 'password': 'Password123!'})
        login2 = await client.post('/api/auth/login', json={'identifier': 'user2@example.com', 'password': 'Password123!'})
        assert login1.status_code == 200
        assert login2.status_code == 200
        token1 = login1.json()['access_token']
        token2 = login2.json()['access_token']

        headers1 = {'Authorization': f'Bearer {token1}'}
        headers2 = {'Authorization': f'Bearer {token2}'}

        # Create channel as user1
        create_channel = await client.post('/api/channels/', json={'name': 'test-channel', 'display_name': 'Test Channel'}, headers=headers1)
        assert create_channel.status_code == 201
        channel = create_channel.json()
        channel_id = channel['id']

        # user2 joins channel
        join_resp = await client.post(f'/api/channels/{channel_id}/join', headers=headers2)
        assert join_resp.status_code in (200, 201)

        # user1 creates a message
        msg1 = await client.post('/api/messages/', json={'content': 'Hello from user1', 'channel_id': channel_id}, headers=headers1)
        assert msg1.status_code == 201
        message1 = msg1.json()

        # user2 replies to message1
        msg2 = await client.post('/api/messages/', json={'content': 'Reply from user2', 'channel_id': channel_id, 'parent_id': message1['id']}, headers=headers2)
        assert msg2.status_code == 201

        # Get channel messages
        msgs = await client.get(f'/api/messages/channel/{channel_id}', headers=headers1)
        assert msgs.status_code == 200
        data = msgs.json()
        # Messages should include top-level message1
        assert any(m['content'] == 'Hello from user1' for m in data)
        # Check reply_count for message1 equals 1
        msg1_found = [m for m in data if m['content'] == 'Hello from user1'][0]
        assert msg1_found['reply_count'] == 1
