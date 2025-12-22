import pytest
from app.core.security import create_access_token
from datetime import datetime, timedelta

pytestmark = pytest.mark.integration


@pytest.mark.anyio
async def test_channel_messages_authorized_returns_messages_ordering(client, test_session):
    from app.db.models import User, Channel, ChannelMember, Message

    # Create users and channel
    author = User(username='author', email='author@example.com', hashed_password='x')
    member = User(username='member', email='member@example.com', hashed_password='x')
    test_session.add_all([author, member])
    channel = Channel(name='ch1', display_name='Ch 1', type='public')
    test_session.add(channel)
    await test_session.flush()

    # Add membership for member
    membership = ChannelMember(user_id=member.id, channel_id=channel.id)
    test_session.add(membership)

    # Create messages with deterministic creation times
    now = datetime.utcnow()
    msg1 = Message(content='first', channel_id=channel.id, author_id=author.id, created_at=now - timedelta(seconds=10))
    msg2 = Message(content='second', channel_id=channel.id, author_id=author.id, created_at=now)
    test_session.add_all([msg1, msg2])
    await test_session.commit()

    token = create_access_token({'sub': str(member.id), 'username': member.username})
    resp = await client.get(f'/api/channels/{channel.id}/messages?limit=50&before_id=1', headers={'Authorization': f'Bearer {token}'})
    assert resp.status_code == 200
    data = resp.json()
    assert data['channel_id'] == channel.id
    messages = data['messages']
    # two messages
    assert len(messages) == 2
    # ordering ascending by created_at: first message content should be 'first'
    assert messages[0]['content'] == 'first'
    assert messages[1]['content'] == 'second'


@pytest.mark.anyio
async def test_channel_messages_unauthorized_user_forbidden(client, test_session):
    from app.db.models import User, Channel

    user = User(username='other', email='other@example.com', hashed_password='x')
    channel = Channel(name='secret', display_name='Secret', type='public')
    test_session.add_all([user, channel])
    await test_session.commit()

    token = create_access_token({'sub': str(user.id), 'username': user.username})
    resp = await client.get(f'/api/channels/{channel.id}/messages', headers={'Authorization': f'Bearer {token}'})
    assert resp.status_code == 403


@pytest.mark.anyio
async def test_channel_messages_empty_channel_returns_empty_list(client, test_session):
    from app.db.models import User, Channel, ChannelMember

    user = User(username='reader', email='reader@example.com', hashed_password='x')
    channel = Channel(name='empty', display_name='Empty', type='public')
    test_session.add_all([user, channel])
    await test_session.flush()

    member = ChannelMember(user_id=user.id, channel_id=channel.id)
    test_session.add(member)
    await test_session.commit()

    token = create_access_token({'sub': str(user.id), 'username': user.username})
    resp = await client.get(f'/api/channels/{channel.id}/messages', headers={'Authorization': f'Bearer {token}'})
    assert resp.status_code == 200
    data = resp.json()
    assert data['channel_id'] == channel.id
    assert data['messages'] == []
