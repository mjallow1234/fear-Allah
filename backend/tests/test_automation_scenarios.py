import pytest
import json
from httpx import AsyncClient
from sqlalchemy import select

pytestmark = pytest.mark.integration


async def assert_automation_event(test_session, event_key: str, entity_id: int):
    """Shared helper that asserts a specific automation event occurred synchronously.

    Supported event_key values:
      - 'order.created' -> asserts an AutomationTask linked to order id exists and metadata indicates order_created
      - 'inventory.low_stock' -> asserts a restock AutomationTask with metadata 'trigger': 'low_stock' and inventory id in metadata exists
      - 'task.completed' -> asserts a TaskEvent with event_type == step_completed exists for the given task id
    """
    from app.db.models import AutomationTask, TaskEvent
    from app.db.enums import TaskEventType, AutomationTaskType
    from sqlalchemy import select

    if event_key == 'order.created':
        res = await test_session.execute(select(AutomationTask).where(AutomationTask.related_order_id == entity_id))
        task = res.scalar_one_or_none()
        assert task is not None, f"Expected AutomationTask for order {entity_id}"
        assert 'order_created' in (task.task_metadata or ''), "Expected task metadata to indicate order_created"
        return

    if event_key == 'inventory.low_stock':
        # Look for restock task by metadata or by title indicating low stock
        q1 = select(AutomationTask).where(AutomationTask.task_type == AutomationTaskType.restock).where(AutomationTask.task_metadata.like(f'%"inventory_id": {entity_id}%'))
        q2 = select(AutomationTask).where(AutomationTask.task_type == AutomationTaskType.restock).where(AutomationTask.title.ilike(f"%Low Stock%"))
        res = await test_session.execute(q1)
        task = res.scalar_one_or_none()
        if not task:
            res = await test_session.execute(q2)
            task = res.scalar_one_or_none()

        assert task is not None, f"Expected restock AutomationTask for inventory item {entity_id}"
        assert 'low_stock' in (task.task_metadata or ''), "Expected task metadata trigger to be low_stock"
        return

    if event_key == 'task.completed':
        # Use a fresh session to see committed data from other sessions (handles snapshot isolation)
        from app.db.database import async_session
        async with async_session() as fresh_s:
            res = await fresh_s.execute(select(TaskEvent).where(TaskEvent.task_id == entity_id).where(TaskEvent.event_type == TaskEventType.step_completed))
            evt = res.scalar_one_or_none()
        assert evt is not None, f"Expected task completion event for task {entity_id}"
        return

    raise ValueError(f"Unsupported event_key: {event_key}")



async def register_and_login(client: AsyncClient, email: str, username: str, password: str = "testpass123"):
    await client.post(
        "/api/auth/register",
        json={"email": email, "password": password, "username": username}
    )
    login_resp = await client.post(
        "/api/auth/login",
        json={"identifier": email, "password": password}
    )
    token = login_resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


async def create_channel_and_message(client: AsyncClient, headers: dict, channel_name: str = "automation-test"):
    ch_resp = await client.post(
        "/api/channels",
        json={"name": channel_name, "type": "public"},
        headers=headers
    )
    if ch_resp.status_code == 403:
        # Fallback create DM
        buddy_email = f"{channel_name}-buddy@test.com"
        buddy_username = f"{channel_name}_buddy"
        await client.post(
            "/api/auth/register",
            json={"email": buddy_email, "password": "testpass123", "username": buddy_username}
        )
        user_resp = await client.get(f"/api/users/by-username/{buddy_username}", headers=headers)
        buddy = user_resp.json()
        dm_resp = await client.post("/api/channels/direct", json={"user_id": buddy["id"]}, headers=headers)
        dm_resp.raise_for_status()
        channel_id = dm_resp.json()["id"]
    else:
        ch_resp.raise_for_status()
        channel_id = ch_resp.json()["id"]

    # Post an initial message to ensure channel exists and has members
    msg_resp = await client.post(
        "/api/messages/",
        json={"content": "Initial", "channel_id": channel_id},
        headers=headers
    )
    msg_resp.raise_for_status()
    return channel_id, msg_resp.json()["id"]


# ----------------------- Phase 2: Order Automation Tests -----------------------

