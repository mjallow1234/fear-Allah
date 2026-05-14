"""
Phase 6.4 - Notification Engine Emitter
Real-time notification delivery via Socket.IO
"""
import json
from typing import Optional, Dict, Any, List
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Notification
from app.db.enums import NotificationType
from app.services.identity import resolve_display_name


from app.core.config import settings

async def emit_notification_to_user(user_id: int, notification: Notification):
    """
    Emit a notification to a specific user via Socket.IO
    """
    # No-op during tests to avoid external sockets/threads
    if settings.TESTING:
        return

    from app.realtime.socket import emit_notification
    
    notification_data = {
        "id": notification.id,
        "type": notification.type.value if hasattr(notification.type, 'value') else notification.type,
        "title": notification.title,
        "content": notification.content,
        "channel_id": notification.channel_id,
        "message_id": notification.message_id,
        "sender_id": notification.sender_id,
        "sender_username": notification.sender.username if notification.sender else None,
        "sender_display_name": resolve_display_name(notification.sender) if notification.sender else None,
        "task_id": notification.task_id,
        "order_id": notification.order_id,
        "inventory_id": notification.inventory_id,
        "sale_id": notification.sale_id,
        "extra_data": notification.extra_data,
        "is_read": notification.is_read,
        "created_at": notification.created_at.isoformat() if notification.created_at else None,
    }
    
    await emit_notification(user_id, notification_data)


async def emit_notification_read(user_id: int, notification_id: int):
    """
    Emit notification:read event when a notification is marked as read
    """
    # No-op during tests
    if settings.TESTING:
        return

    from app.realtime.socket import sio, authenticated_users
    
    # Find all sids for this user
    for sid, user_data in authenticated_users.items():
        if user_data.get("user_id") == user_id:
            await sio.emit("notification:read", {
                "notification_id": notification_id,
            }, room=sid)


async def emit_all_notifications_read(user_id: int):
    """
    Emit notification:all_read event when all notifications are marked as read
    """
    # No-op during tests
    if settings.TESTING:
        return

    from app.realtime.socket import sio, authenticated_users
    
    # Find all sids for this user
    for sid, user_data in authenticated_users.items():
        if user_data.get("user_id") == user_id:
            await sio.emit("notification:all_read", {}, room=sid)


async def emit_notification_count_update(user_id: int, unread_count: int):
    """
    Emit updated notification count to user
    """
    # No-op during tests
    if settings.TESTING:
        return

    from app.realtime.socket import sio, authenticated_users
    
    # Find all sids for this user
    for sid, user_data in authenticated_users.items():
        if user_data.get("user_id") == user_id:
            await sio.emit("notification:count", {
                "unread": unread_count,
            }, room=sid)


# ============================================================
# High-level notification + emit helpers
# ============================================================

async def create_and_emit_notification(
    db: AsyncSession,
    user_id: int,
    notification_type: NotificationType,
    title: str,
    content: Optional[str] = None,
    defer_emit: bool = False,
    **kwargs
) -> Notification:
    """
    Create a notification and emit it via Socket.IO in one call.
    
    Args:
        defer_emit: When True, create the DB record (flush only, no commit)
                    and skip socket emission. Caller must commit and then
                    call emit_deferred_notifications().
    """
    from app.services.notifications import NotificationService
    
    service = NotificationService(db)
    notification = await service.create_notification(
        user_id=user_id,
        notification_type=notification_type,
        title=title,
        content=content,
        auto_commit=(not defer_emit),
        **kwargs,
    )
    
    if not defer_emit:
        await emit_notification_to_user(user_id, notification)
    return notification


async def create_and_emit_to_multiple(
    db: AsyncSession,
    user_ids: List[int],
    notification_type: NotificationType,
    title: str,
    content: Optional[str] = None,
    defer_emit: bool = False,
    **kwargs
) -> List[Notification]:
    """
    Create notifications for multiple users and emit via Socket.IO.
    
    Args:
        defer_emit: When True, create DB records (flush only, no commit)
                    and skip socket emissions. Caller must commit and then
                    call emit_deferred_notifications().
    """
    from app.services.notifications import NotificationService
    
    notifications = []
    service = NotificationService(db)
    
    for user_id in user_ids:
        notification = await service.create_notification(
            user_id=user_id,
            notification_type=notification_type,
            title=title,
            content=content,
            auto_commit=(not defer_emit),
            **kwargs,
        )
        notifications.append(notification)
        if not defer_emit:
            await emit_notification_to_user(user_id, notification)
    
    return notifications


async def emit_deferred_notifications(notifications: List[Notification]):
    """Emit previously created notifications via Socket.IO.
    
    Call this AFTER db.commit() to send socket events for notifications
    that were created with defer_emit=True.
    """
    for n in notifications:
        try:
            await emit_notification_to_user(n.user_id, n)
        except Exception:
            pass


