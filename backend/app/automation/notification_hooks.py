"""
Phase 6.4 - Automation Notification Hooks
Integrates notifications with the automation engine.

IMPORTANT: For assignment-related events on orders, notifications are
broadcast to ALL order participants (derived from task_assignments),
not just the actor or admin.
"""
from typing import Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db.models import AutomationTask, TaskAssignment, Order, User
from app.db.enums import UserRole
from app.services.notification_emitter import (
    notify_and_emit_task_assigned,
    notify_and_emit_task_completed,
    notify_and_emit_task_auto_closed,
    notify_and_emit_order_created,
    notify_and_emit_order_completed,
    notify_and_emit_low_stock,
    notify_and_emit_inventory_restocked,
    notify_and_emit_sale_recorded,
    create_and_emit_to_multiple,
    # Participant-aware emitters for order-based notifications
    notify_and_emit_task_assigned_to_participants,
    notify_and_emit_task_claimed_to_participants,
    notify_and_emit_task_completed_to_participants,
    notify_and_emit_task_auto_closed_to_participants,
    notify_and_emit_task_overdue_to_participants,
    notify_and_emit_order_completed_to_participants,
)
from app.db.enums import NotificationType
from app.core.config import logger


async def get_admins_and_managers(db: AsyncSession) -> List[int]:
    """Get user IDs of all admins and managers for system notifications"""
    result = await db.execute(
        select(User.id).where(
            (User.is_system_admin == True) |
            (User.role.in_([UserRole.system_admin, UserRole.team_admin]))
        )
    )
    return [row[0] for row in result.fetchall()]


async def get_user_info(db: AsyncSession, user_id: int) -> Optional[dict]:
    """Get basic user info"""
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user:
        return {"id": user.id, "username": user.username}
    return None


# ============================================================
# Task Notification Hooks
# ============================================================

async def on_task_assigned(
    db: AsyncSession,
    task: AutomationTask,
    assignee_id: int,
    assigner_id: Optional[int] = None,
):
    """
    Called when a user is assigned to a task.
    
    If the task is linked to an order, broadcasts notification to ALL order participants.
    Otherwise, sends notification only to the assignee.
    """
    try:
        assigner_name = None
        if assigner_id:
            assigner_info = await get_user_info(db, assigner_id)
            assigner_name = assigner_info["username"] if assigner_info else None
        
        # If task is linked to an order, broadcast to ALL participants
        if task.related_order_id:
            await notify_and_emit_task_assigned_to_participants(
                db=db,
                task_id=task.id,
                order_id=task.related_order_id,
                assignee_id=assignee_id,
                task_title=task.title,
                assigner_name=assigner_name,
            )
            logger.info(f"[Notification] Task assigned broadcast to all participants: task={task.id}, order={task.related_order_id}")
        else:
            # Standalone task - notify only the assignee
            await notify_and_emit_task_assigned(
                db=db,
                task_id=task.id,
                assignee_id=assignee_id,
                task_title=task.title,
                assigner_name=assigner_name,
            )
            logger.info(f"[Notification] Task assigned notification sent: task={task.id}, user={assignee_id}")
    except Exception as e:
        logger.error(f"[Notification] Failed to send task assigned notification: {e}")


async def on_task_completed(
    db: AsyncSession,
    task: AutomationTask,
    completed_by_id: Optional[int] = None,
):
    """
    Called when a task is completed.
    
    If the task is linked to an order, broadcasts notification to ALL order participants.
    Otherwise, notifies only the task creator.
    """
    try:
        # Get completer info
        completed_by = None
        if completed_by_id:
            user_info = await get_user_info(db, completed_by_id)
            completed_by = user_info["username"] if user_info else None
        
        # If task is linked to an order, broadcast to ALL participants
        if task.related_order_id:
            await notify_and_emit_task_completed_to_participants(
                db=db,
                task_id=task.id,
                order_id=task.related_order_id,
                task_title=task.title,
                completed_by=completed_by,
            )
            logger.info(f"[Notification] Task completed broadcast to all participants: task={task.id}, order={task.related_order_id}")
        else:
            # Standalone task - notify only the task creator (if not the completer)
            if task.created_by_id and task.created_by_id != completed_by_id:
                await notify_and_emit_task_completed(
                    db=db,
                    task_id=task.id,
                    notify_user_id=task.created_by_id,
                    task_title=task.title,
                    completed_by=completed_by,
                )
            logger.info(f"[Notification] Task completed notification sent: task={task.id}")
    except Exception as e:
        logger.error(f"[Notification] Failed to send task completed notification: {e}")