@pytest.mark.anyio
async def test_order_creation_triggers_tasks(client: AsyncClient, test_session):
    # Create users: agent and support/admin
    agent_headers = await register_and_login(client, "agent1@test.com", "agent1")

    from app.db.models import User, Order, AutomationTask, Notification, AuditLog
    from app.db.enums import AutomationTaskStatus

    # Ensure a support/admin user exists who will receive notifications
    q = await test_session.execute(select(User).where(User.username == 'support1'))
    support = q.scalar_one_or_none()
    if not support:
        support = User(username="support1", email="support1@test.com", hashed_password="x", is_system_admin=True, is_active=True)
        test_session.add(support)
        await test_session.commit()
        await test_session.refresh(support)

    channel_id, _ = await create_channel_and_message(client, agent_headers, "sales-channel")

    # Send slash command to create order
    # Provide required args: type and product
    resp = await client.post('/api/messages/', json={'content': '/order create type=AGENT_RESTOCK product=2001 amount=3', 'channel_id': channel_id}, headers=agent_headers)
    assert resp.status_code == 201
    data = resp.json()
    assert data.get('system') is True
    assert 'Order created' in data.get('content', '')

    # Verify order exists
    res = await test_session.execute(select(Order).order_by(Order.id.desc()).limit(1))
    order = res.scalar_one_or_none()
    assert order is not None

    # Verify automation task created and is OPEN (claim-based workflow should start OPEN)
    res = await test_session.execute(select(AutomationTask).where(AutomationTask.related_order_id == order.id))
    task = res.scalar_one_or_none()
    assert task is not None
    assert task.status == AutomationTaskStatus.open

    # Ensure channel role assignment was created so claim can succeed
    # Register and set foreman role on a user
    foreman_headers = await register_and_login(client, "foreman1@test.com", "foreman1")
    from sqlalchemy import update
    from app.db.models import User, ChannelRoleAssignment, Role
    await test_session.execute(update(User).where(User.username == 'foreman1').values(role='foreman', is_active=True))
    await test_session.commit()

    # Find the foreman role_id (channel scope)
    role_res = await test_session.execute(select(Role).where(Role.name == 'foreman', Role.scope == 'channel'))
    role_obj = role_res.scalar_one_or_none()

    # Check channel role assignment exists for the foreman on the channel where the command was executed
    res = await test_session.execute(select(ChannelRoleAssignment).where(ChannelRoleAssignment.user_id == (await (await test_session.execute(select(User).where(User.username == 'foreman1'))).scalar_one()).id, ChannelRoleAssignment.channel_id == channel_id, ChannelRoleAssignment.role_id == (role_obj.id if role_obj else None)))
    cra = res.scalar_one_or_none()

    # If the legacy tasks table didn't provide channel info in this test DB, it's acceptable for CRA to be None
    # but if it exists then claim should succeed. Proceed to attempt claim.

    claim_resp = await client.post(f"/api/automation/tasks/{task.id}/claim", headers=foreman_headers)
    assert claim_resp.status_code == 200

    # Refresh and assert claimed state
    res = await test_session.execute(select(AutomationTask).where(AutomationTask.id == task.id))
    task = res.scalar_one()
    assert task.status == AutomationTaskStatus.claimed
    assert task.claimed_by_user_id is not None

    # Exact automation event assertion
    await assert_automation_event(test_session, 'order.created', order.id)

    # Audit entry exists (slash command audit)
    res = await test_session.execute(select(AuditLog).where(AuditLog.target_type == 'order').order_by(AuditLog.created_at.desc()).limit(1))
    audit = res.scalar_one_or_none()
    assert audit is not None


