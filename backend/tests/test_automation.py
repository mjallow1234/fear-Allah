"""
Tests for Automation Engine (Phase 6.1)
Tests task lifecycle: create → assign → complete → auto-close
"""
import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession

from app.main import app
from app.db.enums import AutomationTaskType, AutomationTaskStatus, AssignmentStatus




@pytest.mark.anyio
async def test_automation_task_lifecycle(
    async_client_authenticated: tuple[AsyncClient, dict],
):
    """Test full task lifecycle: create → assign → complete → auto-close"""
    client, user_data = async_client_authenticated
    user_id = user_data["user_id"]
    
    # 1. Create a task
    create_resp = await client.post(
        "/api/automation/tasks",
        json={
            "task_type": "RESTOCK",
            "title": "Test Restock Task",
            "description": "Test task for automation engine",
        },
    )
    assert create_resp.status_code == 201, f"Create failed: {create_resp.text}"
    task_data = create_resp.json()
    task_id = task_data["id"]
    
    assert task_data["title"] == "Test Restock Task"
    assert task_data["task_type"] == "RESTOCK"
    assert task_data["status"].upper() == "PENDING"
    assert task_data["created_by_id"] == user_id
    
    # 2. Get the task
    get_resp = await client.get(f"/api/automation/tasks/{task_id}")
    assert get_resp.status_code == 200
    assert get_resp.json()["id"] == task_id
    
    # 3. Assign current user to the task
    assign_resp = await client.post(
        f"/api/automation/tasks/{task_id}/assign",
        json={
            "user_id": user_id,
            "role_hint": "tester",
        },
    )
    assert assign_resp.status_code == 201, f"Assign failed: {assign_resp.text}"
    assignment = assign_resp.json()
    assert assignment["user_id"] == user_id
    assert assignment["role_hint"] == "tester"
    assert assignment["status"].upper() == "PENDING"
    
    # 4. Verify task is now in_progress
    get_resp2 = await client.get(f"/api/automation/tasks/{task_id}")
    assert get_resp2.json()["status"].upper() == "IN_PROGRESS"
    
    # 5. Complete the assignment
    complete_resp = await client.post(
        f"/api/automation/tasks/{task_id}/complete",
        json={"notes": "Task completed successfully"},
    )
    assert complete_resp.status_code == 200, f"Complete failed: {complete_resp.text}"
    completed_assignment = complete_resp.json()
    assert completed_assignment["status"].upper() == "DONE"
    assert completed_assignment["notes"] == "Task completed successfully"

    # 6. Verify task not auto-closed (assignment completion should not close the task)
    get_resp3 = await client.get(f"/api/automation/tasks/{task_id}")
    assert get_resp3.json()["status"].upper() == "IN_PROGRESS"
    
    # 7. Get events (audit trail)
    events_resp = await client.get(f"/api/automation/tasks/{task_id}/events")
    assert events_resp.status_code == 200
    events = events_resp.json()
    # At least: created, assigned, step_completed
    assert len(events) >= 3
    
    event_types = [e["event_type"] for e in events]
    event_types_upper = [et.upper() for et in event_types]
    assert "CREATED" in event_types_upper
    assert "ASSIGNED" in event_types_upper
    assert "STEP_COMPLETED" in event_types_upper
    assert "CLOSED" not in event_types_upper


