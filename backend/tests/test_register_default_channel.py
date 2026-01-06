import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.models import Channel, ChannelMember, Message, User

pytestmark = pytest.mark.integration


@pytest.mark.anyio
async def test_register_adds_user_to_general_and_can_fetch_messages(client: AsyncClient, test_session: AsyncSession):
    # Avoid demo onboarding to ensure deterministic behavior
    old_env = settings.APP_ENV
    settings.APP_ENV = 'production'

    # Create a seed author and a general channel with a message
    seed = User(email='seed@test.com', username='seed', hashed_password='x', is_active=True)
    test_session.add(seed)
    await test_session.commit()
    await test_session.refresh(seed)

    general = Channel(name='general', display_name='General', description='General discussion', type='public')
    test_session.add(general)
    await test_session.commit()
    await test_session.refresh(general)

    msg = Message(content='Welcome!', channel_id=general.id, author_id=seed.id)
    test_session.add(msg)
    await test_session.commit()
    await test_session.refresh(msg)

    # Register new user
    r = await client.post('/api/auth/register', json={'email': 'newuser@example.com', 'password': 'Password123!', 'username': 'newuser'})
    assert r.status_code == 201
    token = r.json()['access_token']

    # Ensure membership exists for general
    result = await test_session.execute(select(ChannelMember).where(ChannelMember.user_id == r.json()['user']['id']))
    memberships = result.scalars().all()
    assert any(m.channel_id == general.id for m in memberships), "New user must be member of general channel"

    # User can fetch messages from general
    dl = await client.get(f'/api/messages/channel/{general.id}', headers={'Authorization': f'Bearer {token}'})
    assert dl.status_code == 200
    # API returns a list of messages
    assert any(m['content'] == 'Welcome!' for m in dl.json())
    # Restore env
    settings.APP_ENV = old_env


@pytest.mark.anyio
async def test_register_creates_general_if_missing_and_membership_is_single(client: AsyncClient, test_session: AsyncSession):
    old_env = settings.APP_ENV
    settings.APP_ENV = 'production'

    # Ensure no general channel exists
    from sqlalchemy import delete
    await test_session.execute(delete(ChannelMember))
    await test_session.execute(delete(Channel))
    await test_session.commit()

    r = await client.post('/api/auth/register', json={'email': 'solo@example.com', 'password': 'Password123!', 'username': 'solo'})
    assert r.status_code == 201
    user_id = r.json()['user']['id']

    # General should now exist
    result = await test_session.execute(select(Channel).where(Channel.name == 'general'))
    general = result.scalar_one_or_none()
    assert general is not None

    # User should be member of exactly one channel (the default)
    result = await test_session.execute(select(ChannelMember).where(ChannelMember.user_id == user_id))
    memberships = result.scalars().all()
    assert len(memberships) == 1
    assert memberships[0].channel_id == general.id

    settings.APP_ENV = old_env


@pytest.mark.anyio
async def test_non_member_cannot_access_private_channel(client: AsyncClient, test_session: AsyncSession):
    old_env = settings.APP_ENV
    settings.APP_ENV = 'production'

    # Create private channel and message
    author = User(email='auth2@test.com', username='auth2', hashed_password='x', is_active=True)
    test_session.add(author)
    await test_session.commit()
    await test_session.refresh(author)

    private = Channel(name='secret', display_name='Secret', description='Private', type='private')
    test_session.add(private)
    await test_session.commit()
    await test_session.refresh(private)

    msg = Message(content='Top secret', channel_id=private.id, author_id=author.id)
    test_session.add(msg)
    await test_session.commit()
    await test_session.refresh(msg)

    # Register new user
    r = await client.post('/api/auth/register', json={'email': 'outsider2@example.com', 'password': 'Password123!', 'username': 'outsider2'})
    assert r.status_code == 201
    token = r.json()['access_token']

    # Attempt to fetch private messages
    dl = await client.get(f'/api/messages/channel/{private.id}', headers={'Authorization': f'Bearer {token}'})
    assert dl.status_code == 403

    settings.APP_ENV = old_env