# ============================================================
# Automation-specific notification emitters
# ============================================================

async def notify_and_emit_task_assigned(
    db: AsyncSession,
    task_id: int,
    assignee_id: int,
    task_title: str,
    assigner_name: Optional[str] = None,
) -> Notification:
    """Create and emit task assigned notification"""
    content = f"You have been assigned a new task: {task_title}"
    if assigner_name:
        content = f"{assigner_name} assigned you a task: {task_title}"
    
    return await create_and_emit_notification(
        db,
        user_id=assignee_id,
        notification_type=NotificationType.task_assigned,
        title="Task Assigned",
        content=content,
        task_id=task_id,
    )


async def notify_and_emit_task_completed(
    db: AsyncSession,
    task_id: int,
    notify_user_id: int,
    task_title: str,
    completed_by: Optional[str] = None,
) -> Notification:
    """Create and emit task completed notification"""
    content = f"Task completed: {task_title}"
    if completed_by:
        content = f"{completed_by} completed the task: {task_title}"
    
    return await create_and_emit_notification(
        db,
        user_id=notify_user_id,
        notification_type=NotificationType.task_completed,
        title="Task Completed",
        content=content,
        task_id=task_id,
    )


async def notify_and_emit_task_auto_closed(
    db: AsyncSession,
    task_id: int,
    notify_user_id: int,
    task_title: str,
    reason: str = "auto-closed due to inactivity",
) -> Notification:
    """Create and emit task auto-closed notification"""
    return await create_and_emit_notification(
        db,
        user_id=notify_user_id,
        notification_type=NotificationType.task_auto_closed,
        title="Task Auto-Closed",
        content=f"Task '{task_title}' was {reason}",
        task_id=task_id,
    )


async def notify_and_emit_task_overdue(
    db: AsyncSession,
    task_id: int,
    notify_user_id: int,
    task_title: str,
    due_date: Optional[str] = None,
) -> Notification:
    """Create and emit task overdue notification"""
    content = f"Task '{task_title}' is overdue"
    if due_date:
        content += f" (was due {due_date})"
    return await create_and_emit_notification(
        db,
        user_id=notify_user_id,
        notification_type=NotificationType.task_overdue,
        title="Task Overdue",
        content=content,
        task_id=task_id,
    )


# ============================================================
# Order-Participant-Aware Notification Emitters
# Broadcast to ALL participants in an order, not just single recipients
# ============================================================

async def notify_and_emit_task_assigned_to_participants(
    db: AsyncSession,
    task_id: int,
    order_id: int,
    assignee_id: int,
    task_title: str,
    assigner_name: Optional[str] = None,
) -> List[Notification]:
    """
    Broadcast task assigned notification to ALL order participants.
    Everyone involved in the order sees when any assignment happens.
    """
    from app.services.notifications import get_order_participant_user_ids
    
    participant_ids = await get_order_participant_user_ids(db, order_id)
    
    content = f"Task assigned to user {assignee_id}: {task_title}"
    if assigner_name:
        content = f"{assigner_name} assigned a task: {task_title}"
    
    return await create_and_emit_to_multiple(
        db,
        user_ids=list(participant_ids),
        notification_type=NotificationType.task_assigned,
        title="Task Assigned",
        content=content,
        task_id=task_id,
        order_id=order_id,
    )


async def notify_and_emit_task_claimed_to_participants(
    db: AsyncSession,
    task_id: int,
    order_id: int,
    claimer_id: int,
    task_title: str,
) -> List[Notification]:
    """
    Broadcast task claimed notification to ALL order participants.
    """
    from app.services.notifications import get_order_participant_user_ids
    
    participant_ids = await get_order_participant_user_ids(db, order_id)
    
    content = f"Task '{task_title}' was claimed by user {claimer_id}"
    
    return await create_and_emit_to_multiple(
        db,
        user_ids=list(participant_ids),
        notification_type=NotificationType.task_claimed,
        title="Task Claimed",
        content=content,
        task_id=task_id,
        order_id=order_id,
    )


async def notify_and_emit_task_completed_to_participants(
    db: AsyncSession,
    task_id: int,
    order_id: int,
    task_title: str,
    completed_by: Optional[str] = None,
    defer_emit: bool = False,
) -> List[Notification]:
    """
    Broadcast task completed notification to ALL order participants.
    """
    from app.services.notifications import get_order_participant_user_ids
    
    participant_ids = await get_order_participant_user_ids(db, order_id)
    
    content = f"Task completed: {task_title}"
    if completed_by:
        content = f"{completed_by} completed the task: {task_title}"
    
    return await create_and_emit_to_multiple(
        db,
        user_ids=list(participant_ids),
        notification_type=NotificationType.task_completed,
        title="Task Completed",
        content=content,
        task_id=task_id,
        order_id=order_id,
        defer_emit=defer_emit,
    )