async def on_task_auto_closed(
    db: AsyncSession,
    task: AutomationTask,
    reason: str = "all assignments completed",
):
    """
    Called when a task is auto-closed by the system.
    
    If the task is linked to an order, broadcasts notification to ALL order participants.
    Otherwise, notifies only the task creator.
    """
    try:
        # If task is linked to an order, broadcast to ALL participants
        if task.related_order_id:
            await notify_and_emit_task_auto_closed_to_participants(
                db=db,
                task_id=task.id,
                order_id=task.related_order_id,
                task_title=task.title,
                reason=reason,
            )
            logger.info(f"[Notification] Task auto-closed broadcast to all participants: task={task.id}, order={task.related_order_id}")
        else:
            # Standalone task - notify only the task creator
            if task.created_by_id:
                await notify_and_emit_task_auto_closed(
                    db=db,
                    task_id=task.id,
                    notify_user_id=task.created_by_id,
                    task_title=task.title,
                    reason=reason,
                )
            logger.info(f"[Notification] Task auto-closed notification sent: task={task.id}")
    except Exception as e:
        logger.error(f"[Notification] Failed to send task auto-closed notification: {e}")


# ============================================================
# Order Notification Hooks
# ============================================================

async def on_order_created(
    db: AsyncSession,
    order: Order,
    include_admins: bool = False,
):
    """
    Called when an order is created.
    
    NOTE:
    order_created happens BEFORE tasks exist.
    Never use task_assignments or participant resolution here.
    Recipients are derived ONLY from user_operational_roles joined with ORDER_TYPE_ROLES.
    Admins are included only if explicitly requested via include_admins=True.
    """
    try:
        from app.services.notifications import get_order_role_user_ids
        
        # Get recipients based on order type roles ONLY (via user_operational_roles)
        role_user_ids, roles = await get_order_role_user_ids(db, order)
        
        # DEBUG LOG - helps diagnose role resolution on prod
        logger.error(
            "[ORDER_CREATED] roles=%s resolved_users=%s order_id=%s",
            roles, role_user_ids, order.id
        )
        
        # Include admins only if explicitly configured
        if include_admins:
            admin_ids = await get_admins_and_managers(db)
            all_recipients = list(set(role_user_ids + admin_ids))
        else:
            all_recipients = list(role_user_ids)
        
        # Filter out invalid user IDs (0, None) and the order creator
        all_recipients = [uid for uid in all_recipients if uid and uid > 0]
        if order.created_by_id and order.created_by_id in all_recipients:
            all_recipients.remove(order.created_by_id)
        
        # Log warning if no recipients found (do NOT silently return)
        if not all_recipients:
            logger.warning(
                "[ORDER_CREATED] No recipients found for order_id=%s order_type=%s roles=%s",
                order.id, order.order_type, roles
            )
        
        for user_id in all_recipients:
            await notify_and_emit_order_created(
                db=db,
                order_id=order.id,
                notify_user_id=user_id,
                order_reference=order.reference or str(order.id),
                customer_name=order.customer_name,
            )
        
        logger.info(f"[Notification] Order created notifications sent to {len(all_recipients)} users: order={order.id}")
    except Exception as e:
        logger.error(f"[Notification] Failed to send order created notification: {e}")