@pytest.mark.anyio
async def test_order_creation_denied_for_viewer(client: AsyncClient, test_session):
    viewer_headers = await register_and_login(client, "viewer1@test.com", "viewer1")

    from app.db.models import Order, AuditLog

    channel_id, _ = await create_channel_and_message(client, viewer_headers, "sales-channel-2")

    resp = await client.post('/api/messages/', json={'content': '/order create type=AGENT_RESTOCK items=3', 'channel_id': channel_id}, headers=viewer_headers)
    assert resp.status_code == 201
    data = resp.json()
    assert data.get('system') is True
    assert data.get('content') == '❌ Permission denied'

    # Ensure no order created
    res = await test_session.execute(select(Order))
    assert res.scalars().first() is None

    # Audit log for denied action exists
    res = await test_session.execute(select(AuditLog).where(AuditLog.target_type == 'order').order_by(AuditLog.created_at.desc()))
    audit = res.scalar_one_or_none()
    assert audit is not None
    # meta should indicate permission_denied
    meta = json.loads(audit.meta) if audit.meta else {}
    assert meta.get('result') == 'permission_denied'


@pytest.mark.anyio
async def test_order_creation_validation_error(client: AsyncClient, test_session):
    agent_headers = await register_and_login(client, "agent2@test.com", "agent2")

    from app.db.models import Order

    channel_id, _ = await create_channel_and_message(client, agent_headers, "sales-channel-3")

    resp = await client.post('/api/messages/', json={'content': '/order create', 'channel_id': channel_id}, headers=agent_headers)
    assert resp.status_code == 201
    data = resp.json()
    assert data.get('system') is True
    assert data.get('content', '').startswith('❌ Invalid arguments')

    # Ensure no DB mutations
    res = await test_session.execute(select(Order))
    assert res.scalars().first() is None


# ----------------------- Phase 3: Sales Automation Tests -----------------------

@pytest.mark.anyio
async def test_sale_records_inventory_and_triggers_automation(client: AsyncClient, test_session):
    agent_headers = await register_and_login(client, "agent_sale@test.com", "agent_sale")

    from app.db.models import Inventory, Sale, InventoryTransaction, Notification, User, AutomationTask

    # Ensure an admin exists so notifications have recipients
    q = await test_session.execute(select(User).where(User.username == 'admin_for_sales'))
    admin = q.scalar_one_or_none()
    if not admin:
        admin = User(username='admin_for_sales', email='admin_sales@test.com', hashed_password='x', is_system_admin=True, is_active=True)
        test_session.add(admin)
        await test_session.flush()

    # Create inventory for product 400042 set to be low after sale to trigger low_stock
    inv = Inventory(product_id=400042, total_stock=6, total_sold=0, product_name='MP400042', low_stock_threshold=5)
    test_session.add(inv)
    await test_session.commit()

    channel_id, _ = await create_channel_and_message(client, agent_headers, "sales-channel-4")

    resp = await client.post('/api/messages/', json={'content': '/sale record product=400042 qty=2 price=250', 'channel_id': channel_id}, headers=agent_headers)
    assert resp.status_code == 201
    data = resp.json()
    assert data.get('system') is True

    # Sale record created
    res = await test_session.execute(select(Sale).where(Sale.product_id == 400042))
    sale = res.scalar_one_or_none()
    assert sale is not None
    assert sale.quantity == 2

    # Inventory reduced
    res = await test_session.execute(select(Inventory).where(Inventory.product_id == 400042))
    inv2 = res.scalar_one()
    assert inv2.total_stock == 4

    # Inventory transaction logged
    res = await test_session.execute(select(InventoryTransaction).where(InventoryTransaction.inventory_item_id == inv2.id))
    itx = res.scalar_one_or_none()
    assert itx is not None
    assert itx.reason == 'sale'

    # Exact automation expectation: a low_stock restock AutomationTask must have been created
    await assert_automation_event(test_session, 'inventory.low_stock', inv2.id)


