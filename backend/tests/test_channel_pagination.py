import pytest
from app.core.security import create_access_token
from datetime import datetime, timedelta

pytestmark = pytest.mark.integration


@pytest.mark.anyio
async def test_channel_messages_pagination_first_page(client, test_session):
    from app.db.models import User, Channel, ChannelMember, Message

    # Create users and channel
    author = User(username='author', email='author@example.com', hashed_password='x')
    member = User(username='member', email='member@example.com', hashed_password='x')
    test_session.add_all([author, member])
    channel = Channel(name='ch-pag', display_name='Pag', type='public')
    test_session.add(channel)
    await test_session.flush()

    # Add membership for member
    membership = ChannelMember(user_id=member.id, channel_id=channel.id)
    test_session.add(membership)

    # Create 5 messages with deterministic times (older -> newer)
    now = datetime.utcnow()
    msgs = []
    for i in range(5):
        m = Message(content=f'msg-{i+1}', channel_id=channel.id, author_id=author.id, created_at=now - timedelta(seconds=60*(5-i)))
        msgs.append(m)
    test_session.add_all(msgs)
    await test_session.commit()

    token = create_access_token({'sub': str(member.id), 'username': member.username})
    resp = await client.get(f'/api/channels/{channel.id}/messages?limit=2', headers={'Authorization': f'Bearer {token}'})
    assert resp.status_code == 200
    data = resp.json()
    assert data['channel_id'] == channel.id
    assert data['has_more'] is True
    messages = data['messages']
    # Should return the 2 newest messages in chronological order (older first)
    assert len(messages) == 2
    assert messages[0]['content'] == 'msg-4'
    assert messages[1]['content'] == 'msg-5'


@pytest.mark.anyio
async def test_channel_messages_pagination_cursor_pages(client, test_session):
    from app.db.models import User, Channel, ChannelMember, Message

    # Create users and channel
    author = User(username='author2', email='author2@example.com', hashed_password='x')
    member = User(username='member2', email='member2@example.com', hashed_password='x')
    test_session.add_all([author, member])
    channel = Channel(name='ch-pag-2', display_name='Pag2', type='public')
    test_session.add(channel)
    await test_session.flush()

    # Add membership for member
    membership = ChannelMember(user_id=member.id, channel_id=channel.id)
    test_session.add(membership)

    # Create 5 messages with deterministic times (older -> newer)
    now = datetime.utcnow()
    msgs = []
    for i in range(5):
        m = Message(content=f'msg-{i+1}', channel_id=channel.id, author_id=author.id, created_at=now - timedelta(seconds=60*(5-i)))
        msgs.append(m)
    test_session.add_all(msgs)
    await test_session.commit()

    token = create_access_token({'sub': str(member.id), 'username': member.username})

    # First page (limit 2) -> msgs 4 and 5
    resp1 = await client.get(f'/api/channels/{channel.id}/messages?limit=2', headers={'Authorization': f'Bearer {token}'})
    assert resp1.status_code == 200
    d1 = resp1.json()
    assert d1['has_more'] is True
    m1 = d1['messages']
    assert [m['content'] for m in m1] == ['msg-4', 'msg-5']

    # Use before = id of first message in that page (older one, msg-4) to fetch older messages
    before_id = m1[0]['id']
    resp2 = await client.get(f'/api/channels/{channel.id}/messages?limit=2&before={before_id}', headers={'Authorization': f'Bearer {token}'})
    assert resp2.status_code == 200
    d2 = resp2.json()
    # Should return msg-2 and msg-3
    assert [m['content'] for m in d2['messages']] == ['msg-2', 'msg-3']
    assert d2['has_more'] is True

    # Continue to last page
    before_id_2 = d2['messages'][0]['id']
    resp3 = await client.get(f'/api/channels/{channel.id}/messages?limit=2&before={before_id_2}', headers={'Authorization': f'Bearer {token}'})
    assert resp3.status_code == 200
    d3 = resp3.json()
    assert [m['content'] for m in d3['messages']] == ['msg-1']
    assert d3['has_more'] is False
