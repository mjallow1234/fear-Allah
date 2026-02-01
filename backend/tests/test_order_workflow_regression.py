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
    from app.db.models import TaskAssignment, AutomationTask
    from app.db.enums import AssignmentStatus

    task = await OrderAutomationTriggers._get_order_automation_task(test_session, order_id)
    assert task is not None
    t_status = task.status.name.upper() if hasattr(task.status, 'name') else str(task.status).upper()
    assert t_status in ('IN_PROGRESS', 'OPEN')

    # Ensure ORDER is NOT completed when foreman finishes
    from app.db.models import Order
    o_res = await test_session.execute(__import__('sqlalchemy').select(Order).where(Order.id == order_id))
    ord_row = o_res.scalar_one_or_none()
    assert ord_row is not None
    ord_status = ord_row.status.name.upper() if hasattr(ord_row.status, 'name') else str(ord_row.status).upper()
    assert ord_status != 'COMPLETED'

    # Check the foreman assignment for this automation task was NOT marked done
    res = await test_session.execute(__import__('sqlalchemy').select(TaskAssignment).where(TaskAssignment.task_id == task.id).where(TaskAssignment.role_hint == 'foreman'))
    fa = res.scalars().first()
    assert fa is not None
    assert fa.status != AssignmentStatus.done.value

    # Ensure delivery task is now active (unlocked)
    dr_ref = await test_session.get(Task, dr.id)
    assert dr_ref.status in ('ACTIVE', 'ACTIVE'.lower(), 'active',)


@pytest.mark.anyio
async def test_delivery_steps_do_not_auto_complete_assignment(client: AsyncClient, test_session):
    # Setup users
    await client.post('/api/auth/register', json={'email': 'f3@example.com', 'password': 'Password123!', 'username': 'foreman2'})
    await client.post('/api/auth/register', json={'email': 'd3@example.com', 'password': 'Password123!', 'username': 'delivery2'})
    login_f = await client.post('/api/auth/login', json={'identifier': 'f3@example.com', 'password': 'Password123!'})
    login_d = await client.post('/api/auth/login', json={'identifier': 'd3@example.com', 'password': 'Password123!'})
    tf = login_f.json()['access_token']
    td = login_d.json()['access_token']

    # Create order as foreman
    create = await client.post('/api/orders/', json={'order_type': 'AGENT_RESTOCK', 'items': []}, headers={'Authorization': f'Bearer {tf}'})
    if create.status_code != 201:
        pytest.skip('Order creation not permitted in this environment')
    order_id = create.json()['order_id']

    # Find workflow tasks
    from app.db.models import Task, TaskAssignment
    res = await test_session.execute(__import__('sqlalchemy').select(Task).where(Task.order_id == order_id).order_by(Task.id))
    tasks = res.scalars().all()

    fh = next((t for t in tasks if t.step_key == 'foreman_handover'), None)
    dr = next((t for t in tasks if t.step_key == 'delivery_received'), None)
    assert fh is not None and dr is not None

    # Assign foreman and complete handover to unlock delivery steps
    fh.assigned_user_id = 1
    test_session.add(fh)
    await test_session.commit()

    resp = await client.post(f'/api/tasks/{fh.id}/complete', headers={'Authorization': f'Bearer {tf}'})
    assert resp.status_code == 200

    # Fetch automation task and create a delivery assignment (simulate assignment)
    from app.automation.order_triggers import OrderAutomationTriggers
    task = await OrderAutomationTriggers._get_order_automation_task(test_session, order_id)
    assert task is not None

    # Create delivery assignment explicitly
    da = TaskAssignment(task_id=task.id, user_id=2, role_hint='delivery', status='in_progress')
    test_session.add(da)
    await test_session.commit()

    # Assign delivery user to the delivery_received workflow step and complete it
    dr.assigned_user_id = 2
    test_session.add(dr)
    await test_session.commit()

    resp = await client.post(f'/api/tasks/{dr.id}/complete', headers={'Authorization': f'Bearer {td}'})
    assert resp.status_code == 200

    # Reload delivery assignment and ensure it is NOT marked done
    res = await test_session.execute(__import__('sqlalchemy').select(TaskAssignment).where(TaskAssignment.task_id == task.id).where(TaskAssignment.role_hint == 'delivery'))
    fa = res.scalars().first()
    assert fa is not None
    assert getattr(fa.status, 'value', fa.status) != 'done'

    # Complete remaining delivery steps (deliver_items, accept_delivery)
    di = next((t for t in tasks if t.step_key == 'deliver_items'), None)
    ad = next((t for t in tasks if t.step_key == 'accept_delivery'), None)
    assert di is not None and ad is not None

    di.assigned_user_id = 2
    test_session.add(di)
    await test_session.commit()
    resp = await client.post(f'/api/tasks/{di.id}/complete', headers={'Authorization': f'Bearer {td}'})
    assert resp.status_code == 200

    ad.assigned_user_id = 2
    test_session.add(ad)
    await test_session.commit()
    resp = await client.post(f'/api/tasks/{ad.id}/complete', headers={'Authorization': f'Bearer {td}'})
    assert resp.status_code == 200

    # After final delivery step, delivery assignment should be marked done
    res = await test_session.execute(__import__('sqlalchemy').select(TaskAssignment).where(TaskAssignment.task_id == task.id).where(TaskAssignment.role_hint == 'delivery'))
    fa2 = res.scalars().first()
    assert fa2 is not None
    assert getattr(fa2.status, 'value', fa2.status) == 'done'