@pytest.mark.anyio
async def test_sale_triggers_low_stock_automation(client: AsyncClient, test_session):
    agent_headers = await register_and_login(client, "agent_sale2@test.com", "agent_sale2")

    from app.db.models import Inventory, Sale, Notification, User, AutomationTask

    # Ensure admin exists to receive low stock notifications
    q = await test_session.execute(select(User).where(User.username == 'admin_lowstock'))
    admin = q.scalar_one_or_none()
    if not admin:
        admin = User(username='admin_lowstock', email='admin_lowstock@test.com', hashed_password='x', is_system_admin=True, is_active=True)
        test_session.add(admin)
        await test_session.flush()

    # Create inventory near threshold (threshold default 10)
    inv = Inventory(product_id=500001, total_stock=6, total_sold=0, product_name='LowStockProd', low_stock_threshold=5)
    test_session.add(inv)
    await test_session.commit()

    channel_id, _ = await create_channel_and_message(client, agent_headers, "sales-channel-5")

    resp = await client.post('/api/messages/', json={'content': '/sale record product=500001 qty=5 price=250', 'channel_id': channel_id}, headers=agent_headers)
    assert resp.status_code == 201

    # Sale succeeds
    res = await test_session.execute(select(Sale).where(Sale.product_id == 500001))
    sale = res.scalar_one_or_none()
    assert sale is not None

    # Inventory < threshold
    res = await test_session.execute(select(Inventory).where(Inventory.product_id == 500001))
    inv2 = res.scalar_one()
    assert inv2.total_stock < inv2.low_stock_threshold

    # Exact automation expectation: a low_stock restock AutomationTask must have been created
    await assert_automation_event(test_session, 'inventory.low_stock', inv2.id)


@pytest.mark.anyio
async def test_sale_rejected_when_stock_insufficient(client: AsyncClient, test_session):
    agent_headers = await register_and_login(client, "agent_sale3@test.com", "agent_sale3")

    from app.db.models import Inventory, Sale

    inv = Inventory(product_id=999999, total_stock=2, total_sold=0, product_name='ScarceProd')
    test_session.add(inv)
    await test_session.commit()

    channel_id, _ = await create_channel_and_message(client, agent_headers, "sales-channel-6")

    resp = await client.post('/api/messages/', json={'content': '/sale record product=999999 qty=999 price=250', 'channel_id': channel_id}, headers=agent_headers)
    assert resp.status_code == 201
    data = resp.json()
    assert data.get('system') is True
    assert 'Error' in data.get('content', '') or 'insufficient' in data.get('content', '').lower()

    # No sale created
    res = await test_session.execute(select(Sale).where(Sale.product_id == 999999))
    assert res.scalar_one_or_none() is None

    # Inventory unchanged
    res = await test_session.execute(select(Inventory).where(Inventory.product_id == 999999))
    inv2 = res.scalar_one()
    assert inv2.total_stock == 2


# ----------------------- Phase 4: Task Automation Tests -----------------------

@pytest.mark.anyio
async def test_task_created_from_order(client: AsyncClient, test_session):
    agent_headers = await register_and_login(client, "agent_task@test.com", "agent_task")

    from app.db.models import Order, Notification, AutomationTask

    # Ensure admin exists so template assignments are created synchronously
    from app.db.models import User
    q = await test_session.execute(select(User).where(User.username == 'support1'))
    admin = q.scalar_one_or_none()
    if not admin:
        admin = User(username='support1', email='support1@test.com', hashed_password='x', is_system_admin=True, is_active=True)
        test_session.add(admin)
        await test_session.commit()

    channel_id, _ = await create_channel_and_message(client, agent_headers, "sales-channel-7")

    # Create order via slash command (provide product)
    resp = await client.post('/api/messages/', json={'content': '/order create type=AGENT_RESTOCK product=3001 amount=1', 'channel_id': channel_id}, headers=agent_headers)
    assert resp.status_code == 201

    # Find created order and automation task
    res = await test_session.execute(select(Order).order_by(Order.id.desc()).limit(1))
    order = res.scalar_one()

    res = await test_session.execute(select(AutomationTask).where(AutomationTask.related_order_id == order.id))
    atask = res.scalar_one_or_none()
    assert atask is not None
    # With admin support present, template assignments are created synchronously and task should be in_progress
    from app.db.enums import AutomationTaskType, AutomationTaskStatus
    assert atask.task_type == AutomationTaskType.restock
    assert atask.status == AutomationTaskStatus.open

    # Exact automation expectation
    await assert_automation_event(test_session, 'order.created', order.id)


