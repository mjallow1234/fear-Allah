import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timedelta

from app.core.security import create_access_token as create_access_token_fn

pytestmark = pytest.mark.integration


@pytest.mark.anyio
async def test_socket_reject_must_change_password():
    """Socket authentication must reject users with must_change_password == True"""
    from jose import jwt
    from app.core.config import settings
    from app.realtime.auth import authenticate_socket

    def create_test_token(user_id: int):
        expire = datetime.utcnow() + timedelta(hours=1)
        payload = {"sub": str(user_id), "exp": expire}
        return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)

    mock_user = MagicMock()
    mock_user.id = 123
    mock_user.username = "pwuser"
    mock_user.display_name = "PW"
    mock_user.team_id = None
    mock_user.role = "member"
    mock_user.is_active = True
    mock_user.must_change_password = True

    token = create_test_token(user_id=123)

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_user

    mock_db = AsyncMock()
    mock_db.execute = AsyncMock(return_value=mock_result)

    mock_session_cm = AsyncMock()
    mock_session_cm.__aenter__.return_value = mock_db
    mock_session_cm.__aexit__.return_value = None

    with patch("app.realtime.auth.async_session", return_value=mock_session_cm):
        is_auth, user_data = await authenticate_socket(auth={"token": token}, environ={})

    assert is_auth is False
    assert user_data is None


@pytest.mark.anyio
async def test_must_change_password_blocks_rest(client, test_session):
    from app.db.models import User, Channel, Message
    from app.core.security import create_access_token

    now = datetime.utcnow()
    author = User(username='author', email='author@example.com', hashed_password='x')
    user = User(username='locked', email='locked@example.com', hashed_password='x', must_change_password=True, created_at=now - timedelta(days=1))
    channel = Channel(name='public1', display_name='Public1', type='public')
    test_session.add_all([author, user, channel])
    await test_session.flush()

    msg = Message(content='hello', channel_id=channel.id, author_id=author.id, created_at=now)
    test_session.add(msg)
    await test_session.commit()

    token = create_access_token({'sub': str(user.id), 'username': user.username})

    # Fetch messages should be blocked
    resp = await client.get(f'/api/channels/{channel.id}/messages', headers={'Authorization': f'Bearer {token}'})
    assert resp.status_code == 403

    # Posting messages should also be blocked
    resp2 = await client.post('/api/messages/', json={'content': 'hi', 'channel_id': channel.id}, headers={'Authorization': f'Bearer {token}'})
    assert resp2.status_code == 403


@pytest.mark.anyio
async def test_public_channel_user_cannot_see_old_messages(client, test_session):
    from app.db.models import User, Channel, Message
    from app.core.security import create_access_token

    now = datetime.utcnow()
    author = User(username='a', email='a@example.com', hashed_password='x')
    new_user = User(username='new', email='new@example.com', hashed_password='x', created_at=now)
    channel = Channel(name='pub', display_name='Pub', type='public')
    test_session.add_all([author, new_user, channel])
    await test_session.flush()

    old_msg = Message(content='old', channel_id=channel.id, author_id=author.id, created_at=now - timedelta(days=10))
    new_msg = Message(content='new', channel_id=channel.id, author_id=author.id, created_at=now + timedelta(seconds=1))
    test_session.add_all([old_msg, new_msg])
    await test_session.commit()

    token = create_access_token({'sub': str(new_user.id), 'username': new_user.username})
    # Check v3.4 channel messages endpoint
    resp = await client.get(f'/api/channels/{channel.id}/messages', headers={'Authorization': f'Bearer {token}'})
    assert resp.status_code == 200
    data = resp.json()
    messages = [m['content'] for m in data['messages']]
    assert 'old' not in messages
    assert 'new' in messages

    # Also validate the legacy messages endpoint
    resp2 = await client.get(f'/api/messages/channel/{channel.id}', headers={'Authorization': f'Bearer {token}'})
    assert resp2.status_code == 200
    data2 = resp2.json()
    # Legacy endpoint returns a list; newer v3.4 returns { messages: [...] }
    if isinstance(data2, list):
        msgs2 = [m['content'] for m in data2]
    else:
        msgs2 = [m['content'] for m in data2.get('messages', [])]
    assert 'old' not in msgs2
    assert 'new' in msgs2


