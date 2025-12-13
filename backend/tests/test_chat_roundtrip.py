import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.integration


@pytest.mark.anyio
async def test_chat_roundtrip(client: AsyncClient):
    # Register users
    r1 = await client.post('/api/auth/register', json={'email': 'user1@example.com', 'password': 'Password123!', 'username': 'user1'})
    assert r1.status_code == 201
    r2 = await client.post('/api/auth/register', json={'email': 'user2@example.com', 'password': 'Password123!', 'username': 'user2'})
    assert r2.status_code == 201

    # Login
    login1 = await client.post('/api/auth/login', json={'identifier': 'user1@example.com', 'password': 'Password123!'})
    login2 = await client.post('/api/auth/login', json={'identifier': 'user2@example.com', 'password': 'Password123!'})
    assert login1.status_code == 200
    assert login2.status_code == 200
    token1 = login1.json()['access_token']
    token2 = login2.json()['access_token']

    headers1 = {'Authorization': f'Bearer {token1}'}
    headers2 = {'Authorization': f'Bearer {token2}'}

    # Create channel
    create_channel = await client.post('/api/channels/', json={'name': 'test-channel', 'display_name': 'Test Channel'}, headers=headers1)
    assert create_channel.status_code == 201
    channel_id = create_channel.json()['id']

    # user2 joins
    join_resp = await client.post(f'/api/channels/{channel_id}/join', headers=headers2)
    assert join_resp.status_code in (200, 201)

    # user1 posts
    msg1 = await client.post('/api/messages/', json={'content': 'Hello', 'channel_id': channel_id}, headers=headers1)
    assert msg1.status_code == 201
    message1 = msg1.json()

    # user2 replies
    msg2 = await client.post('/api/messages/', json={'content': 'Reply', 'channel_id': channel_id, 'parent_id': message1['id']}, headers=headers2)
    assert msg2.status_code == 201

    # verify
    msgs = await client.get(f'/api/messages/channel/{channel_id}', headers=headers1)
    assert msgs.status_code == 200
    data = msgs.json()
    assert any(m['content'] == 'Hello' for m in data)
import pytest
from httpx import AsyncClient


@pytest.mark.anyio
async def test_chat_roundtrip(client: AsyncClient):
    # Register two users
    r1 = await client.post('/api/auth/register', json={'email': 'user1@example.com', 'password': 'Password123!', 'username': 'user1'})
    assert r1.status_code == 201
    r2 = await client.post('/api/auth/register', json={'email': 'user2@example.com', 'password': 'Password123!', 'username': 'user2'})
    assert r2.status_code == 201

    # Login to get tokens
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

    # user1 posts a message
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
    assert any(m['content'] == 'Hello from user1' for m in data)
    msg1_found = [m for m in data if m['content'] == 'Hello from user1'][0]
    assert msg1_found.get('reply_count', 0) == 1
import pytest
from httpx import AsyncClient


@pytest.mark.anyio
async def test_chat_roundtrip(client: AsyncClient):
    # Register two users
    r1 = await client.post('/api/auth/register', json={'email': 'user1@example.com', 'password': 'Password123!', 'username': 'user1'})
    assert r1.status_code == 201
    r2 = await client.post('/api/auth/register', json={'email': 'user2@example.com', 'password': 'Password123!', 'username': 'user2'})
    assert r2.status_code == 201

    # Login to get tokens
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

    # user1 posts a message
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
    assert any(m['content'] == 'Hello from user1' for m in data)
    # Check reply_count for message1 equals 1
    msg1_found = [m for m in data if m['content'] == 'Hello from user1'][0]
    assert msg1_found.get('reply_count', 0) == 1
import pytest
from httpx import AsyncClient


@pytest.mark.anyio
async def test_chat_roundtrip(client: AsyncClient):
    # Register two users
    r1 = await client.post('/api/auth/register', json={'email': 'user1@example.com', 'password': 'Password123!', 'username': 'user1'})
    assert r1.status_code == 201
    r2 = await client.post('/api/auth/register', json={'email': 'user2@example.com', 'password': 'Password123!', 'username': 'user2'})
    assert r2.status_code == 201
    assert r2.status_code == 201

    # Login to get tokens
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