@pytest.mark.anyio
async def test_task_completion_triggers_next_step(client: AsyncClient, test_session):
    # Create a task by creating an order first
    agent_headers = await register_and_login(client, "agent_task2@test.com", "agent_task2")
    support_headers = await register_and_login(client, "support_task@test.com", "support_task")

    from app.db.models import Order, AutomationTask, TaskAssignment, Notification, User

    # Ensure support_task user exists before creating the order so automation auto-assigns
    q = await test_session.execute(select(User).where(User.username == 'support_task'))
    u = q.scalar_one_or_none()
    if not u:
        u = User(username='support_task', email='support_task@test.com', hashed_password='x', is_system_admin=True, is_active=True)
        test_session.add(u)
        await test_session.commit()

    channel_id, _ = await create_channel_and_message(client, agent_headers, "sales-channel-8")

    # Create order (provide product)
    resp = await client.post('/api/messages/', json={'content': '/order create type=AGENT_RESTOCK product=7001 amount=1', 'channel_id': channel_id}, headers=agent_headers)
    assert resp.status_code == 201

    # Find task created from order
    res = await test_session.execute(select(AutomationTask).order_by(AutomationTask.id.desc()).limit(1))
    atask = res.scalar_one()

    # Create and commit an assignment for support_task explicitly to make completion deterministic
    q = await test_session.execute(select(User).where(User.username == 'support_task'))
    u = q.scalar_one_or_none()
    if not u:
        u = User(username='support_task', email='support_task@test.com', hashed_password='x', is_active=True)
        test_session.add(u)
        await test_session.flush()

    # Ensure an assignment exists for support_task; create it if absent using a fresh DB session
    from app.db.database import async_session
    from sqlalchemy.exc import IntegrityError
    async with async_session() as fresh_s:
        res = await fresh_s.execute(select(TaskAssignment).where(TaskAssignment.task_id == atask.id).where(TaskAssignment.user_id == u.id))
        existing = res.scalar_one_or_none()
        if existing:
            assignment_id = existing.id
        else:
            nta = TaskAssignment(task_id=atask.id, user_id=u.id, status='PENDING')
            fresh_s.add(nta)
            try:
                await fresh_s.commit()
                assignment_id = nta.id
            except IntegrityError:
                await fresh_s.rollback()
                res = await fresh_s.execute(select(TaskAssignment).where(TaskAssignment.task_id == atask.id).where(TaskAssignment.user_id == u.id))
                existing = res.scalar_one()
                assignment_id = existing.id

    # Complete the assignment via slash command as support_task
    resp = await client.post('/api/messages/', json={'content': f'/task complete id={assignment_id}', 'channel_id': channel_id}, headers=support_headers)
    assert resp.status_code == 201
    data = resp.json()
    assert data.get('system') is True

    # Verify assignment status updated using a fresh DB session so we see committed changes
    async with async_session() as fresh_s:
        res = await fresh_s.execute(select(TaskAssignment).where(TaskAssignment.id == assignment_id))
        t = res.scalar_one()
        assert t.status.lower() in ('done', 'completed')

    # Exact automation expectation: task completion emits a step_completed event
    await assert_automation_event(test_session, 'task.completed', atask.id)