@pytest.mark.anyio
async def test_socket_join_private_channel_rejected(monkeypatch):
    from app.realtime.socket import join_channel, authenticated_users
    from unittest.mock import AsyncMock
    sid = 'test-sid'
    authenticated_users[sid] = {"user_id": 10, "username": "u10"}

    # Mock DB results: channel exists and is private; membership missing
    mock_channel = MagicMock()
    mock_channel.id = 99
    mock_channel.type = 'private'
    mock_res_channel = MagicMock(); mock_res_channel.scalar_one_or_none.return_value = mock_channel

    mock_res_user = MagicMock(); mock_res_user.scalar_one_or_none.return_value = None
    mock_res_member = MagicMock(); mock_res_member.scalar_one_or_none.return_value = None

    mock_db = AsyncMock()
    # channel query, user query, membership query
    mock_db.execute = AsyncMock(side_effect=[mock_res_channel, mock_res_user, mock_res_member])
    mock_session_cm = AsyncMock()
    mock_session_cm.__aenter__.return_value = mock_db
    mock_session_cm.__aexit__.return_value = None

    with patch("app.db.database.async_session", return_value=mock_session_cm):
        # Patch sio.emit and enter_room
        emitted = {}
        async def fake_emit(event, payload=None, room=None, **kwargs):
            emitted['event'] = event
            emitted['payload'] = payload
            emitted['room'] = room
        monkeypatch.setattr('app.realtime.socket.sio.emit', AsyncMock(side_effect=fake_emit))
        monkeypatch.setattr('app.realtime.socket.sio.enter_room', AsyncMock())

        await join_channel(sid, {"channel_id": 99})

        assert emitted['event'] == 'error'
        assert emitted['payload'] == {"message": "You are not a member of this channel. Contact admin if that is not the case."}
        assert emitted['room'] == sid

    authenticated_users.pop(sid, None)


@pytest.mark.anyio
async def test_socket_join_private_channel_allowed_when_member(monkeypatch):
    from app.realtime.socket import join_channel, authenticated_users
    from unittest.mock import AsyncMock
    sid = 'test-sid-allow'
    authenticated_users[sid] = {"user_id": 11, "username": "u11"}
    # Simulate connect setup (rooms map)
    from app.realtime.socket import user_rooms
    user_rooms[sid] = set()

    mock_channel = MagicMock()
    mock_channel.id = 100
    mock_channel.type = 'private'
    mock_res_channel = MagicMock(); mock_res_channel.scalar_one_or_none.return_value = mock_channel

    mock_user = MagicMock(); mock_user.id = 11; mock_user.must_change_password = False
    mock_res_user = MagicMock(); mock_res_user.scalar_one_or_none.return_value = mock_user

    mock_member = MagicMock(); mock_member.scalar_one_or_none.return_value = MagicMock()

    mock_db = AsyncMock()
    mock_db.execute = AsyncMock(side_effect=[mock_res_channel, mock_res_user, mock_member])
    mock_session_cm = AsyncMock()
    mock_session_cm.__aenter__.return_value = mock_db
    mock_session_cm.__aexit__.return_value = None

    with patch("app.db.database.async_session", return_value=mock_session_cm):
        # Patch sio.enter_room and emit
        enter_called = {}
        async def fake_enter_room(sid_arg, room_name):
            enter_called['sid'] = sid_arg
            enter_called['room'] = room_name
        emitted = {}
        async def fake_emit(event, payload=None, room=None, **kwargs):
            emitted['event'] = event
            emitted['payload'] = payload
            emitted['room'] = room
        monkeypatch.setattr('app.realtime.socket.sio.enter_room', AsyncMock(side_effect=fake_enter_room))
        monkeypatch.setattr('app.realtime.socket.sio.emit', AsyncMock(side_effect=fake_emit))

        await join_channel(sid, {"channel_id": 100})

        assert enter_called['sid'] == sid
        assert enter_called['room'] == 'channel:100'
        assert emitted['event'] == 'channel:joined'
        assert emitted['payload']['channel_id'] == 100

    authenticated_users.pop(sid, None)


@pytest.mark.anyio
async def test_rest_join_private_channel_blocked(client, test_session):
    from app.db.models import User, Channel
    from app.core.security import create_access_token

    user = User(username='u', email='u@example.com', hashed_password='x')
    channel = Channel(name='priv', display_name='Priv', type='private')
    test_session.add_all([user, channel])
    await test_session.commit()

    token = create_access_token({'sub': str(user.id), 'username': user.username})
    resp = await client.post(f'/api/channels/{channel.id}/join', headers={'Authorization': f'Bearer {token}'})
    assert resp.status_code == 403
    assert resp.json().get('detail') == "You are not a member of this channel. Contact admin if that is not the case."


@pytest.mark.anyio
async def test_post_private_channel_by_non_member_blocked(client, test_session):
    from app.db.models import User, Channel
    from app.core.security import create_access_token

    user = User(username='puser', email='p@example.com', hashed_password='x')
    channel = Channel(name='priv2', display_name='Priv2', type='private')
    test_session.add_all([user, channel])
    await test_session.commit()

    token = create_access_token({'sub': str(user.id), 'username': user.username})
    resp = await client.post('/api/messages/', json={'content': 'hello', 'channel_id': channel.id}, headers={'Authorization': f'Bearer {token}'})
    assert resp.status_code == 403
    assert resp.json().get('detail') == "You are not a member of this channel. Contact admin if that is not the case."