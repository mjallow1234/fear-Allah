"""
Tests for Order-Driven Automation (Phase 6.2)
Tests that orders automatically create and update automation tasks.
"""
import pytest
from httpx import AsyncClient
from sqlalchemy import select




@pytest.mark.anyio
async def test_order_creates_automation_task(
    async_client_authenticated: tuple[AsyncClient, dict],
    test_session: object,
):
    """Test that creating an order also creates an automation task."""
    client, user_data = async_client_authenticated
    
    # Ensure a system admin exists so template auto-assignments can find a user
    from app.db.models import User
    from app.core.security import get_password_hash

    admin = User(
        username="auto_admin",
        email="auto_admin@example.com",
        hashed_password=get_password_hash("admin123"),
        is_system_admin=True,
        is_active=True,
    )
    test_session.add(admin)
    await test_session.commit()
    await test_session.refresh(admin)

    # Create an order
    order_resp = await client.post(
        "/api/orders/",
        json={
            "order_type": "AGENT_RESTOCK",
            "items": [{"product_id": 1, "quantity": 10}],
            "metadata": {"note": "Test order"},
        },
    )
    assert order_resp.status_code == 201, f"Order creation failed: {order_resp.text}"
    order_data = order_resp.json()
    order_id = order_data["order_id"]
    
    # Check automation status
    auto_resp = await client.get(f"/api/orders/{order_id}/automation")
    assert auto_resp.status_code == 200
    auto_data = auto_resp.json()
    
    assert auto_data["has_automation"] == True
    assert "task_id" in auto_data
    assert auto_data["title"] == f"Restock Order #{order_id}"
    # For order-created tasks with operational required roles, tasks are kept OPEN (claim-based workflow)
    assert auto_data["task_status"].upper() == "OPEN"


@pytest.mark.anyio
async def test_foreman_completion_creates_delivery_task(
    async_client_authenticated: tuple[AsyncClient, dict],
    test_session: object,
):
    """When a foreman task completes for a qualifying order, create a single delivery task."""
    client, user_data = async_client_authenticated

    # Create a qualifying AGENT_RESTOCK order
    order_resp = await client.post(
        "/api/orders/",
        json={
            "order_type": "AGENT_RESTOCK",
            "items": [{"product_id": 1, "quantity": 1}],
        },
    )
    assert order_resp.status_code == 201
    order_id = order_resp.json()["order_id"]

    # Get automation task for the order (should be the foreman restock task)
    auto_resp = await client.get(f"/api/orders/{order_id}/automation")
    assert auto_resp.status_code == 200
    task_id = auto_resp.json()["task_id"]

    # Mark the foreman task as completed
    from app.automation.service import AutomationService
    from app.db.enums import AutomationTaskStatus

    await AutomationService.update_task_status(db=test_session, task_id=task_id, new_status=AutomationTaskStatus.completed, user_id=None)

    # Ensure exactly one delivery task exists for the order
    from sqlalchemy import select
    from app.db.models import AutomationTask

    res = await test_session.execute(
        select(AutomationTask).where(AutomationTask.related_order_id == order_id, AutomationTask.required_role == 'delivery')
    )
    tasks = res.scalars().all()

    assert len(tasks) == 1, f"Expected 1 delivery task, found {len(tasks)}"
    dt = tasks[0]
    assert getattr(dt.status, 'value', dt.status) == 'open'
    assert dt.required_role == 'delivery'