@pytest.mark.anyio
async def test_task_marked_completed_when_last_assignment_done(async_client_authenticated: tuple[AsyncClient, dict], test_session: object):
    """When the final assignment is completed, the task should be marked COMPLETED."""
    client, user_data = async_client_authenticated
    user_id = user_data['user_id']

    from app.db.models import User, TaskAssignment
    from app.core.security import get_password_hash
    from sqlalchemy import select

    # Create two users
    u1 = User(username='final_u1', email='fu1@example.com', hashed_password=get_password_hash('pw'), is_active=True)
    u2 = User(username='final_u2', email='fu2@example.com', hashed_password=get_password_hash('pw'), is_active=True)
    test_session.add_all([u1, u2])
    await test_session.commit()
    await test_session.refresh(u1)
    await test_session.refresh(u2)

    # Create a task
    create_resp = await client.post('/api/automation/tasks', json={'task_type': 'CUSTOM', 'title': 'final assignment test'})
    assert create_resp.status_code == 201
    task_id = create_resp.json()['id']

    # Assign both users
    a1 = await client.post(f'/api/automation/tasks/{task_id}/assign', json={'user_id': u1.id})
    assert a1.status_code == 201
    a2 = await client.post(f'/api/automation/tasks/{task_id}/assign', json={'user_id': u2.id})
    assert a2.status_code == 201

    # Login as u1 and complete their assignment
    login1 = await client.post('/api/auth/login', json={'identifier': 'fu1@example.com', 'password': 'pw'})
    token1 = login1.json()['access_token']
    resp1 = await client.post(f'/api/automation/tasks/{task_id}/complete', json={'notes': 'done1'}, headers={'Authorization': f'Bearer {token1}'})
    assert resp1.status_code == 200

    # Task should NOT yet be completed
    t_resp = await client.get(f'/api/automation/tasks/{task_id}')
    assert t_resp.status_code == 200
    assert t_resp.json()['status'].upper() != 'COMPLETED'

    # Login as u2 and complete their assignment
    login2 = await client.post('/api/auth/login', json={'identifier': 'fu2@example.com', 'password': 'pw'})
    token2 = login2.json()['access_token']
    resp2 = await client.post(f'/api/automation/tasks/{task_id}/complete', json={'notes': 'done2'}, headers={'Authorization': f'Bearer {token2}'})
    assert resp2.status_code == 200

    # Now the task should NOT be auto-completed (assignment completion does not close automation)
    t_resp2 = await client.get(f'/api/automation/tasks/{task_id}')
    assert t_resp2.status_code == 200
    assert t_resp2.json()['status'].upper() != 'COMPLETED'

    create_resp = await client.post(
        "/api/automation/tasks",
        json={
            "task_type": "RETAIL",
            "title": "My Assignment Test",
        },
    )
    assert create_resp.status_code == 201
    task_id = create_resp.json()["id"]
    
    assign_resp = await client.post(
        f"/api/automation/tasks/{task_id}/assign",
        json={"user_id": user_id},
    )
    assert assign_resp.status_code == 201
    
    # Get my assignments
    my_resp = await client.get("/api/automation/my-assignments")
    assert my_resp.status_code == 200
    assignments = my_resp.json()
    assert len(assignments) >= 1
    
    # Find our assignment
    our_assignment = next((a for a in assignments if a["task_id"] == task_id), None)
    assert our_assignment is not None


@pytest.mark.anyio
async def test_cancel_task(
    async_client_authenticated: tuple[AsyncClient, dict],
):
    """Test cancelling a task."""
    client, _ = async_client_authenticated
    
    # Create a task
    create_resp = await client.post(
        "/api/automation/tasks",
        json={
            "task_type": "CUSTOM",
            "title": "Task to Cancel",
        },
    )
    assert create_resp.status_code == 201
    task_id = create_resp.json()["id"]
    
    # Cancel it
    cancel_resp = await client.post(f"/api/automation/tasks/{task_id}/cancel")
    assert cancel_resp.status_code == 200
    assert cancel_resp.json()["status"].upper() == "CANCELLED"


@pytest.mark.anyio
async def test_cannot_complete_unassigned_task(
    async_client_authenticated: tuple[AsyncClient, dict],
):
    """Test that unassigned user cannot complete a task."""
    client, _ = async_client_authenticated
    
    # Create a task but don't assign
    create_resp = await client.post(
        "/api/automation/tasks",
        json={
            "task_type": "CUSTOM",
            "title": "Unassigned Task",
        },
    )
    assert create_resp.status_code == 201
    task_id = create_resp.json()["id"]
    
    # Try to complete without being assigned
    complete_resp = await client.post(
        f"/api/automation/tasks/{task_id}/complete",
        json={},
    )
    assert complete_resp.status_code == 404  # Not found because not assigned


