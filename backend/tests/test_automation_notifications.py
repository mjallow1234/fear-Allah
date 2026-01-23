"""Notification fan-out tests for claimable tasks"""
import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.db.models import User, Notification
from app.db.enums import NotificationType


@pytest.mark.anyio
async def test_notify_on_task_creation(async_client_authenticated: tuple[AsyncClient, dict], test_session):
    client, user = async_client_authenticated
    # Create a delivery role user and an admin
    u_delivery = User(email='dev1@example.com', username='dev1', hashed_password='x', is_active=True, role='delivery')
    admin = User(email='admin1@example.com', username='admin1', hashed_password='x', is_active=True, is_system_admin=True, role='system_admin')
    test_session.add_all([u_delivery, admin])
    await test_session.commit()
    await test_session.refresh(u_delivery)
    await test_session.refresh(admin)

    # Create a task with required_role delivery
    create_resp = await client.post('/api/automation/tasks', json={'task_type': 'restock', 'title': 'Notify Task', 'required_role': 'delivery'})
    assert create_resp.status_code == 201
    task_id = create_resp.json()['id']

    # Check notifications: delivery user and admin should have notifications
    res = await test_session.execute(select(Notification).where(Notification.user_id.in_([u_delivery.id, admin.id])))
    notifs = res.scalars().all()
    assert any(n for n in notifs if n.user_id == u_delivery.id and n.type == NotificationType.task_opened)
    assert any(n for n in notifs if n.user_id == admin.id and n.type == NotificationType.task_opened)


@pytest.mark.anyio
async def test_notify_on_claim(async_client_authenticated: tuple[AsyncClient, dict], test_session):
    client, user = async_client_authenticated
    # Create two delivery users and an admin
    u1 = User(email='u1@example.com', username='u1', hashed_password='x', is_active=True, role='delivery')
    u2 = User(email='u2@example.com', username='u2', hashed_password='x', is_active=True, role='delivery')
    admin = User(email='admin2@example.com', username='admin2', hashed_password='x', is_active=True, is_system_admin=True, role='system_admin')
    test_session.add_all([u1, u2, admin])
    await test_session.commit()
    await test_session.refresh(u1)
    await test_session.refresh(u2)
    await test_session.refresh(admin)

    # Create a task with required_role delivery
    create_resp = await client.post('/api/automation/tasks', json={'task_type': 'restock', 'title': 'Claimable Task', 'required_role': 'delivery'})
    assert create_resp.status_code == 201
    task_id = create_resp.json()['id']

    # Claim as u1
    # Authenticate as u1
    from app.core.security import create_access_token
    token = create_access_token({'sub': str(u1.id), 'username': u1.username})
    client.headers.update({'Authorization': f'Bearer {token}'})

    claim_resp = await client.post(f'/api/automation/tasks/{task_id}/claim', json={})
    assert claim_resp.status_code == 200

    # Other delivery user and admin should receive 'task_claimed' notification
    res = await test_session.execute(select(Notification).where(Notification.user_id.in_([u2.id, admin.id])))
    notifs = res.scalars().all()
    assert any(n for n in notifs if n.user_id == u2.id and n.type == NotificationType.task_claimed)
    assert any(n for n in notifs if n.user_id == admin.id and n.type == NotificationType.task_claimed)


@pytest.mark.anyio
async def test_admin_override_notifications(async_client_authenticated: tuple[AsyncClient, dict], test_session):
    client, user = async_client_authenticated
    # Setup users
    u_prev = User(email='prev@example.com', username='prev', hashed_password='x', is_active=True, role='delivery')
    admin = User(email='admin3@example.com', username='admin3', hashed_password='x', is_active=True, is_system_admin=True, role='system_admin')
    test_session.add_all([u_prev, admin])
    await test_session.commit()
    await test_session.refresh(u_prev)
    await test_session.refresh(admin)

    # Create claimed task (claimed by prev)
    # Using service-level insertion to set claimed_by_user_id directly
    from app.db.models import AutomationTask
    task = AutomationTask(task_type='restock', status='claimed', title='Already Claimed', created_by_id=u_prev.id, claimed_by_user_id=u_prev.id, required_role='delivery')
    test_session.add(task)
    await test_session.commit()
    await test_session.refresh(task)

    # Admin override claim using the authenticated admin token
    from app.core.security import create_access_token
    token = create_access_token({'sub': str(admin.id), 'username': admin.username, 'is_system_admin': True})
    client.headers.update({'Authorization': f'Bearer {token}'})

    override_resp = await client.post(f'/api/automation/tasks/{task.id}/claim', json={'override': True})
    assert override_resp.status_code == 200

    # Verify previous claimer (u_prev) and admin got notifications
    res = await test_session.execute(select(Notification).where(Notification.user_id.in_([u_prev.id, admin.id])))
    notifs = res.scalars().all()
    assert any(n for n in notifs if n.user_id == u_prev.id and n.type == NotificationType.task_claimed)
    assert any(n for n in notifs if n.user_id == admin.id and n.type == NotificationType.task_claimed)
