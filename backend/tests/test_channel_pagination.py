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
    # Should return the 2 newest messages (newest first under activity ordering)
    assert len(messages) == 2
    assert messages[0]['content'] == 'msg-5'
    assert messages[1]['content'] == 'msg-4'


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

    # First page (limit 2) -> msgs 5 and 4 (newest first)
    resp1 = await client.get(f'/api/channels/{channel.id}/messages?limit=2', headers={'Authorization': f'Bearer {token}'})
    assert resp1.status_code == 200
    d1 = resp1.json()
    assert d1['has_more'] is True
    m1 = d1['messages']
    assert [m['content'] for m in m1] == ['msg-5', 'msg-4']

    # Use before = id of the last message in that page (older one, msg-4) to fetch older messages
    before_id = m1[-1]['id']
    resp2 = await client.get(f'/api/channels/{channel.id}/messages?limit=2&before={before_id}', headers={'Authorization': f'Bearer {token}'})
    assert resp2.status_code == 200
    d2 = resp2.json()
    # Should return msg-3 and msg-2 (newest-first for that slice)
    assert [m['content'] for m in d2['messages']] == ['msg-3', 'msg-2']
    assert d2['has_more'] is True

    # Continue to last page (use the last item of page2 as the cursor)
    before_id_2 = d2['messages'][-1]['id']
    resp3 = await client.get(f'/api/channels/{channel.id}/messages?limit=2&before={before_id_2}', headers={'Authorization': f'Bearer {token}'})
    assert resp3.status_code == 200
    d3 = resp3.json()
    assert [m['content'] for m in d3['messages']] == ['msg-1']
    assert d3['has_more'] is False


@pytest.mark.anyio
async def test_reply_promotes_parent_in_activity_ordering(client, test_session):
    from app.db.models import User, Channel, ChannelMember, Message
    from app.core.security import create_access_token
    from datetime import datetime, timedelta

    # Setup users and channel
    author = User(username='author_promote', email='ap@example.com', hashed_password='x')
    member = User(username='member_promote', email='mp@example.com', hashed_password='x')
    test_session.add_all([author, member])
    channel = Channel(name='ch-promote', display_name='Promote', type='public')
    test_session.add(channel)
    await test_session.flush()
    test_session.add(ChannelMember(user_id=member.id, channel_id=channel.id))

    # Create 3 messages m1 (oldest), m2, m3 (newest)
    now = datetime.utcnow()
    m1 = Message(content='m1', channel_id=channel.id, author_id=author.id, created_at=now - timedelta(seconds=30))
    m2 = Message(content='m2', channel_id=channel.id, author_id=author.id, created_at=now - timedelta(seconds=20))
    m3 = Message(content='m3', channel_id=channel.id, author_id=author.id, created_at=now - timedelta(seconds=10))
    test_session.add_all([m1, m2, m3])
    await test_session.commit()

    token = create_access_token({'sub': str(member.id), 'username': member.username})

    # Reply to m1 so its last_activity_at becomes newest
    resp_reply = await client.post(f'/api/messages/{m1.id}/reply', json={'content': 'reply-to-m1'}, headers={'Authorization': f'Bearer {token}'})
    assert resp_reply.status_code == 200

    # Fetch channel messages (activity-ordered): expect ordering by last_activity_at -> m2, m3, m1 (m1 was promoted)
    resp = await client.get(f'/api/channels/{channel.id}/messages', headers={'Authorization': f'Bearer {token}'})
    assert resp.status_code == 200
    msgs = resp.json()['messages']
    contents = [m['content'] for m in msgs]
    assert contents == ['m2', 'm3', 'm1']


@pytest.mark.anyio
async def test_cursor_pagination_stable_with_activity_ordering(client, test_session):
    from app.db.models import User, Channel, ChannelMember, Message
    from app.core.security import create_access_token
    from datetime import datetime, timedelta

    # Setup
    author = User(username='author_cursor', email='ac@example.com', hashed_password='x')
    member = User(username='member_cursor', email='mc@example.com', hashed_password='x')
    test_session.add_all([author, member])
    channel = Channel(name='ch-cursor', display_name='Cursor', type='public')
    test_session.add(channel)
    await test_session.flush()
    test_session.add(ChannelMember(user_id=member.id, channel_id=channel.id))

    # Create 5 messages
    now = datetime.utcnow()
    msgs = []
    for i in range(5):
        m = Message(content=f'msg-{i+1}', channel_id=channel.id, author_id=author.id, created_at=now - timedelta(seconds=60*(5-i)))
        msgs.append(m)
    test_session.add_all(msgs)
    await test_session.commit()

    token = create_access_token({'sub': str(member.id), 'username': member.username})

    # Reply to msg-2 to promote it
    full = (await client.get(f'/api/channels/{channel.id}/messages', headers={'Authorization': f'Bearer {token}'})).json()['messages']
    msg2 = next(m for m in full if m['content'] == 'msg-2')
    r = await client.post(f"/api/messages/{msg2['id']}/reply", json={'content': 'promote'}, headers={'Authorization': f'Bearer {token}'})
    assert r.status_code == 200

    # Read full ordered list (baseline)
    baseline = (await client.get(f'/api/channels/{channel.id}/messages', headers={'Authorization': f'Bearer {token}'})).json()['messages']
    # Now page through with limit=2 and concatenate
    page1 = (await client.get(f'/api/channels/{channel.id}/messages?limit=2', headers={'Authorization': f'Bearer {token}'})).json()
    assert page1['has_more'] is True
    p1 = page1['messages']

    before_id = p1[-1]['id']
    page2 = (await client.get(f'/api/channels/{channel.id}/messages?limit=2&before={before_id}', headers={'Authorization': f'Bearer {token}'})).json()
    p2 = page2['messages']

    before_id_2 = p2[-1]['id'] if p2 else None
    page3 = (await client.get(f'/api/channels/{channel.id}/messages?limit=2&before={before_id_2}', headers={'Authorization': f'Bearer {token}'})).json() if before_id_2 else {'messages': []}
    p3 = page3['messages']

    concatenated = p1 + p2 + p3
    # concatenated should equal baseline
    assert [m['id'] for m in concatenated] == [m['id'] for m in baseline]
