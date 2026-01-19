import pytest

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Role, UserRole as UserRoleModel


@pytest.mark.asyncio
async def test_auth_me_returns_operational_role(client, test_session, user_token):
    # Create an operational role and assign it to the user created by user_token fixture
    role = Role(name='agent', is_system=False)
    test_session.add(role)
    await test_session.commit()
    await test_session.refresh(role)

    # Find the test user created in user_token fixture
    result = await test_session.execute(select(UserRoleModel).where(UserRoleModel.user_id != None))
    # ensure no pre-existing assignment

    # Find the user id from the token fixture by decoding header
    # user_token fixture created a user with email testuser@example.com
    # We need to fetch that user first
    from app.db.models import User
    user_result = await test_session.execute(select(User).where(User.email == 'testuser@example.com'))
    user = user_result.scalar_one_or_none()
    assert user is not None

    # Assign the operational role
    assignment = UserRoleModel(user_id=user.id, role_id=role.id)
    test_session.add(assignment)
    await test_session.commit()

    # Call /api/auth/me with the provided Authorization header
    resp = await client.get('/api/auth/me', headers=user_token)
    assert resp.status_code == 200
    data = resp.json()
    assert 'operational_role_name' in data
    assert data['operational_role_name'] == 'agent'