async def notify_and_emit_task_auto_closed_to_participants(
    db: AsyncSession,
    task_id: int,
    order_id: int,
    task_title: str,
    reason: str = "auto-closed due to inactivity",
) -> List[Notification]:
    """
    Broadcast task auto-closed notification to ALL order participants.
    """
    from app.services.notifications import get_order_participant_user_ids
    
    participant_ids = await get_order_participant_user_ids(db, order_id)
    
    return await create_and_emit_to_multiple(
        db,
        user_ids=list(participant_ids),
        notification_type=NotificationType.task_auto_closed,
        title="Task Auto-Closed",
        content=f"Task '{task_title}' was {reason}",
        task_id=task_id,
        order_id=order_id,
    )


async def notify_and_emit_task_overdue_to_participants(
    db: AsyncSession,
    task_id: int,
    order_id: int,
    task_title: str,
    due_date: Optional[str] = None,
) -> List[Notification]:
    """
    Broadcast task overdue notification to ALL order participants.
    """
    from app.services.notifications import get_order_participant_user_ids
    
    participant_ids = await get_order_participant_user_ids(db, order_id)
    
    content = f"Task '{task_title}' is overdue"
    if due_date:
        content += f" (was due {due_date})"
    
    return await create_and_emit_to_multiple(
        db,
        user_ids=list(participant_ids),
        notification_type=NotificationType.task_overdue,
        title="Task Overdue",
        content=content,
        task_id=task_id,
        order_id=order_id,
    )


async def notify_and_emit_task_step_completed_to_participants(
    db: AsyncSession,
    order_id: int,
    task_id: int,  # workflow task ID - NOT used for notifications.task_id (FK mismatch)
    step_key: str,
    step_label: str,
    role: Optional[str] = None,
    defer_emit: bool = False,
) -> List[Notification]:
    """
    Notify all order participants that a workflow step has been completed.
    
    This is called when a workflow Task (step) transitions to done,
    e.g., "Foreman completed: Assemble items"
    
    NOTE: task_id param is the workflow tasks.id, but notifications.task_id
    references automation_tasks.id. We set task_id=None to avoid FK violation
    and store step info in metadata instead.
    """
    from app.services.notifications import get_order_participant_user_ids
    
    participant_ids = await get_order_participant_user_ids(db, order_id)
    
    # Build human-readable content: "Foreman completed: Assemble items"
    role_display = role.capitalize() if role else "Someone"
    content = f"{role_display} completed: {step_label}"
    
    return await create_and_emit_to_multiple(
        db,
        user_ids=list(participant_ids),
        notification_type=NotificationType.task_step_completed,
        title="Workflow Step Completed",
        content=content,
        task_id=None,  # DO NOT set - workflow task ID != automation_task ID
        order_id=order_id,
        defer_emit=defer_emit,
        metadata={
            "step_key": step_key,
            "step_label": step_label,
            "role": role,
            "workflow_task_id": task_id,  # Store for reference only
        },
    )


async def notify_and_emit_order_completed_to_participants(
    db: AsyncSession,
    order_id: int,
    order_reference: str,
    defer_emit: bool = False,
) -> List[Notification]:
    """
    Broadcast order completed notification to ALL order participants.
    """
    from app.services.notifications import get_order_participant_user_ids
    
    participant_ids = await get_order_participant_user_ids(db, order_id)
    
    return await create_and_emit_to_multiple(
        db,
        user_ids=list(participant_ids),
        notification_type=NotificationType.order_completed,
        title="Order Completed",
        content=f"Order #{order_reference} has been completed",
        order_id=order_id,
        defer_emit=defer_emit,
    )


async def notify_and_emit_order_created_to_roles(
    db: AsyncSession,
    order_id: int,
    order_type: str,
    order_reference: Optional[str] = None,
    creator_name: Optional[str] = None,
    created_by_id: Optional[int] = None,
) -> List[Notification]:
    """
    Emit order_created notifications to users based on order type roles.

    Uses user_operational_roles to resolve recipients.
    This is called at ORDER CREATION TIME, before any tasks exist.

    NOTE: This is the authoritative order_created emitter.
    Do NOT use task assignments or participant resolution here.
    """
    from app.services.notifications import get_order_role_user_ids_by_type
    from app.core.config import logger
    
    # Resolve users by order type roles (via user_operational_roles)
    user_ids, roles = await get_order_role_user_ids_by_type(db, order_type)
    
    # DEBUG LOG - verify role resolution on prod
    logger.error(
        "[ORDER_CREATED] order_id=%s order_type=%s roles=%s recipients=%s",
        order_id, order_type, roles, user_ids
    )
    
    # Filter out invalid user IDs and the order creator
    user_ids = [uid for uid in user_ids if uid and uid > 0]
    if created_by_id and created_by_id in user_ids:
        user_ids.remove(created_by_id)
    
    if not user_ids:
        logger.warning(
            "[ORDER_CREATED] No recipients found for order_id=%s order_type=%s roles=%s",
            order_id, order_type, roles
        )
        return []
    
    ref = order_reference or str(order_id)
    content = f"New order #{ref}"
    if creator_name:
        content += f" from {creator_name}"

    return await create_and_emit_to_multiple(
        db,
        user_ids=user_ids,
        notification_type=NotificationType.order_created,
        title="New Order",
        content=content,
        order_id=order_id,
    )


