"""
Phase 6.4 - Automation Notification Hooks
Integrates notifications with the automation engine.
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
    Sends notification to the assignee.
    """
    try:
        assigner_name = None
        if assigner_id:
            assigner_info = await get_user_info(db, assigner_id)
            assigner_name = assigner_info["username"] if assigner_info else None
        
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
    Notifies the task creator and all assignees.
    """
    try:
        # Get completer info
        completed_by = None
        if completed_by_id:
            user_info = await get_user_info(db, completed_by_id)
            completed_by = user_info["username"] if user_info else None
        
        # Notify task creator
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
    Notifies the task creator.
    """
    try:
        # Notify task creator
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
    notify_admins: bool = True,
):
    """
    Called when an order is created.
    Optionally notifies admins/managers.
    """
    try:
        if notify_admins:
            admin_ids = await get_admins_and_managers(db)
            # Don't notify the person who created the order
            if order.created_by_id in admin_ids:
                admin_ids.remove(order.created_by_id)
            
            for admin_id in admin_ids:
                await notify_and_emit_order_created(
                    db=db,
                    order_id=order.id,
                    notify_user_id=admin_id,
                    order_number=order.order_number or str(order.id),
                    customer_name=order.customer_name,
                )
        
        logger.info(f"[Notification] Order created notifications sent: order={order.id}")
    except Exception as e:
        logger.error(f"[Notification] Failed to send order created notification: {e}")


async def on_order_completed(
    db: AsyncSession,
    order: Order,
):
    """
    Called when an order is completed.
    Notifies the order creator.
    """
    try:
        # Notify order creator
        if order.created_by_id:
            await notify_and_emit_order_completed(
                db=db,
                order_id=order.id,
                notify_user_id=order.created_by_id,
                order_number=order.order_number or str(order.id),
            )
        
        logger.info(f"[Notification] Order completed notification sent: order={order.id}")
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
