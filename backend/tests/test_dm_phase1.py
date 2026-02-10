import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from app.core.security import create_access_token
from app.db.models import User, Channel, ChannelMember, Message
from app.db.enums import ChannelType
import asyncio

pytestmark = pytest.mark.integration


@pytest.mark.anyio
async def test_emit_message_new_routes_to_dm_room(monkeypatch, test_session):
    # Create a DM channel
    a = User(username='d1', email='d1@example.com', hashed_password='x')
    b = User(username='d2', email='d2@example.com', hashed_password='x')
    test_session.add_all([a,b])
    await test_session.flush()

    dm = Channel(name='dm-test', display_name='DM', type=ChannelType.direct.value)
    test_session.add(dm)
    await test_session.commit()

    called = {}
    async def fake_emit(event, payload=None, room=None, **kwargs):
        called['event'] = event
        called['payload'] = payload
        called['room'] = room

    monkeypatch.setattr('app.realtime.socket.sio.emit', AsyncMock(side_effect=fake_emit))

    from app.realtime.socket import emit_message_new
    await emit_message_new(dm.id, {"id": 1, "content": "hi"})

    assert called.get('room') == f"dm:{dm.id}"

    # Public channel should route to channel:{id}
    ch = Channel(name='pub1', display_name='Pub1', type=ChannelType.public.value)
    test_session.add(ch)
    await test_session.commit()

    await emit_message_new(ch.id, {"id": 2, "content": "hello"})
    assert called.get('room') == f"channel:{ch.id}"


@pytest.mark.anyio
async def test_manager_broadcast_to_dm_only_delivers_to_participants(client, test_session):
    from app.api.ws import manager

    # Create users and DM
    a = User(username='ma', email='a@ex', hashed_password='x')
    b = User(username='mb', email='b@ex', hashed_password='x')
    c = User(username='mc', email='c@ex', hashed_password='x')
    test_session.add_all([a,b,c])
    await test_session.flush()

    dm = Channel(name='dm-room', display_name='dm', type=ChannelType.direct.value)
    ch = Channel(name='chan-room', display_name='chan', type=ChannelType.public.value)
    test_session.add_all([dm, ch])
    await test_session.flush()

    # Add members for dm: a and b
    m1 = ChannelMember(user_id=a.id, channel_id=dm.id)
    m2 = ChannelMember(user_id=b.id, channel_id=dm.id)
    test_session.add_all([m1,m2])
    await test_session.commit()

    # Fake websockets
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

    ws_a = FakeWS(); ws_b = FakeWS(); ws_c = FakeWS()

    # Connect a and b to DM
    await manager.connect(ws_a, dm.id, a.id, 'ma')
    await manager.connect(ws_b, dm.id, b.id, 'mb')

    # Connect c to a different public channel
    await manager.connect(ws_c, ch.id, c.id, 'mc')

    # Broadcast to DM -> should only deliver to a and b
    await manager.broadcast_to_channel(dm.id, {"type": "message", "content": "secret"})
    assert any(m['content'] == 'secret' for m in ws_a.received)
    assert any(m['content'] == 'secret' for m in ws_b.received)
    assert not any(m['content'] == 'secret' for m in ws_c.received)


@pytest.mark.anyio
async def test_nonparticipant_cannot_connect_to_dm_ws(monkeypatch):
    from app.api.ws import manager
    # Prepare fake websocket
    class FakeWS:
        def __init__(self):
            self.closed = False
            self.accepted = False
        async def accept(self):
            self.accepted = True
        async def close(self, code=1000):
            self.closed = True
    fake_ws = FakeWS()

    # Mock DB: channel is direct and membership missing
    mock_channel = MagicMock(); mock_channel.id = 50; mock_channel.type = 'direct'
    mock_res_channel = MagicMock(); mock_res_channel.scalar_one_or_none.return_value = mock_channel

    mock_member_res = MagicMock(); mock_member_res.scalar_one_or_none.return_value = None

    mock_db = AsyncMock()
    mock_db.execute = AsyncMock(side_effect=[mock_res_channel, mock_member_res])
    mock_cm = AsyncMock(); mock_cm.__aenter__.return_value = mock_db; mock_cm.__aexit__.return_value = None

    with patch('app.db.database.async_session', return_value=mock_cm):
        await manager.connect(fake_ws, 50, 9999, 'ghost')
        # Expect it to have closed the websocket
        assert fake_ws.closed is True


@pytest.mark.anyio
async def test_admin_cannot_manage_dm_endpoints(client, test_session):
    # Create admin and DM channel
    admin = User(username='adm', email='adm@example.com', hashed_password='x')
    u = User(username='u1', email='u1@example.com', hashed_password='x')
    test_session.add_all([admin, u])
    await test_session.flush()
    admin.is_system_admin = True
    dm = Channel(name='dman', display_name='dman', type=ChannelType.direct.value)
    test_session.add(dm)
    await test_session.commit()

    token = create_access_token({'sub': str(admin.id), 'username': admin.username})
    # Attempt to add member
    resp = await client.post(f'/api/channels/{dm.id}/members', json={'user_id': u.id}, headers={'Authorization': f'Bearer {token}'})
    assert resp.status_code == 403
    assert resp.json().get('detail') == "Direct messages cannot be managed as channels."

    # Attempt to remove member
    resp2 = await client.delete(f'/api/channels/{dm.id}/members/{u.id}', headers={'Authorization': f'Bearer {token}'})
    assert resp2.status_code == 403
    assert resp2.json().get('detail') == "Direct messages cannot be managed as channels."


@pytest.mark.anyio
async def test_dm_post_and_fetch_blocked_for_non_participant(client, test_session):
    # Create users and DM between a and b
    a = User(username='da', email='da@example.com', hashed_password='x')
    b = User(username='db', email='db@example.com', hashed_password='x')
    c = User(username='dc', email='dc@example.com', hashed_password='x')
    test_session.add_all([a,b,c])
    await test_session.flush()

    dm = Channel(name='dm2', display_name='dm2', type=ChannelType.direct.value)
    test_session.add(dm)
    await test_session.flush()
    test_session.add_all([ChannelMember(user_id=a.id, channel_id=dm.id), ChannelMember(user_id=b.id, channel_id=dm.id)])
    await test_session.commit()

    token_c = create_access_token({'sub': str(c.id), 'username': c.username})

    # Attempt to post as non-participant
    resp = await client.post('/api/messages/', json={'content': 'm', 'channel_id': dm.id}, headers={'Authorization': f'Bearer {token_c}'})
    assert resp.status_code == 403
    assert resp.json().get('detail') == "You are not a participant in this direct conversation."

    # Attempt to fetch messages as non-participant
    resp2 = await client.get(f'/api/channels/{dm.id}/messages', headers={'Authorization': f'Bearer {token_c}'})
    assert resp2.status_code == 403
    assert resp2.json().get('detail') == "You are not a participant in this direct conversation."