async def on_order_completed(
    db: AsyncSession,
    order: Order,
):
    """
    Called when an order is completed.
    Broadcasts notification to ALL order participants (derived from task_assignments).
    """
    try:
        await notify_and_emit_order_completed_to_participants(
            db=db,
            order_id=order.id,
            order_reference=order.reference or str(order.id),
        )
        
        logger.info(f"[Notification] Order completed broadcast to all participants: order={order.id}")
    except Exception as e:
        logger.error(f"[Notification] Failed to send order completed notification: {e}")


# ============================================================
# Inventory Notification Hooks
# ============================================================

async def on_low_stock_alert(
    db: AsyncSession,
    inventory_id: int,
    product_name: str,
    current_quantity: int,
    reorder_level: int,
    notify_admins: bool = True,
):
    """
    Called when inventory falls below reorder level.
    Notifies admins/managers.
    """
    try:
        if notify_admins:
            admin_ids = await get_admins_and_managers(db)
            
            for admin_id in admin_ids:
                await notify_and_emit_low_stock(
                    db=db,
                    inventory_id=inventory_id,
                    notify_user_id=admin_id,
                    product_name=product_name,
                    current_quantity=current_quantity,
                    reorder_level=reorder_level,
                )
        
        logger.info(f"[Notification] Low stock notifications sent: inventory={inventory_id}")

        # Also post an alert to Sales HQ channel
        try:
            from app.services.sales_hq import ensure_sales_hq_channel, post_system_message
            ch = await ensure_sales_hq_channel(db)
            if ch:
                content = f"**Low Stock Alert**: {product_name} is low ({current_quantity} units, reorder level: {reorder_level})."
                await post_system_message(db, ch.id, content)
        except Exception as e:
            logger.warning(f"[Notification] Failed to post low stock to Sales HQ: {e}")

    except Exception as e:
        logger.error(f"[Notification] Failed to send low stock notification: {e}")


async def on_inventory_restocked(
    db: AsyncSession,
    inventory_id: int,
    product_name: str,
    quantity_added: int,
    new_quantity: int,
    restocked_by_id: Optional[int] = None,
    notify_admins: bool = True,
):
    """
    Called when inventory is restocked.
    Notifies admins/managers (except the one who restocked).
    """
    try:
        if notify_admins:
            admin_ids = await get_admins_and_managers(db)
            # Don't notify the person who restocked
            if restocked_by_id in admin_ids:
                admin_ids.remove(restocked_by_id)
            
            for admin_id in admin_ids:
                await notify_and_emit_inventory_restocked(
                    db=db,
                    inventory_id=inventory_id,
                    notify_user_id=admin_id,
                    product_name=product_name,
                    quantity_added=quantity_added,
                    new_quantity=new_quantity,
                )
        
        logger.info(f"[Notification] Inventory restocked notifications sent: inventory={inventory_id}")
    except Exception as e:
        logger.error(f"[Notification] Failed to send inventory restocked notification: {e}")


# ============================================================
# Sales Notification Hooks
# ============================================================

async def on_sale_recorded(
    db: AsyncSession,
    sale_id: int,
    total_amount: float,
    product_name: Optional[str] = None,
    agent_id: Optional[int] = None,
    notify_admins: bool = True,
):
    """
    Called when a sale is recorded.
    Optionally notifies admins/managers.
    """
    try:
        if notify_admins:
            admin_ids = await get_admins_and_managers(db)
            # Don't notify the agent who made the sale
            if agent_id in admin_ids:
                admin_ids.remove(agent_id)
            
            for admin_id in admin_ids:
                await notify_and_emit_sale_recorded(
                    db=db,
                    sale_id=sale_id,
                    notify_user_id=admin_id,
                    total_amount=total_amount,
                    product_name=product_name,
                )
        
        logger.info(f"[Notification] Sale recorded notifications sent: sale={sale_id}")
    except Exception as e:
        logger.error(f"[Notification] Failed to send sale recorded notification: {e}")