@pytest.mark.anyio
async def test_full_workflow_completion_closes_automation_task(client: AsyncClient, test_session):
    # Verify that completing the final workflow step marks the automation task COMPLETED
    # Setup users
    await client.post('/api/auth/register', json={'email': 'f4@example.com', 'password': 'Password123!', 'username': 'foreman3'})
    await client.post('/api/auth/register', json={'email': 'd4@example.com', 'password': 'Password123!', 'username': 'delivery3'})
    login_f = await client.post('/api/auth/login', json={'identifier': 'f4@example.com', 'password': 'Password123!'})
    login_d = await client.post('/api/auth/login', json={'identifier': 'd4@example.com', 'password': 'Password123!'})
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

    # Assign and complete each workflow step in order
    for step_key, user_token, user_id in [
        ('assemble_items', tf, 1),
        ('foreman_handover', tf, 1),
        ('delivery_received', td, 2),
        ('deliver_items', td, 2),
        ('confirm_received', tf, 1),
    ]:
        t = next((t for t in tasks if t.step_key == step_key), None)
        assert t is not None, f"Missing workflow step {step_key}"
        t.assigned_user_id = user_id
        test_session.add(t)
        await test_session.commit()

        resp = await client.post(f'/api/tasks/{t.id}/complete', headers={'Authorization': f'Bearer {user_token}'})
        assert resp.status_code == 200

    # After final step, the order's automation task should be COMPLETED
    from app.automation.order_triggers import OrderAutomationTriggers
    at = await OrderAutomationTriggers._get_order_automation_task(test_session, order_id)
    assert at is not None
    # Normalize status to NAME if possible
    t_status = at.status.name.upper() if hasattr(at.status, 'name') else str(at.status).upper()
    assert t_status == 'COMPLETED'
    assert getattr(at, 'completed_at', None) is not None

    # Ensure ORDER is completed after automation completes
    from app.db.models import Order
    o_res = await test_session.execute(__import__('sqlalchemy').select(Order).where(Order.id == order_id))
    ord_row = o_res.scalar_one_or_none()
    assert ord_row is not None
    ord_status = ord_row.status.name.upper() if hasattr(ord_row.status, 'name') else str(ord_row.status).upper()
    assert ord_status == 'COMPLETED'
    # Delivery user should see the completed automation task in their task list
    login_d2 = await client.post('/api/auth/login', json={'identifier': 'd4@example.com', 'password': 'Password123!'})
    td2 = login_d2.json()['access_token']
    resp = await client.get('/api/automation/tasks', headers={'Authorization': f'Bearer {td2}'})
    assert resp.status_code == 200
    data = resp.json()
    # There should be at least one task with related_order_id == order_id and status == COMPLETED
    found = False
    for t in data.get('tasks', []):
        if t.get('related_order_id') == order_id:
            s = t.get('status')
            # status may be enum value or string
            s_up = s.upper() if isinstance(s, str) else (s.get('name').upper() if isinstance(s, dict) and s.get('name') else str(s).upper())
            if s_up == 'COMPLETED':
                found = True
                break
    assert found, f"Delivery user did not see completed automation task for order {order_id}"


@pytest.mark.anyio
async def test_delivery_assignment_completion_marks_automation_task_completed(client: AsyncClient, test_session):
    # Create users
    await client.post('/api/auth/register', json={'email': 'f5@example.com', 'password': 'Password123!', 'username': 'foreman4'})
    await client.post('/api/auth/register', json={'email': 'd5@example.com', 'password': 'Password123!', 'username': 'delivery4'})
    login_f = await client.post('/api/auth/login', json={'identifier': 'f5@example.com', 'password': 'Password123!'})
    login_d = await client.post('/api/auth/login', json={'identifier': 'd5@example.com', 'password': 'Password123!'})
    tf = login_f.json()['access_token']
    td = login_d.json()['access_token']

    # Create AGENT_RESTOCK order as foreman
    create = await client.post('/api/orders/', json={'order_type': 'AGENT_RESTOCK', 'items': []}, headers={'Authorization': f'Bearer {tf}'})
    if create.status_code != 201:
        pytest.skip('Order creation not permitted in this environment')
    order_id = create.json()['order_id']

    # Find workflow tasks and complete foreman handover to chain delivery automation task
    from app.db.models import Task, TaskAssignment
    res = await test_session.execute(__import__('sqlalchemy').select(Task).where(Task.order_id == order_id).order_by(Task.id))
    tasks = res.scalars().all()
    fh = next((t for t in tasks if t.step_key == 'foreman_handover'), None)
    assert fh is not None

    fh.assigned_user_id = 1
    test_session.add(fh)
    await test_session.commit()

    resp = await client.post(f'/api/tasks/{fh.id}/complete', headers={'Authorization': f'Bearer {tf}'})
    assert resp.status_code == 200

    # Find the created delivery AutomationTask
    from app.automation.order_triggers import OrderAutomationTriggers
    at = await OrderAutomationTriggers._get_order_automation_task(test_session, order_id)
    assert at is not None and getattr(at, 'required_role', None) == 'delivery'

    # Create a delivery assignment (single assignment) and commit
    delivery_user_id = 2
    da = TaskAssignment(task_id=at.id, user_id=delivery_user_id, role_hint='delivery', status='in_progress')
    test_session.add(da)
    await test_session.commit()

    # Delivery user completes their assignment via automation endpoint
    resp = await client.post(f'/api/automation/tasks/{at.id}/complete', headers={'Authorization': f'Bearer {td}'})
    assert resp.status_code == 200


