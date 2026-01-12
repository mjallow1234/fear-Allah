import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.integration


@pytest.mark.anyio
async def test_register_requires_operational_role(client: AsyncClient):
    # Attempt to register without operational_role -> should fail
    r = await client.post('/api/auth/register', json={'email': 'noop@example.com', 'password': 'Password123!', 'username': 'noop'})
    assert r.status_code == 400
    assert 'operational_role' in r.json().get('detail', '') or 'operational_role' in r.text


@pytest.mark.anyio
async def test_automation_assigns_by_operational_role(client: AsyncClient, test_session):
    # Create a foreman user and an admin user
    # Also create a username-prefixed but differently-role user to prove prefix lookup is ignored
    await client.post('/api/auth/register', json={'email': 'f1@example.com', 'password': 'Password123!', 'username': 'foreman1', 'operational_role': 'foreman'})
    await client.post('/api/auth/register', json={'email': 'foreman_fake@example.com', 'password': 'Password123!', 'username': 'foreman_fake', 'operational_role': 'agent'})
    await client.post('/api/auth/register', json={'email': 'admin@example.com', 'password': 'Password123!', 'username': 'adminuser', 'operational_role': 'agent'})
    # Make admin a system admin
    from app.db.models import User
    res = await test_session.execute(__import__('sqlalchemy').select(User).where(User.username == 'adminuser'))
    admin = res.scalar_one()
    admin.is_system_admin = True
    test_session.add(admin)
    await test_session.commit()

    # Login as foreman to create an order
    login = await client.post('/api/auth/login', json={'identifier': 'f1@example.com', 'password': 'Password123!'})
    token = login.json()['access_token']

    # Create an agent_restock order which should assign a foreman
    resp = await client.post('/api/orders/', json={'order_type': 'AGENT_RESTOCK', 'items': []}, headers={'Authorization': f'Bearer {token}'})
    assert resp.status_code == 201
    data = resp.json()
    order_id = data['order_id']

    # Inspect automation tasks and assignments
    from app.db.models import AutomationTask, TaskAssignment, User
    q = await test_session.execute(__import__('sqlalchemy').select(AutomationTask).where(AutomationTask.related_order_id == order_id))
    tasks = q.scalars().all()
    assert tasks, "Expected automation tasks to be created for the order"

    # At least one assignment should be to a user whose operational_role == 'foreman' or to admin fallback
    assigned_user_ids = []
    for t in tasks:
        qa = await test_session.execute(__import__('sqlalchemy').select(TaskAssignment).where(TaskAssignment.task_id == t.id))
        assigns = qa.scalars().all()
        assigned_user_ids.extend([a.user_id for a in assigns if a.user_id])

    assert assigned_user_ids, "No assignments created"

    # Check that at least one assigned user has operational_role 'foreman' or is system_admin
    found = False
    for uid in assigned_user_ids:
        res = await test_session.execute(__import__('sqlalchemy').select(User).where(User.id == uid))
        u = res.scalar_one()
        if getattr(u, 'operational_role', None) == 'foreman' or u.is_system_admin:
            # Ensure we didn't select the username-prefixed but differently-role user
            assert u.username != 'foreman_fake', 'Assigned user was chosen by username prefix instead of operational_role'
            found = True
            break
    assert found, "Assignment did not select a foreman or admin fallback"
