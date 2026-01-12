import pytest
from httpx import AsyncClient

from app.core.security import create_access_token

pytestmark = pytest.mark.integration


@pytest.mark.anyio
async def test_non_admin_cannot_create_channel(client: AsyncClient, test_session):
    # Create a normal user
    from app.db.models import User
    user = User(username='normal', email='normal@example.com', hashed_password='x', operational_role='agent')
    test_session.add(user)
    await test_session.commit()

    token = create_access_token({'sub': str(user.id), 'username': user.username})

    resp = await client.post('/api/channels', json={'name': 'foo', 'display_name': 'Foo', 'type': 'O'}, headers={'Authorization': f'Bearer {token}'})
    assert resp.status_code == 403


@pytest.mark.anyio
async def test_admin_can_create_channel_and_broadcast(client: AsyncClient, test_session, monkeypatch):
    from app.db.models import User, ChannelMember
    # Create admin user directly
    admin = User(username='admin', email='admin@example.com', hashed_password='x', operational_role='agent', is_system_admin=True)
    test_session.add(admin)
    await test_session.commit()

    token = create_access_token({'sub': str(admin.id), 'username': admin.username})

    # Capture broadcast events
    captured = []

    async def fake_broadcast(msg):
        captured.append(msg)

    # Patch the ws manager broadcast_presence
    from app.api import ws as ws_module
    monkeypatch.setattr(ws_module.manager, 'broadcast_presence', fake_broadcast)

    resp = await client.post('/api/channels', json={'name': 'newchan', 'display_name': 'New Channel', 'type': 'O'}, headers={'Authorization': f'Bearer {token}'})
    assert resp.status_code == 201
    data = resp.json()
    assert data['name'] == 'newchan'

    # verify creator added as member
    query = await test_session.execute(
        __import__('sqlalchemy').select(ChannelMember).where(ChannelMember.channel_id == data['id'], ChannelMember.user_id == admin.id)
    )
    membership = query.scalar_one_or_none()
    assert membership is not None

    # ensure broadcast happened
    assert any(m.get('type') == 'channel_created' for m in captured)


@pytest.mark.anyio
async def test_mark_channel_read_updates_last_read_at(client: AsyncClient, test_session):
    from app.db.models import User, Channel, ChannelMember
    from app.core.security import create_access_token

    # Create user, channel, membership
    user = User(username='reader', email='reader@example.com', hashed_password='x', operational_role='agent')
    test_session.add(user)
    channel = Channel(name='readchan', display_name='Read Chan', type='public')
    test_session.add(channel)
    await test_session.flush()

    membership = ChannelMember(user_id=user.id, channel_id=channel.id)
    test_session.add(membership)
    await test_session.commit()

    token = create_access_token({'sub': str(user.id), 'username': user.username})

    resp = await client.post(f'/api/channels/{channel.id}/read', headers={'Authorization': f'Bearer {token}'})
    assert resp.status_code == 200
    data = resp.json()
    assert data['channel_id'] == channel.id
    assert data['last_read_at'] is not None


@pytest.mark.anyio
async def test_mark_channel_read_non_member_forbidden(client: AsyncClient, test_session):
    from app.db.models import User, Channel
    from app.core.security import create_access_token

    user = User(username='other', email='other@example.com', hashed_password='x', operational_role='agent')
    test_session.add(user)
    channel = Channel(name='noch', display_name='No Ch', type='public')
    test_session.add(channel)
    await test_session.commit()

    token = create_access_token({'sub': str(user.id), 'username': user.username})
    resp = await client.post(f'/api/channels/{channel.id}/read', headers={'Authorization': f'Bearer {token}'})
    assert resp.status_code == 403


@pytest.mark.anyio
async def test_mark_channel_read_invalid_channel_returns_404(client: AsyncClient, test_session):
    from app.db.models import User
    from app.core.security import create_access_token

    user = User(username='u404', email='u404@example.com', hashed_password='x', operational_role='agent')
    test_session.add(user)
    await test_session.commit()

    token = create_access_token({'sub': str(user.id), 'username': user.username})
    resp = await client.post('/api/channels/999999/read', headers={'Authorization': f'Bearer {token}'})
    assert resp.status_code == 404