@pytest.mark.anyio
async def test_available_tasks_endpoint(
    async_client_authenticated: tuple[AsyncClient, dict],
    test_session: object,
):
    """Test the available-tasks endpoint for role-based queues."""
    client, _ = async_client_authenticated

    # Create a task requiring foreman
    create_resp = await client.post(
        "/api/automation/tasks",
        json={
            "task_type": "RESTOCK",
            "title": "Available Task",
            "required_role": "foreman",
        },
    )
    assert create_resp.status_code == 201
    task = create_resp.json()
    task_id = task["id"]

    # It should appear in available tasks for role=foreman
    avail_resp = await client.get('/api/automation/available-tasks', params={'role': 'foreman'})
    assert avail_resp.status_code == 200
    data = avail_resp.json()
    tasks = data.get('tasks', [])
    assert any(t['id'] == task_id for t in tasks), f"Task {task_id} not found in available tasks: {tasks}"

    # Ensure no placeholder assignments for operational roles were created on task creation
    get_task = await client.get(f"/api/automation/tasks/{task_id}")
    assert get_task.status_code == 200
    assignments = get_task.json().get('assignments', [])
    roles = set(a.get('role_hint') for a in assignments if a.get('role_hint'))
    assert 'foreman' not in roles and 'delivery' not in roles, f"Operational assignments unexpectedly present: {roles}"

    # Register and login as a foreman user and claim the task
    await client.post('/api/auth/register', json={'email': 'foreman_test@example.com', 'password': 'Password123!', 'username': 'foreman_test'})
    login = await client.post('/api/auth/login', json={'identifier': 'foreman_test@example.com', 'password': 'Password123!'})
    assert login.status_code == 200
    foreman_token = login.json().get('access_token')

    # Ensure user has role 'foreman' in DB so they can claim
    from sqlalchemy import update
    from app.db.models import User
    await test_session.execute(update(User).where(User.username == 'foreman_test').values(role='foreman', is_active=True))
    await test_session.commit()

    # Save original authorization header and set new token
    orig_auth = client.headers.get('Authorization')
    client.headers.update({'Authorization': f'Bearer {foreman_token}'})

    claim_resp = await client.post(f"/api/automation/tasks/{task_id}/claim", json={})
    assert claim_resp.status_code == 200

    # As the foreman, my-assignments should include this task and assignment should be created
    my_assign_resp = await client.get('/api/automation/my-assignments')
    assert my_assign_resp.status_code == 200
    my_assignments = my_assign_resp.json()
    assert any(a.get('task_id') == task_id and a.get('role_hint') == 'foreman' for a in my_assignments), f"Claim did not create assignment for claimer: {my_assignments}"

    # Restore original user and check available tasks again
    if orig_auth:
        client.headers.update({'Authorization': orig_auth})
    else:
        client.headers.pop('Authorization', None)

    avail_resp2 = await client.get('/api/automation/available-tasks', params={'role': 'foreman'})
    assert avail_resp2.status_code == 200
    data2 = avail_resp2.json()
    tasks2 = data2.get('tasks', [])
    assert not any(t['id'] == task_id for t in tasks2), f"Task {task_id} still appeared in available tasks after claim"


@pytest.mark.anyio
async def test_my_assignments_admin_returns_200(async_client_authenticated: tuple[AsyncClient, dict], test_session: object):
    """Admin GET /my-assignments should return 200 (fix NameError import bug)."""
    client, _ = async_client_authenticated

    from app.db.models import User
    from app.core.security import get_password_hash

    admin = User(username='my_assign_admin', email='my_assign_admin@example.com', hashed_password=get_password_hash('pw'), is_active=True, is_system_admin=True)
    test_session.add(admin)
    await test_session.commit()
    await test_session.refresh(admin)

    login = await client.post('/api/auth/login', json={'identifier': 'my_assign_admin', 'password': 'pw'})
    token = login.json()['access_token']

    resp = await client.get('/api/automation/my-assignments', headers={'Authorization': f'Bearer {token}'})
    assert resp.status_code == 200
    # Should be a list
    assert isinstance(resp.json(), list)


@pytest.mark.anyio
async def test_admin_force_complete_task_with_no_assignments(async_client_authenticated: tuple[AsyncClient, dict], test_session: object):
    """System admin should be able to force-complete a task even when no assignments exist."""
    client, _ = async_client_authenticated

    from app.db.models import User
    from app.core.security import get_password_hash

    # Create a task with no assignments
    create = await client.post('/api/automation/tasks', json={'task_type': 'custom', 'title': 'no assignments'})
    assert create.status_code == 201
    task_id = create.json()['id']

    # Create admin and login
    admin = User(username='force_no_assign_admin', email='fna@example.com', hashed_password=get_password_hash('pw'), is_active=True, is_system_admin=True)
    test_session.add(admin)
    await test_session.commit()
    await test_session.refresh(admin)

    login = await client.post('/api/auth/login', json={'identifier': 'force_no_assign_admin', 'password': 'pw'})
    token = login.json()['access_token']

    # Admin posts to complete with empty body
    res = await client.post(f'/api/automation/tasks/{task_id}/complete', json={}, headers={'Authorization': f'Bearer {token}'})
    assert res.status_code == 200

    # Verify task status is COMPLETED
    t_resp = await client.get(f'/api/automation/tasks/{task_id}')
    assert t_resp.status_code == 200
    assert t_resp.json()['status'].upper() == 'COMPLETED'
