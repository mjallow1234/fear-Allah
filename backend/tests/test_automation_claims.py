"""Tests for task claiming behavior: race, invalid role, admin override"""
import asyncio
import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.main import app
from app.db.models import AutomationTask, AuditLog, User
from app.db.enums import AutomationTaskType, AutomationTaskStatus
from app.automation.service import AutomationService, ClaimConflictError, ClaimPermissionError


@pytest.mark.anyio
async def test_invalid_role_cannot_claim(async_client_authenticated: tuple[AsyncClient, dict], test_session: AsyncSession):
    client, user_data = async_client_authenticated
    user_id = user_data["user_id"]

    # Create a task and mark it to require 'delivery' role
    create_resp = await client.post(
        "/api/automation/tasks",
        json={"task_type": "retail", "title": "Role restricted task"},
    )
    assert create_resp.status_code == 201
    task_id = create_resp.json()["id"]

    # Update DB to set required_role
    from sqlalchemy import text
    await test_session.execute(
        text("UPDATE automation_tasks SET required_role = :role WHERE id = :id"),
        {"role": "delivery", "id": task_id},
    )
    await test_session.commit()

    # Attempt to claim as regular user
    claim_resp = await client.post(f"/api/automation/tasks/{task_id}/claim", json={})
    assert claim_resp.status_code == 403



@pytest.mark.anyio
async def test_admin_override_claim(test_session: AsyncSession, client: AsyncClient, test_engine):
    # Create a normal user who initially claimed the task
    user = User(email='claimer@example.com', username='claimer', hashed_password='x', is_active=True)
    admin = User(email='admin@example.com', username='admin', hashed_password='x', is_active=True, is_system_admin=True)
    test_session.add_all([user, admin])
    await test_session.commit()
    await test_session.refresh(user)
    await test_session.refresh(admin)

    # Create a task and mark it claimed by `user`
    task = AutomationTask(task_type=AutomationTaskType.retail, status=AutomationTaskStatus.claimed, title='Claimed Task', created_by_id=user.id, claimed_by_user_id=user.id)
    test_session.add(task)
    await test_session.commit()
    await test_session.refresh(task)

    # Admin takes over claim via service layer with override (should not raise)
    await AutomationService.claim_task(db=test_session, task_id=task.id, user_id=admin.id, override=True)

    # Verify claim is now held (attempting to claim as previous claimer should fail)
    from sqlalchemy.ext.asyncio import AsyncSession as _AsyncSession
    from sqlalchemy.orm import sessionmaker
    async_session_factory = sessionmaker(test_engine, class_=_AsyncSession, expire_on_commit=False)
    async with async_session_factory() as s:
        with pytest.raises(ClaimConflictError):
            await AutomationService.claim_task(db=s, task_id=task.id, user_id=user.id, override=False)


@pytest.mark.anyio
async def test_race_condition_two_simultaneous_claims(test_engine, test_session: AsyncSession):
    # Use raw sessions to simulate two concurrent request handlers
    from sqlalchemy.ext.asyncio import AsyncSession as _AsyncSession, create_async_engine
    from sqlalchemy.orm import sessionmaker

    async_session_factory = sessionmaker(test_engine, class_=_AsyncSession, expire_on_commit=False)

    # Create two users
    u1 = User(email='race1@example.com', username='race1', hashed_password='x', is_active=True)
    u2 = User(email='race2@example.com', username='race2', hashed_password='x', is_active=True)
    test_session.add_all([u1, u2])
    await test_session.commit()
    await test_session.refresh(u1)
    await test_session.refresh(u2)

    # Create an OPEN task
    task = AutomationTask(task_type=AutomationTaskType.restock, status=AutomationTaskStatus.open, title='Race Task', created_by_id=u1.id)
    test_session.add(task)
    await test_session.commit()
    await test_session.refresh(task)

    async def attempt_claim(user_id: int):
        async with async_session_factory() as s:
            try:
                t = await AutomationService.claim_task(db=s, task_id=task.id, user_id=user_id)
                return (True, user_id)
            except ClaimConflictError:
                return (False, user_id)

    # Run multiple claim attempts concurrently to increase chance of contention
    tasks = [attempt_claim(uid) for uid in (u1.id, u2.id, u1.id, u2.id, u1.id)]
    res = await asyncio.gather(*tasks)

    successes = [r for r in res if r[0]]
    failures = [r for r in res if not r[0]]

    # At most one should succeed; at least one should fail under contention
    assert len(successes) <= 1
    assert len(failures) >= 1

    # Confirm DB has been updated: if there was a success it should match, otherwise no one claimed
    result = await test_session.execute(select(AutomationTask.claimed_by_user_id).where(AutomationTask.id == task.id))
    claimed_by = result.scalar_one_or_none()
    if len(successes) == 1:
        assert claimed_by == successes[0][1]
    else:
        assert claimed_by is None