async def notify_and_emit_order_created(
    db: AsyncSession,
    order_id: int,
    notify_user_id: int,
    order_reference: str,
    creator_name: Optional[str] = None,
) -> Notification:
    """Create and emit order created notification"""
    content = f"New order #{order_reference}"
    if creator_name:
        content += f" from {creator_name}"
    
    return await create_and_emit_notification(
        db,
        user_id=notify_user_id,
        notification_type=NotificationType.order_created,
        title="New Order",
        content=content,
        order_id=order_id,
    )


async def notify_and_emit_order_completed(
    db: AsyncSession,
    order_id: int,
    notify_user_id: int,
    order_reference: str,
) -> Notification:
    """Create and emit order completed notification"""
    return await create_and_emit_notification(
        db,
        user_id=notify_user_id,
        notification_type=NotificationType.order_completed,
        title="Order Completed",
        content=f"Order #{order_reference} has been completed",
        order_id=order_id,
    )


async def notify_and_emit_low_stock(
    db: AsyncSession,
    inventory_id: int,
    notify_user_id: int,
    product_name: str,
    current_quantity: int,
    reorder_level: int,
    product_id: Optional[int] = None,
) -> Notification:
    """Create and emit low stock notification"""
    return await create_and_emit_notification(
        db,
        user_id=notify_user_id,
        notification_type=NotificationType.low_stock,
        title="Low Stock Alert",
        content=f"{product_name} is low on stock ({current_quantity} units, reorder level: {reorder_level})",
        inventory_id=inventory_id,
        metadata={
            "current_quantity": current_quantity,
            "reorder_level": reorder_level,
            "action_type": "inventory",
            "entity_id": product_id or inventory_id,
            "action_url": f"/sales?tab=inventory&product={product_id or inventory_id}",
        },
    )


async def notify_and_emit_inventory_restocked(
    db: AsyncSession,
    inventory_id: int,
    notify_user_id: int,
    product_name: str,
    quantity_added: int,
    new_quantity: int,
    product_id: Optional[int] = None,
) -> Notification:
    """Create and emit inventory restocked notification"""
    return await create_and_emit_notification(
        db,
        user_id=notify_user_id,
        notification_type=NotificationType.inventory_restocked,
        title="Inventory Restocked",
        content=f"{product_name} restocked: +{quantity_added} units (now {new_quantity})",
        inventory_id=inventory_id,
        metadata={
            "quantity_added": quantity_added,
            "new_quantity": new_quantity,
            "action_type": "inventory",
            "entity_id": product_id or inventory_id,
            "action_url": f"/sales?tab=inventory&product={product_id or inventory_id}",
        },
    )


async def notify_and_emit_sale_recorded(
    db: AsyncSession,
    sale_id: int,
    notify_user_id: int,
    total_amount: float,
    product_name: Optional[str] = None,
    agent_display: Optional[str] = None,
    transaction_id: int | None = None,
) -> Notification:
    """Create and emit sale recorded notification"""
    content = f"Sale recorded: D{total_amount:.2f}"
    if product_name:
        content = f"Sale recorded for {product_name}: D{total_amount:.2f}"
    if agent_display:
        content += f" by {agent_display}"
    
    return await create_and_emit_notification(
        db,
        user_id=notify_user_id,
        notification_type=NotificationType.sale_recorded,
        title="Sale Recorded",
        content=content,
        sale_id=sale_id,
        metadata={
            "action_type": "sale",
            "entity_id": sale_id,
            "action_url": f"/sales?tab=transactions&highlight={transaction_id or sale_id}",
        },
    )


async def notify_and_emit_system(
    db: AsyncSession,
    notify_user_id: int,
    title: str,
    content: str,
    metadata: Optional[Dict[str, Any]] = None,
) -> Notification:
    """Create and emit a generic system notification"""
    return await create_and_emit_notification(
        db,
        user_id=notify_user_id,
        notification_type=NotificationType.system,
        title=title,
        content=content,
        metadata=metadata,
    )
