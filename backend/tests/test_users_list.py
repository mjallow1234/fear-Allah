import pytest


@pytest.mark.asyncio
async def test_list_users_endpoint(client, test_session):
    # Create two users
    from app.db.models import User
    from app.core.security import get_password_hash

    u1 = User(username='u1', email='u1@example.com', hashed_password=get_password_hash('pass'), is_active=True)
    u2 = User(username='u2', email='u2@example.com', hashed_password=get_password_hash('pass'), is_active=True)
    test_session.add_all([u1, u2])
    await test_session.commit()
    await test_session.refresh(u1)
    await test_session.refresh(u2)

    resp = await client.get('/api/users/')
    assert resp.status_code == 200, f"Unexpected status: {resp.status_code} body: {resp.text}"
    data = resp.json()
    assert isinstance(data, list)
    assert any(u['username'] == 'u1' for u in data)
    assert any(u['username'] == 'u2' for u in data)