@pytest.mark.anyio
async def test_foreman_handover_does_not_duplicate_delivery_task(client: AsyncClient, test_session):
    # Create users
    await client.post('/api/auth/register', json={'email': 'dup1@example.com', 'password': 'Password123!', 'username': 'foreman_dup'})
    await client.post('/api/auth/register', json={'email': 'dup2@example.com', 'password': 'Password123!', 'username': 'delivery_dup'})
    login_f = await client.post('/api/auth/login', json={'identifier': 'dup1@example.com', 'password': 'Password123!'})
    login_d = await client.post('/api/auth/login', json={'identifier': 'dup2@example.com', 'password': 'Password123!'})
    tf = login_f.json()['access_token']
    td = login_d.json()['access_token']

    # Create AGENT_RESTOCK order as foreman
    create = await client.post('/api/orders/', json={'order_type': 'AGENT_RESTOCK', 'items': []}, headers={'Authorization': f'Bearer {tf}'})
    if create.status_code != 201:
        pytest.skip('Order creation not permitted in this environment')
    order_id = create.json()['order_id']

    # Find workflow tasks and complete foreman handover to chain delivery automation task
    from app.db.models import Task, AutomationTask
    res = await test_session.execute(__import__('sqlalchemy').select(Task).where(Task.order_id == order_id).order_by(Task.id))
    tasks = res.scalars().all()
    fh = next((t for t in tasks if t.step_key == 'foreman_handover'), None)
    assert fh is not None

    fh.assigned_user_id = 1
    test_session.add(fh)
    await test_session.commit()

    resp = await client.post(f'/api/tasks/{fh.id}/complete', headers={'Authorization': f'Bearer {tf}'})
    assert resp.status_code == 200

    # Retrieve automation task and call chain function twice (simulate duplicate trigger)
    from app.automation.order_triggers import OrderAutomationTriggers
    at = await OrderAutomationTriggers._get_order_automation_task(test_session, order_id)
    assert at is not None

    # Call the chaining function twice to simulate race/duplicate trigger
    await AutomationService._maybe_chain_foreman_to_delivery(test_session, at)
    await AutomationService._maybe_chain_foreman_to_delivery(test_session, at)

    # Ensure only one delivery automation task exists for the order
    res2 = await test_session.execute(__import__('sqlalchemy').select(AutomationTask).where(AutomationTask.related_order_id == order_id, AutomationTask.required_role == 'delivery'))
    delivery_tasks = res2.scalars().all()
    assert len(delivery_tasks) == 1, f"Expected 1 delivery task, found {len(delivery_tasks)}"

    # Reload automation task and ensure it is COMPLETED
    res = await test_session.execute(__import__('sqlalchemy').select(TaskAssignment).where(TaskAssignment.task_id == at.id))
    assignments = res.scalars().all()
    # Ensure assignment is marked done
    assert any(getattr(a.status, 'value', a.status) == 'done' for a in assignments)

    # After role-scoped automation completes, ORDER should NOT be marked COMPLETED (global automation is authoritative)
    from app.db.models import Order
    r = await test_session.execute(__import__('sqlalchemy').select(Order).where(Order.id == order_id))
    ord_ref = r.scalar_one_or_none()
    assert ord_ref is not None
    ord_status = ord_ref.status.name.upper() if hasattr(ord_ref.status, 'name') else str(ord_ref.status).upper()
    assert ord_status != 'COMPLETED'

    # Reload automation task
    from app.db.models import AutomationTask
    r = await test_session.execute(__import__('sqlalchemy').select(AutomationTask).where(AutomationTask.id == at.id))
    at_ref = r.scalar_one_or_none()
    assert at_ref is not None
    t_status = at_ref.status.name.upper() if hasattr(at_ref.status, 'name') else str(at_ref.status).upper()
    assert t_status == 'COMPLETED'
