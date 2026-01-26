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
    assert auto_data["task_status"] == "IN_PROGRESS"  # Should be in progress since we have assignments


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
        role="foreman",
        is_active=True,
    )
    delivery = User(
        username="delivery1",
        email="delivery1@example.com",
        hashed_password=get_password_hash("pw"),
        role="delivery",
        is_active=True,
    )
    test_session.add_all([foreman, delivery])
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

    assert any(a.role_hint == "foreman" for a in assignments), "Foreman assignment missing"
    assert any(a.role_hint == "delivery" for a in assignments), "Delivery assignment missing"
    assert any(a.role_hint == "requester" and a.user_id == user_data["user_id"] for a in assignments), "Requester assignment missing"


@pytest.mark.anyio
async def test_assignment_placeholder_created_if_no_role_user(
    async_client_authenticated: tuple[AsyncClient, dict],
    test_session: object,
):
    """If no active role user exists, a placeholder assignment (user_id=None) should be created."""
    client, user_data = async_client_authenticated

    # Deactivate any existing foreman users to simulate 'no active foreman'
    from app.db.models import User
    from sqlalchemy import update

    await test_session.execute(update(User).where(User.role == 'foreman').values(is_active=False))
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

    # Check TaskAssignment rows exist and that foreman assignment has user_id == None
    from app.db.models import TaskAssignment
    res = await test_session.execute(select(TaskAssignment).where(TaskAssignment.task_id == task_id))
    assignments = res.scalars().all()

    assert any(a.role_hint == "foreman" for a in assignments), "Foreman assignment missing"
    assert any(a.role_hint == "foreman" and a.user_id is None for a in assignments), "Foreman placeholder assignment not created"

@pytest.mark.anyio
async def test_foreman_sees_assigned_task_in_inbox(
    async_client_authenticated: tuple[AsyncClient, dict],
):
    """Foreman should see newly created restock tasks in their inbox."""
    client, user_data = async_client_authenticated

    # Register foreman and delivery users so template assignment finds them
    await client.post('/api/auth/register', json={'email': 'foreman1@example.com', 'password': 'Password123!', 'username': 'foreman1'})
    await client.post('/api/auth/register', json={'email': 'delivery1@example.com', 'password': 'Password123!', 'username': 'delivery1'})

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

    # Foreman should see the automation task in their inbox
    resp = await client.get('/api/automation/tasks', headers={'Authorization': f'Bearer {foreman_token}'})
    assert resp.status_code == 200
    data = resp.json()
    tasks = data['tasks']

    assert any(t.get('related_order_id') == order_id for t in tasks), "Foreman does not see assigned restock task in inbox"


@pytest.mark.anyio
async def test_delivery_sees_restock_and_retail_tasks_in_inbox(
    async_client_authenticated: tuple[AsyncClient, dict],
):
    """Delivery should see restock and retail tasks in their inbox."""
    client, user_data = async_client_authenticated

    # Register delivery user
    await client.post('/api/auth/register', json={'email': 'delivery2@example.com', 'password': 'Password123!', 'username': 'delivery2'})
    login = await client.post('/api/auth/login', json={'identifier': 'delivery2@example.com', 'password': 'Password123!'})
    delivery_token = login.json()['access_token']

    # Create AGENT_RESTOCK and AGENT_RETAIL orders
    r1 = await client.post('/api/orders/', json={'order_type': 'AGENT_RESTOCK', 'items': [{"product_id":1, "quantity":1}]})
    r2 = await client.post('/api/orders/', json={'order_type': 'AGENT_RETAIL', 'items': [{"product_id":2, "quantity":1}]})
    assert r1.status_code == 201 and r2.status_code == 201
    id1 = r1.json()['order_id']
    id2 = r2.json()['order_id']

    # Delivery should see tasks for both orders
    resp = await client.get('/api/automation/tasks', headers={'Authorization': f'Bearer {delivery_token}'})
    assert resp.status_code == 200
    tasks = resp.json()['tasks']

    assert any(t.get('related_order_id') == id1 for t in tasks), "Delivery does not see restock task"
    assert any(t.get('related_order_id') == id2 for t in tasks), "Delivery does not see retail task"


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

    assert any(a.role_hint == "foreman" for a in assignments), "Foreman assignment missing on API-created task"
    assert any(a.role_hint == "delivery" for a in assignments), "Delivery assignment missing on API-created task"


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