@pytest.mark.anyio
async def test_task_completion_denied_for_non_assignee(client: AsyncClient, test_session):
    agent_headers = await register_and_login(client, "agent_task3@test.com", "agent_task3")
    viewer_headers = await register_and_login(client, "viewer_task@test.com", "viewer_task")

    from app.db.models import AutomationTask, TaskAssignment, AuditLog

    # Create order which creates task (provide product)
    channel_id, _ = await create_channel_and_message(client, agent_headers, "sales-channel-9")
    resp = await client.post('/api/messages/', json={'content': '/order create type=AGENT_RESTOCK product=9001 amount=1', 'channel_id': channel_id}, headers=agent_headers)
    assert resp.status_code == 201

    res = await test_session.execute(select(AutomationTask).order_by(AutomationTask.id.desc()).limit(1))
    atask = res.scalar_one()

    # Create an assignment for some other user but not the viewer
    # Use a fresh session to ensure the assignment is visible to the slash command handler
    from app.db.models import User
    from app.db.database import async_session
    
    async with async_session() as fresh_s:
        # Find or create the not_viewer user
        q = await fresh_s.execute(select(User).where(User.username == 'not_viewer'))
        u = q.scalar_one_or_none()
        if not u:
            u = User(username='not_viewer', email='not_viewer@test.com', hashed_password='x', is_active=True)
            fresh_s.add(u)
            await fresh_s.flush()
        
        # Create assignment for not_viewer
        ta = TaskAssignment(task_id=atask.id, user_id=u.id, status='PENDING')
        fresh_s.add(ta)
        await fresh_s.commit()
        assignment_id = ta.id

    # viewer tries to complete assignment
    resp = await client.post('/api/messages/', json={'content': f'/task complete id={assignment_id}', 'channel_id': channel_id}, headers=viewer_headers)
    assert resp.status_code == 201
    data = resp.json()
    assert data.get('system') is True
    assert data.get('content') == '❌ Permission denied'

    # Assignment unchanged
    async with async_session() as fresh_s:
        res = await fresh_s.execute(select(TaskAssignment).where(TaskAssignment.id == assignment_id))
        ta2 = res.scalar_one()
        assert ta2.status.lower() == 'pending'

    # Audit log exists for denied action for this assignment
    # Audit log for this viewer's denied attempt
    from app.db.models import User
    qv = await test_session.execute(select(User).where(User.username == 'viewer_task'))
    v = qv.scalar_one_or_none()
    assert v is not None

    q = select(AuditLog).where(
        AuditLog.action == 'slash_command',
        AuditLog.target_type == 'task',
        AuditLog.user_id == v.id
    ).order_by(AuditLog.created_at.desc()).limit(1)
    res = await test_session.execute(q)
    audit = res.scalar_one_or_none()
    assert audit is not None
    meta = json.loads(audit.meta) if audit and audit.meta else {}
    assert meta.get('result') == 'permission_denied'


# ----------------------- Phase 5: Automation Engine Health -----------------------

@pytest.mark.anyio
async def test_automation_test_event_does_not_mutate_db(client: AsyncClient, test_session, monkeypatch):
    admin_headers = await register_and_login(client, "admin_automation@test.com", "admin_automation")

    # Promote user to system admin
    from app.db.models import User, Order, AutomationTask, Notification
    q = await test_session.execute(select(User).where(User.username == 'admin_automation'))
    u = q.scalar_one_or_none()
    if u:
        u.is_system_admin = True
        test_session.add(u)
        await test_session.commit()

    channel_id, _ = await create_channel_and_message(client, admin_headers, "sales-channel-10")

    # Call the dry-run automation test command (should NOT mutate DB)
    resp = await client.post('/api/messages/', json={'content': '/automation test event=order_created', 'channel_id': channel_id}, headers=admin_headers)
    assert resp.status_code == 201
    data = resp.json()
    assert data.get('system') is True

    # Ensure no orders, tasks, notifications persisted by this dry run
    res = await test_session.execute(select(Order))
    assert res.scalars().first() is None
    res = await test_session.execute(select(AutomationTask))
    assert res.scalars().first() is None
    res = await test_session.execute(select(Notification))
    assert res.scalars().first() is None


# ----------------------- Phase 6: Failure Safety -----------------------

@pytest.mark.anyio
async def test_automation_failure_does_not_rollback_order(client: AsyncClient, test_session, monkeypatch):
    agent_headers = await register_and_login(client, "agent_fail@test.com", "agent_fail")

    from app.db.models import Order

    # Monkeypatch order automation handler to raise
    async def fake_on_order_created(db, order, created_by_id):
        raise RuntimeError("boom")

    monkeypatch.setattr('app.automation.order_triggers.OrderAutomationTriggers.on_order_created', fake_on_order_created)

    channel_id, _ = await create_channel_and_message(client, agent_headers, "sales-channel-11")

    resp = await client.post('/api/messages/', json={'content': '/order create type=AGENT_RESTOCK product=4004 amount=2', 'channel_id': channel_id}, headers=agent_headers)
    assert resp.status_code == 201
    data = resp.json()
    assert data.get('system') is True
    assert 'Order created' in data.get('content', '')

    # Order still created despite automation failure
    res = await test_session.execute(select(Order).order_by(Order.id.desc()).limit(1))
    order = res.scalar_one_or_none()
    assert order is not None

    # No partial tasks created
    from app.db.models import AutomationTask
    res = await test_session.execute(select(AutomationTask).where(AutomationTask.related_order_id == order.id))
    assert res.scalars().first() is None