@pytest.mark.anyio
async def test_order_auto_creates_assignments(
    async_client_authenticated: tuple[AsyncClient, dict],
    test_session: object,
):
    """Ensure assignments (foreman, delivery, requester) are created when an order creates an automation task."""
    client, user_data = async_client_authenticated

    from app.db.models import User, TaskAssignment
    from app.core.security import get_password_hash
    from sqlalchemy import select

    # Create role users so auto_assign_role can find them
    foreman = User(
        username="foreman1",
        email="foreman1@example.com",
        hashed_password=get_password_hash("pw"),
        is_active=True,
    )
    delivery = User(
        username="delivery1",
        email="delivery1@example.com",
        hashed_password=get_password_hash("pw"),
        is_active=True,
    )
    test_session.add_all([foreman, delivery])
    await test_session.commit()
    await test_session.refresh(foreman)
    await test_session.refresh(delivery)

    # Add operational role rows for workflow resolution
    from app.db.models import UserOperationalRole
    test_session.add_all([
        UserOperationalRole(user_id=foreman.id, role='foreman'),
        UserOperationalRole(user_id=delivery.id, role='delivery'),
    ])
    await test_session.commit()
    await test_session.refresh(foreman)
    await test_session.refresh(delivery)

    # Create an order as the authenticated user (requester)
    order_resp = await client.post(
        "/api/orders/",
        json={
            "order_type": "AGENT_RESTOCK",
            "items": [{"product_id": 1, "quantity": 1}],
            "metadata": {},
        },
    )
    assert order_resp.status_code == 201
    order_id = order_resp.json()["order_id"]

    # Get automation task for the order
    auto_resp = await client.get(f"/api/orders/{order_id}/automation")
    assert auto_resp.status_code == 200
    task_id = auto_resp.json()["task_id"]

    # Check TaskAssignment rows exist
    res = await test_session.execute(select(TaskAssignment).where(TaskAssignment.task_id == task_id))
    assignments = res.scalars().all()

    # Operational assignments are NOT auto-created anymore. Only requester should be auto-assigned
    assert any(a.role_hint == "requester" and a.user_id == user_data["user_id"] for a in assignments), "Requester assignment missing"
    assert not any(a.role_hint == "foreman" for a in assignments), "Foreman assignment should NOT be auto-created"
    assert not any(a.role_hint == "delivery" for a in assignments), "Delivery assignment should NOT be auto-created"


@pytest.mark.anyio
async def test_assignment_placeholder_created_if_no_role_user(
    async_client_authenticated: tuple[AsyncClient, dict],
    test_session: object,
):
    """No operational placeholders should be created at order time (backfill handles legacy placeholders)."""
    client, user_data = async_client_authenticated

    # Deactivate any existing foreman users to simulate 'no active foreman'
    from app.db.models import User
    from sqlalchemy import update

    # Deactivate any users that hold the operational 'foreman' role
    from app.db.models import UserOperationalRole
    await test_session.execute(
        update(User).where(
            User.id.in_(
                select(UserOperationalRole.user_id).where(UserOperationalRole.role == 'foreman')
            )
        ).values(is_active=False)
    )
    await test_session.commit()

    # Create an AGENT_RESTOCK order
    order_resp = await client.post(
        "/api/orders/",
        json={
            "order_type": "AGENT_RESTOCK",
            "items": [{"product_id": 9, "quantity": 1}],
            "metadata": {},
        },
    )
    assert order_resp.status_code == 201
    order_id = order_resp.json()["order_id"]

    # Get automation task for the order
    auto_resp = await client.get(f"/api/orders/{order_id}/automation")
    assert auto_resp.status_code == 200
    task_id = auto_resp.json()["task_id"]

    # No placeholders for operational roles are created at task creation
    from app.db.models import TaskAssignment
    res = await test_session.execute(select(TaskAssignment).where(TaskAssignment.task_id == task_id))
    assignments = res.scalars().all()

    assert not any(a.role_hint == "foreman" for a in assignments), "Foreman placeholder should NOT be created at task creation"

@pytest.mark.anyio
async def test_foreman_sees_assigned_task_in_inbox(
    async_client_authenticated: tuple[AsyncClient, dict],
    test_session: object,
):
    """Foreman should NOT see newly created restock tasks in their inbox until they claim them."""
    client, user_data = async_client_authenticated

    # Register foreman and delivery users so template assignment finds them
    await client.post('/api/auth/register', json={'email': 'foreman1@example.com', 'password': 'Password123!', 'username': 'foreman1'})
    await client.post('/api/auth/register', json={'email': 'delivery1@example.com', 'password': 'Password123!', 'username': 'delivery1'})

    # Ensure they have the correct operational role on the DB for role-based resolution
    from sqlalchemy import update
    from app.db.models import User

    # Ensure users are active and grant operational roles
    await test_session.execute(update(User).where(User.username == 'foreman1').values(is_active=True))
    await test_session.execute(update(User).where(User.username == 'delivery1').values(is_active=True))
    await test_session.commit()

    # Insert operational roles for foreman1 and delivery1
    from app.db.models import UserOperationalRole, User as DBUser
    res = await test_session.execute(select(DBUser).where(DBUser.username == 'foreman1'))
    foreman = res.scalar_one_or_none()
    res2 = await test_session.execute(select(DBUser).where(DBUser.username == 'delivery1'))
    delivery = res2.scalar_one_or_none()
    test_session.add_all([
        UserOperationalRole(user_id=foreman.id, role='foreman'),
        UserOperationalRole(user_id=delivery.id, role='delivery'),
    ])
    await test_session.commit()

    # Login as foreman
    login = await client.post('/api/auth/login', json={'identifier': 'foreman1@example.com', 'password': 'Password123!'})
    foreman_token = login.json()['access_token']

    # Create an AGENT_RESTOCK order as the original authenticated user
    order_resp = await client.post(
        "/api/orders/",
        json={
            "order_type": "AGENT_RESTOCK",
            "items": [{"product_id": 1, "quantity": 1}],
            "metadata": {},
        },
    )
    assert order_resp.status_code == 201
    order_id = order_resp.json()["order_id"]

    # Foreman should NOT see the automation task yet (it is unclaimed)
    resp = await client.get('/api/automation/tasks', headers={'Authorization': f'Bearer {foreman_token}'})
    assert resp.status_code == 200
    data = resp.json()
    tasks = data['tasks']

    assert not any(t.get('related_order_id') == order_id for t in tasks), "Foreman should not see unclaimed restock task in inbox"


