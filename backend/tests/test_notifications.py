"""
Phase 6.4 - Notification Engine Tests
Tests for notification creation, delivery, and automation hooks.
"""
import pytest
import json
from datetime import datetime
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession

from app.main import app
from app.db.database import async_session
from app.db.models import User, Notification
from app.db.enums import NotificationType, UserRole
from app.services.notifications import (
    NotificationService,
    notify_task_assigned,
    notify_task_completed,
    notify_low_stock,
)
from app.services.notification_emitter import (
    create_and_emit_notification,
    notify_and_emit_task_assigned,
)


# ============================================================
# Fixtures
# ============================================================

@pytest.fixture
async def db_session():
    """Provide a database session for tests."""
    async with async_session() as session:
        yield session


@pytest.fixture
async def test_users(db_session: AsyncSession):
    """Create test users for notification tests."""
    from sqlalchemy import select
    
    # Check if test users exist
    result = await db_session.execute(
        select(User).where(User.username == "notif_test_user")
    )
    user = result.scalar_one_or_none()
    
    if not user:
        user = User(
            username="notif_test_user",
            email="notif_test@example.com",
            password_hash="test_hash",
            role=UserRole.member,
            is_active=True,
        )
        db_session.add(user)
        await db_session.commit()
        await db_session.refresh(user)
    
    # Create admin user
    result = await db_session.execute(
        select(User).where(User.username == "notif_admin_user")
    )
    admin = result.scalar_one_or_none()
    
    if not admin:
        admin = User(
            username="notif_admin_user",
            email="notif_admin@example.com",
            password_hash="test_hash",
            role=UserRole.admin,
            is_system_admin=True,
            is_active=True,
        )
        db_session.add(admin)
        await db_session.commit()
        await db_session.refresh(admin)
    
    return {"user": user, "admin": admin}


# ============================================================
# NotificationService Tests
# ============================================================

@pytest.mark.asyncio
async def test_create_notification(db_session: AsyncSession, test_users):
    """Test creating a basic notification."""
    user = test_users["user"]
    
    service = NotificationService(db_session)
    notification = await service.create_notification(
        user_id=user.id,
        notification_type=NotificationType.system,
        title="Test Notification",
        content="This is a test notification",
    )
    
    assert notification.id is not None
    assert notification.user_id == user.id
    assert notification.type == NotificationType.system
    assert notification.title == "Test Notification"
    assert notification.is_read is False


@pytest.mark.asyncio
async def test_create_notification_with_automation_context(db_session: AsyncSession, test_users):
    """Test creating notification with automation context fields."""
    user = test_users["user"]
    
    service = NotificationService(db_session)
    notification = await service.create_notification(
        user_id=user.id,
        notification_type=NotificationType.task_assigned,
        title="Task Assigned",
        content="You have a new task",
        task_id=123,
        metadata={"priority": "high"},
    )
    
    assert notification.id is not None
    assert notification.task_id == 123
    assert notification.metadata is not None
    assert "priority" in notification.metadata


@pytest.mark.asyncio
async def test_list_notifications(db_session: AsyncSession, test_users):
    """Test listing notifications for a user."""
    user = test_users["user"]
    
    service = NotificationService(db_session)
    
    # Create a few notifications
    for i in range(3):
        await service.create_notification(
            user_id=user.id,
            notification_type=NotificationType.system,
            title=f"Test Notification {i}",
        )
    
    # List notifications
    notifications = await service.list_notifications(user.id)
    
    assert len(notifications) >= 3


@pytest.mark.asyncio
async def test_unread_count(db_session: AsyncSession, test_users):
    """Test getting unread notification count."""
    user = test_users["user"]
    
    service = NotificationService(db_session)
    
    # Get initial count
    initial_count = await service.get_unread_count(user.id)
    
    # Create new notification
    await service.create_notification(
        user_id=user.id,
        notification_type=NotificationType.system,
        title="New Notification",
    )
    
    # Count should increase
    new_count = await service.get_unread_count(user.id)
    assert new_count == initial_count + 1


@pytest.mark.asyncio
async def test_mark_as_read(db_session: AsyncSession, test_users):
    """Test marking a notification as read."""
    user = test_users["user"]
    
    service = NotificationService(db_session)
    
    # Create notification
    notification = await service.create_notification(
        user_id=user.id,
        notification_type=NotificationType.system,
        title="Test Read",
    )
    
    assert notification.is_read is False
    
    # Mark as read
    success = await service.mark_as_read(notification.id, user.id)
    assert success is True
    
    # Verify
    updated = await service.get_notification(notification.id)
    assert updated.is_read is True


@pytest.mark.asyncio
async def test_mark_all_as_read(db_session: AsyncSession, test_users):
    """Test marking all notifications as read."""
    user = test_users["user"]
    
    service = NotificationService(db_session)
    
    # Create multiple notifications
    for i in range(3):
        await service.create_notification(
            user_id=user.id,
            notification_type=NotificationType.system,
            title=f"Test {i}",
        )
    
    # Mark all as read
    count = await service.mark_all_as_read(user.id)
    assert count >= 3
    
    # Verify unread count is 0
    unread = await service.get_unread_count(user.id)
    assert unread == 0


# ============================================================
# Automation Notification Helper Tests
# ============================================================

