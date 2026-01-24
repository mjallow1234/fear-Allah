import pytest
from app.core.security import create_access_token
from sqlalchemy import select
from app.db.models import AuditLog, User


@pytest.mark.asyncio
async def test_admin_can_view_audit_logs(client, test_session):

    # Create admin user
    admin = User(email='auditor@example.com', username='auditor', display_name='Auditor', hashed_password='x', is_active=True, is_system_admin=True)
    test_session.add(admin)
    await test_session.commit()
    await test_session.refresh(admin)

    # Insert an audit row using the existing AuditLog model
    row = AuditLog(
        user_id=admin.id,
        username=admin.username,
        action='create',
        target_type='raw_materials',
        target_id=1,
        description='Created RM',
        ip_address='127.0.0.1'
    )
    test_session.add(row)
    await test_session.commit()

    token = create_access_token({"sub": str(admin.id), "username": admin.username, "is_system_admin": admin.is_system_admin})

    resp = await client.get('/api/audit/logs', headers={'Authorization': f'Bearer {token}'})
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert 'items' in data
    assert data['total'] >= 1
    first = data['items'][0]
    assert first['action'] == 'create'
    assert first['resource'] == 'raw_materials'
    assert first['user_id'] == admin.id


@pytest.mark.asyncio
async def test_non_admin_cannot_view_audit_logs(client, test_session):

    # Create non-admin user
    user = User(email='user@example.com', username='user1', display_name='User1', hashed_password='x', is_active=True, is_system_admin=False)
    test_session.add(user)
    await test_session.commit()
    await test_session.refresh(user)

    token = create_access_token({"sub": str(user.id), "username": user.username, "is_system_admin": user.is_system_admin})

    resp = await client.get('/api/audit/logs', headers={'Authorization': f'Bearer {token}'})
    assert resp.status_code == 403