@pytest.mark.anyio
async def test_http_claim_endpoint_allows_user_to_claim(async_client_authenticated: tuple[AsyncClient, dict], test_session: AsyncSession):
    client, user_data = async_client_authenticated

    # Create an OPEN task
    create_resp = await client.post("/api/automation/tasks", json={"task_type": "retail", "title": "HTTP Claim Test"})
    assert create_resp.status_code == 201
    task_id = create_resp.json()["id"]

    # Claim via HTTP endpoint
    claim_resp = await client.post(f"/api/automation/tasks/{task_id}/claim", json={})
    assert claim_resp.status_code == 200

    # Verify DB shows claimed_by_user_id is set to our user
    result = await test_session.execute(select(AutomationTask.claimed_by_user_id).where(AutomationTask.id == task_id))
    cid = result.scalar_one_or_none()
    assert cid is not None


@pytest.mark.anyio
async def test_user_with_operational_role_can_claim(test_session: AsyncSession):
    """User who has operational 'foreman' role can claim a task requiring 'foreman'."""
    from app.db.models import User, UserOperationalRole, AutomationTask
    from app.db.enums import AutomationTaskStatus, AutomationTaskType

    # Create user and give operational role
    u = User(email='opuser@example.com', username='opuser', hashed_password='x', is_active=True)
    test_session.add(u)
    await test_session.commit()
    await test_session.refresh(u)

    r = UserOperationalRole(user_id=u.id, role='foreman')
    test_session.add(r)
    await test_session.commit()
    await test_session.refresh(u)  # Ensure relationship is loaded for has_operational_role() check

    # Create an OPEN task requiring foreman
    t = AutomationTask(task_type=AutomationTaskType.restock, status=AutomationTaskStatus.open, title='Op Role Task', created_by_id=u.id, required_role='foreman')
    test_session.add(t)
    await test_session.commit()
    await test_session.refresh(t)

    # Should succeed without raising
    await AutomationService.claim_task(db=test_session, task_id=t.id, user_id=u.id)


@pytest.mark.anyio
async def test_user_without_operational_role_cannot_claim(test_session: AsyncSession):
    """User without operational role cannot claim a task requiring 'foreman'."""
    from app.db.models import User, AutomationTask
    from app.db.enums import AutomationTaskStatus, AutomationTaskType

    u = User(email='noop@example.com', username='noop', hashed_password='x', is_active=True)
    test_session.add(u)
    await test_session.commit()
    await test_session.refresh(u)

    t = AutomationTask(task_type=AutomationTaskType.restock, status=AutomationTaskStatus.open, title='Requires Foreman', created_by_id=u.id, required_role='foreman')
    test_session.add(t)
    await test_session.commit()
    await test_session.refresh(t)

    with pytest.raises(ClaimPermissionError):
        await AutomationService.claim_task(db=test_session, task_id=t.id, user_id=u.id)


@pytest.mark.anyio
async def test_claim_inserts_task_claimed_event(test_session: AsyncSession):
    """Claiming a task should insert a TaskEvent with TaskEventType.task_claimed."""
    from app.db.models import User, UserOperationalRole, AutomationTask, TaskEvent
    from app.db.enums import AutomationTaskStatus, AutomationTaskType, TaskEventType

    # Create user and give operational role
    u = User(email='eventuser@example.com', username='eventuser', hashed_password='x', is_active=True)
    test_session.add(u)
    await test_session.commit()
    await test_session.refresh(u)

    r = UserOperationalRole(user_id=u.id, role='foreman')
    test_session.add(r)
    await test_session.commit()
    await test_session.refresh(u)

    # Create an OPEN task requiring foreman
    t = AutomationTask(task_type=AutomationTaskType.restock, status=AutomationTaskStatus.open, title='Event Task', created_by_id=u.id, required_role='foreman')
    test_session.add(t)
    await test_session.commit()
    await test_session.refresh(t)

    # Claim the task (should not raise)
    await AutomationService.claim_task(db=test_session, task_id=t.id, user_id=u.id)

    # Verify TaskEvent exists with enum member
    res = await test_session.execute(select(TaskEvent).where(TaskEvent.task_id == t.id, TaskEvent.event_type == TaskEventType.task_claimed))
    ev = res.scalar_one_or_none()
    assert ev is not None, "Expected a TaskEvent of type task_claimed to be created on claim"