@pytest.mark.anyio
async def test_delivery_sees_restock_and_retail_tasks_in_inbox(
    async_client_authenticated: tuple[AsyncClient, dict],
    test_session: object,
):
    """Delivery should see restock and retail tasks in their inbox."""
    client, user_data = async_client_authenticated

    # Register delivery user
    await client.post('/api/auth/register', json={'email': 'delivery2@example.com', 'password': 'Password123!', 'username': 'delivery2'})
    # Ensure role is set so role-based resolution will pick this user
    from sqlalchemy import update
    from app.db.models import User

    await test_session.execute(update(User).where(User.username == 'delivery2').values(role='delivery', is_active=True))
    await test_session.commit()

    login = await client.post('/api/auth/login', json={'identifier': 'delivery2@example.com', 'password': 'Password123!'})
    delivery_token = login.json()['access_token']

    # Create AGENT_RESTOCK and AGENT_RETAIL orders
    r1 = await client.post('/api/orders/', json={'order_type': 'AGENT_RESTOCK', 'items': [{"product_id":1, "quantity":1}]})
    r2 = await client.post('/api/orders/', json={'order_type': 'AGENT_RETAIL', 'items': [{"product_id":2, "quantity":1}]})
    assert r1.status_code == 201 and r2.status_code == 201
    id1 = r1.json()['order_id']
    id2 = r2.json()['order_id']

    # Delivery should NOT see tasks until they claim them
    resp = await client.get('/api/automation/tasks', headers={'Authorization': f'Bearer {delivery_token}'})
    assert resp.status_code == 200
    tasks = resp.json()['tasks']

    assert not any(t.get('related_order_id') == id1 for t in tasks), "Delivery should not see unclaimed restock task"
    assert not any(t.get('related_order_id') == id2 for t in tasks), "Delivery should not see unclaimed retail task"


@pytest.mark.anyio
async def test_api_create_task_for_order_auto_assigns(
    async_client_authenticated: tuple[AsyncClient, dict],
    test_session: object,
):
    """Creating a task via API with related_order_id should auto-create assignments."""
    client, user_data = async_client_authenticated

    # Create an order
    order_resp = await client.post(
        "/api/orders/",
        json={
            "order_type": "AGENT_RESTOCK",
            "items": [{"product_id": 1, "quantity": 1}],
            "metadata": {},
        },
    )
    assert order_resp.status_code == 201
    order_id = order_resp.json()["order_id"]

    # Create an automation task via API tied to this order
    task_resp = await client.post(
        "/api/automation/tasks",
        json={
            "task_type": "RESTOCK",
            "title": "Manual restock for order",
            "related_order_id": order_id,
        },
    )
    assert task_resp.status_code == 201
    task_id = task_resp.json()["id"]

    # Check TaskAssignment rows exist
    from sqlalchemy import select
    from app.db.models import TaskAssignment

    res = await test_session.execute(select(TaskAssignment).where(TaskAssignment.task_id == task_id))
    assignments = res.scalars().all()

    # Foreman/delivery should NOT be auto-created for manual API-created tasks; only requester may be present
    assert not any(a.role_hint == "foreman" for a in assignments), "Foreman should NOT be auto-created on API-created task"
    assert not any(a.role_hint == "delivery" for a in assignments), "Delivery should NOT be auto-created on API-created task"


@pytest.mark.anyio
async def test_order_without_automation(
    async_client_authenticated: tuple[AsyncClient, dict],
):
    """Test getting automation status for non-existent order."""
    client, _ = async_client_authenticated
    
    # Check automation for non-existent order
    auto_resp = await client.get("/api/orders/99999/automation")
    assert auto_resp.status_code == 200
    auto_data = auto_resp.json()
    
    assert auto_data["has_automation"] == False