@pytest.mark.asyncio
async def test_notify_task_assigned(db_session: AsyncSession, test_users):
    """Test task assignment notification helper."""
    user = test_users["user"]
    
    notification = await notify_task_assigned(
        db=db_session,
        task_id=999,
        assignee_id=user.id,
        task_title="Test Task",
        assigner_name="Admin",
    )
    
    assert notification.id is not None
    assert notification.type == NotificationType.task_assigned
    assert notification.task_id == 999
    assert "Admin" in notification.content


@pytest.mark.asyncio
async def test_notify_task_completed(db_session: AsyncSession, test_users):
    """Test task completed notification helper."""
    user = test_users["user"]
    
    notification = await notify_task_completed(
        db=db_session,
        task_id=999,
        notify_user_id=user.id,
        task_title="Completed Task",
        completed_by="Test User",
    )
    
    assert notification.id is not None
    assert notification.type == NotificationType.task_completed
    assert "Completed Task" in notification.content


@pytest.mark.asyncio
async def test_notify_low_stock(db_session: AsyncSession, test_users):
    """Test low stock notification helper."""
    admin = test_users["admin"]
    
    notification = await notify_low_stock(
        db=db_session,
        inventory_id=1,
        notify_user_id=admin.id,
        product_name="Test Product",
        current_quantity=5,
        reorder_level=10,
    )
    
    assert notification.id is not None
    assert notification.type == NotificationType.low_stock
    assert "Test Product" in notification.content
    assert notification.extra_data is not None
    
    # Parse extra_data
    extra = json.loads(notification.extra_data)
    assert extra["current_quantity"] == 5
    assert extra["reorder_level"] == 10


# ============================================================
# API Endpoint Tests
# ============================================================

@pytest.mark.asyncio
async def test_list_notifications_api(db_session: AsyncSession, test_users):
    """Test notifications API list endpoint."""
    user = test_users["user"]
    
    # Create auth token (simplified - in reality use proper auth)
    from app.core.security import create_access_token
    token = create_access_token({"sub": str(user.id), "username": user.username})
    
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test"
    ) as client:
        response = await client.get(
            "/api/notifications/",
            headers={"Authorization": f"Bearer {token}"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)


@pytest.mark.asyncio
async def test_notification_count_api(db_session: AsyncSession, test_users):
    """Test notifications count endpoint."""
    user = test_users["user"]
    
    from app.core.security import create_access_token
    token = create_access_token({"sub": str(user.id), "username": user.username})
    
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test"
    ) as client:
        response = await client.get(
            "/api/notifications/count",
            headers={"Authorization": f"Bearer {token}"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "unread" in data
        assert "total" in data


@pytest.mark.asyncio
async def test_mark_notification_read_api(db_session: AsyncSession, test_users):
    """Test mark notification as read endpoint."""
    user = test_users["user"]
    
    # Create a notification
    service = NotificationService(db_session)
    notification = await service.create_notification(
        user_id=user.id,
        notification_type=NotificationType.system,
        title="Test Mark Read",
    )
    
    from app.core.security import create_access_token
    token = create_access_token({"sub": str(user.id), "username": user.username})
    
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test"
    ) as client:
        response = await client.post(
            f"/api/notifications/{notification.id}/read",
            headers={"Authorization": f"Bearer {token}"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True


@pytest.mark.asyncio
async def test_mark_all_read_api(db_session: AsyncSession, test_users):
    """Test mark all notifications as read endpoint."""
    user = test_users["user"]
    
    from app.core.security import create_access_token
    token = create_access_token({"sub": str(user.id), "username": user.username})
    
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test"
    ) as client:
        response = await client.post(
            "/api/notifications/read-all",
            headers={"Authorization": f"Bearer {token}"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True


# ============================================================
# Notification Type Coverage Tests
# ============================================================

@pytest.mark.asyncio
async def test_all_notification_types(db_session: AsyncSession, test_users):
    """Test that all automation notification types can be created."""
    user = test_users["user"]
    service = NotificationService(db_session)
    
    automation_types = [
        NotificationType.task_assigned,
        NotificationType.task_completed,
        NotificationType.task_auto_closed,
        NotificationType.order_created,
        NotificationType.order_completed,
        NotificationType.low_stock,
        NotificationType.inventory_restocked,
        NotificationType.sale_recorded,
        NotificationType.system,
    ]
    
    for notif_type in automation_types:
        notification = await service.create_notification(
            user_id=user.id,
            notification_type=notif_type,
            title=f"Test {notif_type.value}",
        )
        assert notification.id is not None
        assert notification.type == notif_type


@pytest.mark.asyncio
async def test_notification_with_all_automation_fields(db_session: AsyncSession, test_users):
    """Test notification with all automation context fields set."""
    user = test_users["user"]
    service = NotificationService(db_session)
    
    notification = await service.create_notification(
        user_id=user.id,
        notification_type=NotificationType.system,
        title="Full Context Test",
        content="Test with all fields",
        task_id=100,
        order_id=200,
        inventory_id=300,
        sale_id=400,
        metadata={"test_key": "test_value"},
    )
    
    assert notification.task_id == 100
    assert notification.order_id == 200
    assert notification.inventory_id == 300
    assert notification.sale_id == 400
    
    # Verify extra_data
    extra = json.loads(notification.extra_data)
    assert extra["test_key"] == "test_value"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
