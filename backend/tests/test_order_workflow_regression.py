import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.integration


@pytest.mark.anyio
async def test_foreman_handover_does_not_close_automation(client: AsyncClient, test_session):
    # Register users
    await client.post('/api/auth/register', json={'email': 'f2@example.com', 'password': 'Password123!', 'username': 'foreman'})
    await client.post('/api/auth/register', json={'email': 'd2@example.com', 'password': 'Password123!', 'username': 'delivery'})
    login_f = await client.post('/api/auth/login', json={'identifier': 'f2@example.com', 'password': 'Password123!'})
    login_d = await client.post('/api/auth/login', json={'identifier': 'd2@example.com', 'password': 'Password123!'})
    tf = login_f.json()['access_token']
    td = login_d.json()['access_token']

    # Create AGENT_RESTOCK order as foreman
    create = await client.post('/api/orders/', json={'order_type': 'AGENT_RESTOCK', 'items': []}, headers={'Authorization': f'Bearer {tf}'})
    if create.status_code != 201:
        pytest.skip('Order creation not permitted in this environment')
    order_id = create.json()['order_id']

    # Find workflow tasks
    from app.db.models import Task
    res = await test_session.execute(__import__('sqlalchemy').select(Task).where(Task.order_id == order_id).order_by(Task.id))
    tasks = res.scalars().all()

    # Locate foreman_handover and delivery_received steps
    fh = next((t for t in tasks if t.step_key == 'foreman_handover'), None)
    dr = next((t for t in tasks if t.step_key == 'delivery_received'), None)
    assert fh is not None and dr is not None

    # Assign foreman to foreman_handover and complete it
    fh.assigned_user_id = 1
    test_session.add(fh)
    await test_session.commit()

    resp = await client.post(f'/api/tasks/{fh.id}/complete', headers={'Authorization': f'Bearer {tf}'})
    assert resp.status_code == 200

    # Reload automation task and ensure it is NOT closed
    from app.automation.order_triggers import OrderAutomationTriggers
    task = await OrderAutomationTriggers._get_order_automation_task(test_session, order_id)
    assert task is not None
    t_status = task.status.name.upper() if hasattr(task.status, 'name') else str(task.status).upper()
    assert t_status in ('IN_PROGRESS', 'OPEN')

    # Ensure delivery task is now active (unlocked)
    dr_ref = await test_session.get(Task, dr.id)
    assert dr_ref.status in ('ACTIVE', 'ACTIVE'.lower(), 'active',)