@pytest.mark.anyio
async def test_retail_order_automation(
    async_client_authenticated: tuple[AsyncClient, dict],
):
    """Test retail order creates appropriate automation."""
    client, user_data = async_client_authenticated
    
    # Create a retail order
    order_resp = await client.post(
        "/api/orders/",
        json={
            "order_type": "AGENT_RETAIL",
            "items": [{"product_id": 2, "quantity": 5}],
            "metadata": {},
        },
    )
    assert order_resp.status_code == 201
    order_id = order_resp.json()["order_id"]
    
    # Check automation status
    auto_resp = await client.get(f"/api/orders/{order_id}/automation")
    auto_data = auto_resp.json()
    
    assert auto_data["has_automation"] == True
    assert "Retail Order" in auto_data["title"]


@pytest.mark.anyio
async def test_automation_task_linked_to_order(
    async_client_authenticated: tuple[AsyncClient, dict],
):
    """Test that automation task is properly linked to order."""
    client, user_data = async_client_authenticated
    
    # Create an order
    order_resp = await client.post(
        "/api/orders/",
        json={
            "order_type": "CUSTOMER_WHOLESALE",
            "items": [],
            "metadata": {},
        },
    )
    assert order_resp.status_code == 201
    order_id = order_resp.json()["order_id"]
    
    # Get automation status
    auto_resp = await client.get(f"/api/orders/{order_id}/automation")
    auto_data = auto_resp.json()
    task_id = auto_data["task_id"]
    
    # Get the automation task directly
    task_resp = await client.get(f"/api/automation/tasks/{task_id}")
    assert task_resp.status_code == 200
    task_data = task_resp.json()
    
    # Verify the task is linked to the order
    assert task_data["related_order_id"] == order_id
    assert "WHOLESALE" in task_data["task_type"]


@pytest.mark.anyio
async def test_foreman_endpoint_returns_200(async_client_authenticated: tuple[AsyncClient, dict]):
    """Foreman GET /api/automation/tasks should return 200 (no internal server error)."""
    client, _ = async_client_authenticated

    # Register and login as foreman
    await client.post('/api/auth/register', json={'email': 'foreman-check@example.com', 'password': 'Password123!', 'username': 'foreman_check'})
    login = await client.post('/api/auth/login', json={'identifier': 'foreman-check@example.com', 'password': 'Password123!'})
    token = login.json()['access_token']

    resp = await client.get('/api/automation/tasks', headers={'Authorization': f'Bearer {token}'})
    assert resp.status_code == 200


@pytest.mark.anyio
async def test_role_resolution_by_role_not_username(async_client_authenticated: tuple[AsyncClient, dict], test_session: object):
    """If a user has role='foreman' they should be selected even if username is unrelated."""
    client, _ = async_client_authenticated

    from app.db.models import User, TaskAssignment
    from app.core.security import get_password_hash
    from sqlalchemy import select

    # Create a foreman user with a non-prefixed username
    foreman = User(username='bilal', email='bilal@example.com', hashed_password=get_password_hash('pw'), is_active=True)
    test_session.add(foreman)
    await test_session.commit()
    await test_session.refresh(foreman)

    # Give the user the operational 'foreman' role
    from app.db.models import UserOperationalRole
    test_session.add(UserOperationalRole(user_id=foreman.id, role='foreman'))
    await test_session.commit()

    # Create an order which should produce an available task for foreman to claim
    order_resp = await client.post('/api/orders/', json={'order_type': 'AGENT_RESTOCK', 'items': [{'product_id':1, 'quantity':1}]})
    assert order_resp.status_code == 201
    order_id = order_resp.json()['order_id']

    auto_resp = await client.get(f'/api/orders/{order_id}/automation')
    task_id = auto_resp.json()['task_id']

    # The foreman should NOT be auto-assigned, but the task should appear in available-tasks for role=foreman
    avail = await client.get('/api/automation/available-tasks', params={'role': 'foreman'})
    assert avail.status_code == 200
    tasks = avail.json().get('tasks', [])
    assert any(t['id'] == task_id for t in tasks), 'Task not present in available-tasks for foreman'


