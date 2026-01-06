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
    assert task_data["status"] == "PENDING"
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
    assert assignment["status"] == "PENDING"
    
    # 4. Verify task is now in_progress
    get_resp2 = await client.get(f"/api/automation/tasks/{task_id}")
    assert get_resp2.json()["status"] == "IN_PROGRESS"
    
    # 5. Complete the assignment
    complete_resp = await client.post(
        f"/api/automation/tasks/{task_id}/complete",
        json={"notes": "Task completed successfully"},
    )
    assert complete_resp.status_code == 200, f"Complete failed: {complete_resp.text}"
    completed_assignment = complete_resp.json()
    assert completed_assignment["status"] == "DONE"
    assert completed_assignment["notes"] == "Task completed successfully"

    # 6. Verify task auto-closed
    get_resp3 = await client.get(f"/api/automation/tasks/{task_id}")
    assert get_resp3.json()["status"] == "COMPLETED"
    
    # 7. Get events (audit trail)
    events_resp = await client.get(f"/api/automation/tasks/{task_id}/events")
    assert events_resp.status_code == 200
    events = events_resp.json()
    assert len(events) >= 4  # created, assigned, step_completed, closed
    
    event_types = [e["event_type"] for e in events]
    assert "CREATED" in event_types
    assert "ASSIGNED" in event_types
    assert "STEP_COMPLETED" in event_types
    assert "CLOSED" in event_types


@pytest.mark.anyio
async def test_list_my_assignments(
    async_client_authenticated: tuple[AsyncClient, dict],
):
    """Test getting assignments for current user."""
    client, user_data = async_client_authenticated
    user_id = user_data["user_id"]
    
    # Create and assign a task
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
    assert cancel_resp.json()["status"] == "CANCELLED"


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
