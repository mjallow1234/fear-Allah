import pytest
from app.core.security import create_access_token
from app.db.models import User, DirectConversation, DirectConversationParticipant, Message

pytestmark = pytest.mark.integration


@pytest.mark.anyio
async def test_create_direct_conversation_and_uniqueness(client, test_session):
    # Create two users
    a = User(username='alice', email='alice@example.com', hashed_password='x')
    b = User(username='bob', email='bob@example.com', hashed_password='x')
    test_session.add_all([a, b])
    await test_session.commit()

    token_a = create_access_token({'sub': str(a.id), 'username': a.username})

    # Create conversation
    resp = await client.post('/api/direct-conversations/', json={'other_user_id': b.id}, headers={'Authorization': f'Bearer {token_a}'})
    assert resp.status_code == 201
    data = resp.json()
    assert data['participant_ids'] and set(data['participant_ids']) == {a.id, b.id}
    conv_id = data['id']

    # Creating again returns same conversation
    resp2 = await client.post('/api/direct-conversations/', json={'other_user_id': b.id}, headers={'Authorization': f'Bearer {token_a}'})
    assert resp2.status_code == 201
    assert resp2.json()['id'] == conv_id

    # Creating from other side returns same conversation
    token_b = create_access_token({'sub': str(b.id), 'username': b.username})
    resp3 = await client.post('/api/direct-conversations/', json={'other_user_id': a.id}, headers={'Authorization': f'Bearer {token_b}'})
    assert resp3.status_code == 201
    assert resp3.json()['id'] == conv_id


@pytest.mark.anyio
async def test_only_participants_can_fetch_or_send_messages(client, test_session):
    a = User(username='p1', email='p1@example.com', hashed_password='x')
    b = User(username='p2', email='p2@example.com', hashed_password='x')
    c = User(username='p3', email='p3@example.com', hashed_password='x')
    test_session.add_all([a,b,c])
    await test_session.commit()

    # Create conv directly in DB for test
    conv = DirectConversation(created_by_user_id=a.id, participant_pair=f"{min(a.id,b.id)}:{max(a.id,b.id)}")
    test_session.add(conv)
    await test_session.flush()
    test_session.add_all([
        DirectConversationParticipant(direct_conversation_id=conv.id, user_id=a.id),
        DirectConversationParticipant(direct_conversation_id=conv.id, user_id=b.id)
    ])
    await test_session.commit()

    token_c = create_access_token({'sub': str(c.id), 'username': c.username})

    # Non participant fetch messages
    resp = await client.get(f'/api/direct-conversations/{conv.id}/messages', headers={'Authorization': f'Bearer {token_c}'})
    assert resp.status_code == 403

    # Non participant send message
    resp2 = await client.post(f'/api/direct-conversations/{conv.id}/messages', json={'content': 'hi'}, headers={'Authorization': f'Bearer {token_c}'})
    assert resp2.status_code == 403

    # Participant can send and fetch
    token_a = create_access_token({'sub': str(a.id), 'username': a.username})
    resp3 = await client.post(f'/api/direct-conversations/{conv.id}/messages', json={'content': 'hello'}, headers={'Authorization': f'Bearer {token_a}'})
    assert resp3.status_code == 201
    msg = resp3.json()
    assert msg['content'] == 'hello'

    # Fetch as participant
    resp4 = await client.get(f'/api/direct-conversations/{conv.id}/messages', headers={'Authorization': f'Bearer {token_a}'})
    assert resp4.status_code == 200
    assert any(m['content'] == 'hello' for m in resp4.json())


@pytest.mark.anyio
async def test_dm_messages_do_not_appear_in_channel_messages(client, test_session):
    a = User(username='z1', email='z1@example.com', hashed_password='x')
    b = User(username='z2', email='z2@example.com', hashed_password='x')
    test_session.add_all([a,b])
    await test_session.commit()

    # Create conv
    conv = DirectConversation(created_by_user_id=a.id, participant_pair=f"{min(a.id,b.id)}:{max(a.id,b.id)}")
    test_session.add(conv)
    await test_session.flush()
    test_session.add_all([
        DirectConversationParticipant(direct_conversation_id=conv.id, user_id=a.id),
        DirectConversationParticipant(direct_conversation_id=conv.id, user_id=b.id)
    ])
    await test_session.commit()

    token_a = create_access_token({'sub': str(a.id), 'username': a.username})
    resp = await client.post(f'/api/direct-conversations/{conv.id}/messages', json={'content': 'a dm'}, headers={'Authorization': f'Bearer {token_a}'})
    assert resp.status_code == 201
    created_msg = resp.json()

    # Ensure message in DB has direct_conversation_id set and channel_id is None
    from sqlalchemy import select
    r = await test_session.execute(select(Message).where(Message.id == created_msg['id']))
    m = r.scalar_one()
    assert m.direct_conversation_id == conv.id
    assert m.channel_id is None

    # Ensure channel messages endpoint does not include DM content (no channel assoc)
    # Create a normal channel and ensure its messages do not include the DM
    from app.db.models import Channel
    from app.db.enums import ChannelType
    ch = Channel(name='c123', display_name='c123', type=ChannelType.public.value)
    test_session.add(ch)
    await test_session.commit()

    token_b = create_access_token({'sub': str(b.id), 'username': b.username})
    resp2 = await client.get(f'/api/messages/channel/{ch.id}', headers={'Authorization': f'Bearer {token_b}'})
    assert resp2.status_code == 200
    assert all(m.get('content') != 'a dm' for m in resp2.json())