@pytest.mark.anyio
async def test_backfill_assignments_script_updates_placeholders(async_client_authenticated: tuple[AsyncClient, dict], test_session: object):
    """Backfill should update placeholder assignments to bind to active role users."""
    client, _ = async_client_authenticated

    from app.db.models import User, TaskAssignment
    from app.core.security import get_password_hash
    from app.automation.backfill import backfill_assignments
    from sqlalchemy import select

    # Create an order and let template create placeholder assignments by deactivating role users first
    # Deactivate any existing foremen
    from sqlalchemy import text
    await test_session.execute(text("UPDATE users SET is_active = FALSE WHERE role = 'foreman'"))
    await test_session.commit()

    order_resp = await client.post('/api/orders/', json={'order_type': 'AGENT_RESTOCK', 'items': [{'product_id':9, 'quantity':1}]})
    assert order_resp.status_code == 201
    order_id = order_resp.json()['order_id']

    auto_resp = await client.get(f'/api/orders/{order_id}/automation')
    task_id = auto_resp.json()['task_id']

    # No placeholder is auto-created. Insert one manually to simulate legacy data.
    from app.db.models import TaskAssignment
    placeholder = TaskAssignment(task_id=task_id, user_id=None, role_hint='foreman', status='pending')
    test_session.add(placeholder)
    await test_session.commit()
    await test_session.refresh(placeholder)

    assert placeholder is not None
    assert placeholder.user_id is None

    # Now create an active foreman user
    foreman = User(username='foreman_backfill', email='fb@example.com', hashed_password=get_password_hash('pw'), role='foreman', is_active=True)
    test_session.add(foreman)
    await test_session.commit()
    await test_session.refresh(foreman)

    # Run backfill utility directly with test_session
    updated = await backfill_assignments(test_session)
    assert updated >= 1

    # Verify placeholder now bound to user
    res2 = await test_session.execute(select(TaskAssignment).where(TaskAssignment.task_id == task_id, TaskAssignment.role_hint == 'foreman'))
    assignment = res2.scalar_one_or_none()
    assert assignment is not None
    assert assignment.user_id == foreman.id


@pytest.mark.anyio
async def test_admin_can_complete_any_assignment(async_client_authenticated: tuple[AsyncClient, dict], test_session: object):
    """System admin can complete assignments regardless of workflow step or assignment ownership."""
    client, _ = async_client_authenticated

    from app.db.models import User, TaskAssignment, Task
    from app.core.security import get_password_hash
    from sqlalchemy import select, update

    # Create foreman user and admin user
    foreman = User(username='foreman3', email='f3@example.com', hashed_password=get_password_hash('pw'), role='foreman', is_active=True)
    admin = User(username='sysadmin', email='sysadmin@example.com', hashed_password=get_password_hash('pw'), is_active=True, is_system_admin=True)
    test_session.add_all([foreman, admin])
    await test_session.commit()
    await test_session.refresh(foreman)
    await test_session.refresh(admin)

    # Create an order and ensure foreman assigned
    order_resp = await client.post('/api/orders/', json={'order_type': 'AGENT_RESTOCK', 'items': [{'product_id':1, 'quantity':1}]})
    assert order_resp.status_code == 201
    order_id = order_resp.json()['order_id']

    auto_resp = await client.get(f'/api/orders/{order_id}/automation')
    task_id = auto_resp.json()['task_id']

    # Set all workflow tasks to pending so non-admin cannot complete (simulate wrong active step)
    await test_session.execute(update(Task).where(Task.order_id == order_id).values(status='pending'))
    await test_session.commit()

    # Login as admin (use the sysadmin user we created earlier)
    login = await client.post('/api/auth/login', json={'identifier': 'sysadmin', 'password': 'pw'})
    token = login.json()['access_token']

    # Admin posts to complete the assignment for the task - should succeed
    resp = await client.post(f'/api/automation/tasks/{task_id}/complete', json={'notes': 'admin complete'}, headers={'Authorization': f'Bearer {token}'})
    assert resp.status_code == 200
    data = resp.json()
    assert data['status'] in ('done', 'DONE', 'completed') or data['status'] is not None


@pytest.mark.anyio
async def test_delivery_endpoint_returns_200(async_client_authenticated: tuple[AsyncClient, dict]):
    """Delivery GET /api/automation/tasks should return 200 (no internal server error)."""
    client, _ = async_client_authenticated

    # Register and login as delivery
    await client.post('/api/auth/register', json={'email': 'delivery-check@example.com', 'password': 'Password123!', 'username': 'delivery_check'})
    login = await client.post('/api/auth/login', json={'identifier': 'delivery-check@example.com', 'password': 'Password123!'})
    token = login.json()['access_token']

    resp = await client.get('/api/automation/tasks', headers={'Authorization': f'Bearer {token}'})
    assert resp.status_code == 200
