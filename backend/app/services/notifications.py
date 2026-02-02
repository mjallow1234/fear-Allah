"""
Phase 6.4 - Notification Engine Service Layer
Handles notification creation, delivery via Socket.IO, and management
"""
import json
from typing import Optional, List, Dict, Any
from datetime import datetime
from sqlalchemy import select, update, func, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models import Notification, User
from app.db.enums import NotificationType


class NotificationService:
    """Service for managing notifications"""
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def create_notification(
        self,
        user_id: int,
        notification_type: NotificationType,
        title: str,
        content: Optional[str] = None,
        channel_id: Optional[int] = None,
        message_id: Optional[int] = None,
        sender_id: Optional[int] = None,
        task_id: Optional[int] = None,
        order_id: Optional[int] = None,
        inventory_id: Optional[int] = None,
        sale_id: Optional[int] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Notification:
        """Create a new notification"""
        notification = Notification(
            user_id=user_id,
            type=notification_type,
            title=title,
            content=content,
            channel_id=channel_id,
            message_id=message_id,
            sender_id=sender_id,
            task_id=task_id,
            order_id=order_id,
            inventory_id=inventory_id,
            sale_id=sale_id,
            extra_data=json.dumps(metadata) if metadata else None,
            is_read=False,
        )
        self.db.add(notification)
        await self.db.commit()
        await self.db.refresh(notification)
        return notification
    
    async def get_notification(self, notification_id: int) -> Optional[Notification]:
        """Get a single notification by ID"""
        result = await self.db.execute(
            select(Notification).where(Notification.id == notification_id)
        )
        return result.scalar_one_or_none()
    
    async def list_notifications(
        self,
        user_id: int,
        unread_only: bool = False,
        notification_types: Optional[List[NotificationType]] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[Notification]:
        """List notifications for a user with filters"""
        query = select(Notification).where(Notification.user_id == user_id)
        
        if unread_only:
            query = query.where(Notification.is_read == False)
        
        if notification_types:
            query = query.where(Notification.type.in_(notification_types))
        
        query = query.order_by(Notification.created_at.desc())
        query = query.offset(offset).limit(limit)
        
        result = await self.db.execute(query)
        return list(result.scalars().all())
    
    async def get_unread_count(
        self,
        user_id: int,
        notification_types: Optional[List[NotificationType]] = None,
    ) -> int:
        """Get count of unread notifications"""
        query = select(func.count(Notification.id)).where(
            and_(
                Notification.user_id == user_id,
                Notification.is_read == False,
            )
        )
        
        if notification_types:
            query = query.where(Notification.type.in_(notification_types))
        
        result = await self.db.execute(query)
        return result.scalar() or 0
    
    async def mark_as_read(self, notification_id: int, user_id: int) -> bool:
        """Mark a notification as read"""
        result = await self.db.execute(
            update(Notification)
            .where(
                and_(
                    Notification.id == notification_id,
                    Notification.user_id == user_id,
                )
            )
            .values(is_read=True)
        )
        await self.db.commit()
        return result.rowcount > 0
    
    async def mark_all_as_read(
        self,
        user_id: int,
        notification_types: Optional[List[NotificationType]] = None,
    ) -> int:
        """Mark all notifications as read for a user"""
        query = (
            update(Notification)
            .where(
                and_(
                    Notification.user_id == user_id,
                    Notification.is_read == False,
                )
            )
            .values(is_read=True)
        )
        
        if notification_types:
            query = query.where(Notification.type.in_(notification_types))
        
        result = await self.db.execute(query)
        await self.db.commit()
        return result.rowcount
    
    async def delete_notification(self, notification_id: int, user_id: int) -> bool:
        """Delete a notification"""
        notification = await self.get_notification(notification_id)
        if notification and notification.user_id == user_id:
            await self.db.delete(notification)
            await self.db.commit()
            return True
        return False


# ---------------- Automation Notification Helpers ----------------

async def notify_task_assigned(
    db: AsyncSession,
    task_id: int,
    assignee_id: int,
    task_title: str,
    assigner_name: Optional[str] = None,
) -> Notification:
    """Create notification when task is assigned"""
    service = NotificationService(db)
    content = f"You have been assigned a new task: {task_title}"
    if assigner_name:
        content = f"{assigner_name} assigned you a task: {task_title}"
    
    return await service.create_notification(
        user_id=assignee_id,
        notification_type=NotificationType.task_assigned,
        title="Task Assigned",
        content=content,
        task_id=task_id,
    )


async def notify_task_opened(
    db: AsyncSession,
    task_id: int,
    task_title: str,
    required_role: str,
) -> list[Notification]:
    """Notify all users with `required_role` and admins that a task is available."""
    # Get users with the role
    from app.db.models import User
    result = await db.execute(select(User.id).where(User.role == required_role, User.is_active == True))
    role_user_ids = [r[0] for r in result.fetchall()]

    # Admins/managers
    admin_ids = await get_admins_and_managers(db)

    # Deduplicate and exclude empty
    recipients = list(dict.fromkeys([uid for uid in (role_user_ids + admin_ids) if uid is not None]))

    title = "Task Available"
    content = f"Task '{task_title}' is available for role: {required_role}"

    return await notify_users(db, recipients, NotificationType.task_opened, title=title, content=content, task_id=task_id)


async def notify_task_claimed(
    db: AsyncSession,
    task_id: int,
    task_title: str,
    claimer_id: int,
    required_role: Optional[str] = None,
) -> list[Notification]:
    """Notify other role members and admins that a task was claimed."""
    from app.db.models import User
    recipients = set()

    if required_role:
        res = await db.execute(select(User.id).where(User.role == required_role, User.is_active == True))
        recipients.update(r[0] for r in res.fetchall())

    # Admins
    admin_ids = await get_admins_and_managers(db)
    recipients.update(admin_ids)

    # Remove the claimer itself
    recipients.discard(claimer_id)

    title = "Task Claimed"
    content = f"Task '{task_title}' was claimed by user {claimer_id}"

    return await notify_users(db, list(recipients), NotificationType.task_claimed, title=title, content=content, task_id=task_id)


async def notify_task_reassigned(
    db: AsyncSession,
    task_id: int,
    task_title: str,
    from_user_id: Optional[int],
    to_user_id: int,
) -> list[Notification]:
    """Notify previous claimer (if present), the new assignee, and admins on reassignment."""
    recipients = []
    if from_user_id:
        recipients.append(from_user_id)
    recipients.append(to_user_id)
    admin_ids = await get_admins_and_managers(db)
    recipients.extend(admin_ids)

    # Deduplicate
    recipients = list(dict.fromkeys(recipients))

    title = "Task Reassigned"
    content = f"Task '{task_title}' was reassigned from {from_user_id} to {to_user_id}"

    return await notify_users(db, recipients, NotificationType.task_claimed, title=title, content=content, task_id=task_id)


async def notify_task_completed(
    db: AsyncSession,
    task_id: int,
    notify_user_id: int,
    task_title: str,
    completed_by: Optional[str] = None,
) -> Notification:
    """Create notification when task is completed"""
    service = NotificationService(db)
    content = f"Task completed: {task_title}"
    if completed_by:
        content = f"{completed_by} completed the task: {task_title}"
    
    return await service.create_notification(
        user_id=notify_user_id,
        notification_type=NotificationType.task_completed,
        title="Task Completed",
        content=content,
        task_id=task_id,
    )


async def notify_task_auto_closed(
    db: AsyncSession,
    task_id: int,
    notify_user_id: int,
    task_title: str,
    reason: str = "auto-closed due to inactivity",
) -> Notification:
    """Create notification when task is auto-closed"""
    service = NotificationService(db)
    return await service.create_notification(
        user_id=notify_user_id,
        notification_type=NotificationType.task_auto_closed,
        title="Task Auto-Closed",
        content=f"Task '{task_title}' was {reason}",
        task_id=task_id,
    )


async def notify_task_overdue(
    db: AsyncSession,
    task_id: int,
    notify_user_id: int,
    task_title: str,
    due_date: Optional[str] = None,
) -> Notification:
    """Create notification when task becomes overdue"""
    service = NotificationService(db)
    content = f"Task '{task_title}' is overdue"
    if due_date:
        content += f" (was due {due_date})"
    return await service.create_notification(
        user_id=notify_user_id,
        notification_type=NotificationType.task_overdue,
        title="Task Overdue",
        content=content,
        task_id=task_id,
    )


async def notify_order_created(
    db: AsyncSession,
    order_id: int,
    notify_user_id: int,
    order_reference: str,
    customer_name: Optional[str] = None,
) -> Notification:
    """Create notification when order is created"""
    service = NotificationService(db)
    content = f"New order #{order_reference}"
    if customer_name:
        content += f" from {customer_name}"
    
    return await service.create_notification(
        user_id=notify_user_id,
        notification_type=NotificationType.order_created,
        title="New Order",
        content=content,
        order_id=order_id,
    )


async def notify_order_completed(
    db: AsyncSession,
    order_id: int,
    notify_user_id: int,
    order_reference: str,
) -> Notification:
    """Create notification when order is completed"""
    service = NotificationService(db)
    return await service.create_notification(
        user_id=notify_user_id,
        notification_type=NotificationType.order_completed,
        title="Order Completed",
        content=f"Order #{order_reference} has been completed",
        order_id=order_id,
    )


async def notify_low_stock(
    db: AsyncSession,
    inventory_id: int,
    notify_user_id: int,
    product_name: str,
    current_quantity: int,
    reorder_level: int,
) -> Notification:
    """Create notification for low stock alert"""
    service = NotificationService(db)
    return await service.create_notification(
        user_id=notify_user_id,
        notification_type=NotificationType.low_stock,
        title="Low Stock Alert",
        content=f"{product_name} is low on stock ({current_quantity} units, reorder level: {reorder_level})",
        inventory_id=inventory_id,
        metadata={
            "current_quantity": current_quantity,
            "reorder_level": reorder_level,
        },
    )


async def notify_inventory_restocked(
    db: AsyncSession,
    inventory_id: int,
    notify_user_id: int,
    product_name: str,
    quantity_added: int,
    new_quantity: int,
) -> Notification:
    """Create notification when inventory is restocked"""
    service = NotificationService(db)
    return await service.create_notification(
        user_id=notify_user_id,
        notification_type=NotificationType.inventory_restocked,
        title="Inventory Restocked",
        content=f"{product_name} restocked: +{quantity_added} units (now {new_quantity})",
        inventory_id=inventory_id,
        metadata={
            "quantity_added": quantity_added,
            "new_quantity": new_quantity,
        },
    )


async def notify_sale_recorded(
    db: AsyncSession,
    sale_id: int,
    notify_user_id: int,
    total_amount: float,
    product_name: Optional[str] = None,
) -> Notification:
    """Create notification when sale is recorded"""
    service = NotificationService(db)
    content = f"Sale recorded: ${total_amount:.2f}"
    if product_name:
        content = f"Sale recorded for {product_name}: ${total_amount:.2f}"
    
    return await service.create_notification(
        user_id=notify_user_id,
        notification_type=NotificationType.sale_recorded,
        title="Sale Recorded",
        content=content,
        sale_id=sale_id,
    )


async def notify_system(
    db: AsyncSession,
    notify_user_id: int,
    title: str,
    content: str,
    metadata: Optional[Dict[str, Any]] = None,
) -> Notification:
    """Create a generic system notification"""
    service = NotificationService(db)
    return await service.create_notification(
        user_id=notify_user_id,
        notification_type=NotificationType.system,
        title=title,
        content=content,
        metadata=metadata,
    )


# ---------------- Bulk Notification Helpers ----------------

async def notify_users(
    db: AsyncSession,
    user_ids: List[int],
    notification_type: NotificationType,
    title: str,
    content: Optional[str] = None,
    **kwargs,
) -> List[Notification]:
    """Create notifications for multiple users"""
    service = NotificationService(db)
    notifications = []
    
    for user_id in user_ids:
        notification = await service.create_notification(
            user_id=user_id,
            notification_type=notification_type,
            title=title,
            content=content,
            **kwargs,
        )
        notifications.append(notification)
    
    return notifications


async def get_admins_and_managers(db: AsyncSession) -> List[int]:
    """Get user IDs of all admins (system or team) for system notifications"""
    from app.db.enums import UserRole
    result = await db.execute(
        select(User.id).where(
            (User.is_system_admin == True) | (User.role.in_([UserRole.system_admin, UserRole.team_admin]))
        )
    )
    return [row[0] for row in result.fetchall()]
