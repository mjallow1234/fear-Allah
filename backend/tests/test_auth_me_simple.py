import pytest


@pytest.mark.asyncio
async def test_me_returns_user_and_operational_role_field(client):
    # Login as seeded admin
    resp = await client.post('/api/auth/login', json={'identifier': 'admin', 'password': 'admin123'})
    assert resp.status_code == 200
    data = resp.json()
    assert 'access_token' in data
    token = data['access_token']

    # Call /api/auth/me
    resp2 = await client.get('/api/auth/me', headers={'Authorization': f'Bearer {token}'})
    assert resp2.status_code == 200
    body = resp2.json()
    # Ensure operational_role_name key exists (may be None)
    assert 'operational_role_name' in body


@pytest.mark.asyncio
async def test_me_with_authenticated_fixture(async_client_authenticated, test_session):
    client, meta = async_client_authenticated
    token = meta['token']

    # Create an operational role and assign it to this user
    from app.db.models import Role, UserRole as UserRoleModel
    role = Role(name='agent', is_system=False)
    test_session.add(role)
    await test_session.commit()
    await test_session.refresh(role)

    assignment = UserRoleModel(user_id=meta['user_id'], role_id=role.id)
    test_session.add(assignment)
    await test_session.commit()

    # Call /api/auth/me using provided token
    resp = await client.get('/api/auth/me', headers={'Authorization': f'Bearer {token}'})
    assert resp.status_code == 200
    data = resp.json()
    assert data.get('operational_role_name') == 'agent'
