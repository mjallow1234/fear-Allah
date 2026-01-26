"""
Order-Driven Automation Triggers (Phase 6.2)

This module connects the automation engine to order lifecycle events.
When orders are created or change status, appropriate automation tasks
are created and assigned based on configurable templates.
"""
import json
from typing import Optional
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models import Order, AutomationTask, TaskAssignment, User
from app.db.enums import (
    OrderType, 
    OrderStatus,
    AutomationTaskType, 
    AutomationTaskStatus,
    AssignmentStatus,
    TaskEventType,
)
from app.automation.service import AutomationService
from app.core.config import logger


# ============================================================================
# ORDER-TO-AUTOMATION TASK TEMPLATES
# ============================================================================
# Maps order types to automation task configurations.
# Each template defines what automation tasks to create when an order is submitted.

ORDER_TASK_TEMPLATES = {
    # Agent Restock: Agent requests stock from warehouse
    # Flow: Agent orders → Foreman assembles → Foreman hands over → Delivery receives → Delivery delivers → Agent confirms
    OrderType.agent_restock.value: {
        "task_type": AutomationTaskType.restock,
        "title_template": "Restock Order #{order_id}",
        "description_template": "Process restock order for agent",
        "assignments": [
            {"role_hint": "foreman", "auto_assign_role": "foreman"},
            {"role_hint": "delivery", "auto_assign_role": "delivery"},
            {"role_hint": "requester", "auto_assign_user": "order_creator"},  # Assign order creator for final confirmation
        ],
    },
    
    # Agent Retail: Agent selling to customer  
    # Flow: Agent orders → Delivery acknowledges → Delivery delivers
    OrderType.agent_retail.value: {
        "task_type": AutomationTaskType.retail,
        "title_template": "Retail Order #{order_id}",
        "description_template": "Process retail sale from agent",
        "assignments": [
            {"role_hint": "delivery", "auto_assign_role": "delivery"},
        ],
    },
    
    # Store Keeper Restock: Store keeper requests stock
    # Flow: Store Keeper orders → Foreman assembles → Foreman hands over → Delivery receives → Delivery delivers → Store Keeper confirms
    OrderType.store_keeper_restock.value: {
        "task_type": AutomationTaskType.restock,
        "title_template": "Store Restock #{order_id}",
        "description_template": "Process store keeper restock request",
        "assignments": [
            {"role_hint": "foreman", "auto_assign_role": "foreman"},
            {"role_hint": "delivery", "auto_assign_role": "delivery"},
            {"role_hint": "requester", "auto_assign_user": "order_creator"},  # Assign order creator for final confirmation
        ],
    },
    
    # Customer Wholesale: Direct customer wholesale order
    # Flow: Customer orders → Foreman assembles → Foreman hands over → Delivery receives → Delivery delivers → Customer confirms
    OrderType.customer_wholesale.value: {
        "task_type": AutomationTaskType.wholesale,
        "title_template": "Wholesale Order #{order_id}",
        "description_template": "Process wholesale order for customer",
        "assignments": [
            {"role_hint": "foreman", "auto_assign_role": "foreman"},
            {"role_hint": "delivery", "auto_assign_role": "delivery"},
            {"role_hint": "requester", "auto_assign_user": "order_creator"},  # Assign order creator for final confirmation
        ],
    },
}


# ============================================================================
# ORDER STATUS CHANGE HANDLERS
# ============================================================================
# Maps order status transitions to automation actions.

ORDER_STATUS_HANDLERS = {
    # When order becomes IN_PROGRESS, ensure automation task is also in progress
    OrderStatus.in_progress.value: "handle_order_in_progress",
    
    # When order is AWAITING_CONFIRMATION, notify relevant users
    OrderStatus.awaiting_confirmation.value: "handle_order_awaiting_confirmation",
    
    # When order is COMPLETED, close automation task
    OrderStatus.completed.value: "handle_order_completed",
    
    # When order is CANCELLED, cancel automation task
    OrderStatus.cancelled.value: "handle_order_cancelled",
}


class OrderAutomationTriggers:
    """
    Service class for triggering automations based on order events.
    """
    
    @staticmethod
    async def on_order_created(
        db: AsyncSession,
        order: Order,
        created_by_id: int,
    ) -> Optional[AutomationTask]:
        """
        Trigger automation when a new order is created.
        Creates an AutomationTask linked to the order with appropriate assignments.
        
        Args:
            db: Database session
            order: The newly created Order
            created_by_id: ID of the user who created the order
            
        Returns:
            The created AutomationTask or None if no template exists
        """
        order_type = order.order_type
        if isinstance(order_type, OrderType):
            order_type = order_type.value
            
        template = ORDER_TASK_TEMPLATES.get(order_type)
        if not template:
            logger.debug(f"[OrderAutomation] No template for order type: {order_type}")
            return None
        
        # Create automation task
        try:
            title = template["title_template"].format(order_id=order.id)
            description = template["description_template"].format(order_id=order.id)
            
            task = await AutomationService.create_task(
                db=db,
                task_type=template["task_type"],
                title=title,
                created_by_id=created_by_id,
                description=description,
                related_order_id=order.id,
                metadata={
                    "order_type": order_type,
                    "triggered_by": "order_created",
                    "order_items": order.items,
                },
            )
            
            logger.info(f"[OrderAutomation] Created automation task {task.id} for order {order.id}")
            
            # Create assignments based on template
            await OrderAutomationTriggers._create_template_assignments(
                db=db,
                task=task,
                template=template,
                created_by_id=created_by_id,
            )
            
            # Phase 6.4: Send order created notification
            try:
                from app.automation.notification_hooks import on_order_created
                await on_order_created(db, order, notify_admins=True)
            except Exception as e:
                logger.error(f"[OrderAutomation] Failed to send order notification: {e}")
        except Exception as e:
            import traceback
            logger.error(f"[OrderAutomation] Failure in on_order_created for order {order.id}: {e}\n{traceback.format_exc()}")
            raise
        
        return task
    
    @staticmethod
    async def _create_template_assignments(
        db: AsyncSession,
        task: AutomationTask,
        template: dict,
        created_by_id: int,
    ) -> list[TaskAssignment]:
        """
        Create assignments for a task based on template configuration.
        
        Resolves concrete users for roles (foreman, delivery) when possible.
        If no active user is found for a role, still create a TaskAssignment with
        user_id = None and log a warning.
        """
        assignments = []
        
        for assignment_cfg in template.get("assignments", []):
            role_hint = assignment_cfg.get("role_hint")
            auto_assign_role = assignment_cfg.get("auto_assign_role")
            auto_assign_user = assignment_cfg.get("auto_assign_user")
            
            # Determine who to assign (may be None)
            user_id = None
            
            if auto_assign_user == "order_creator":
                # Assign to the order creator (requester)
                user_id = created_by_id
                logger.info(f"[OrderAutomation] Assigning order creator {user_id} as {role_hint}")
            elif auto_assign_role:
                # Try to find a currently active user with this role (strict - no admin fallback)
                try:
                    user_id = await OrderAutomationTriggers._find_user_by_role(db, auto_assign_role)
                except Exception as e:
                    # Log full traceback so we can detect unexpected issues in role resolution
                    logger.exception(f"[OrderAutomation] Error while resolving role user for '{auto_assign_role}': {e}")
                    user_id = None

                if user_id:
                    logger.info(f"[OrderAutomation] Found user {user_id} for role {auto_assign_role} -> assigning as {role_hint}")
                else:
                    logger.warning(f"[OrderAutomation] No active user found for role '{auto_assign_role}' when creating assignment for task {task.id}; creating placeholder assignment with no user_id")
            
            # Special-case mappings where order creator should be assigned
            if not user_id and role_hint in ("agent", "store_keeper", "sales"):
                user_id = created_by_id
                logger.info(f"[OrderAutomation] Fallback assign to order creator {user_id} for role {role_hint}")
            
            # Create assignment even if user_id is None (reserve role)
            assignment = await AutomationService.assign_user_to_task(
                db=db,
                task_id=task.id,
                user_id=user_id,
                role_hint=role_hint,
                assigned_by_id=created_by_id,
            )
            if assignment:
                assignments.append(assignment)
                logger.info(f"[OrderAutomation] Assigned user {user_id} to task {task.id} (role={role_hint})")
            else:
                logger.debug(f"[OrderAutomation] Assignment not created (maybe duplicate): task={task.id}, role={role_hint}, user_id={user_id}")
        
        return assignments
    
    @staticmethod
    async def _find_user_by_role(
        db: AsyncSession,
        role_name: str,
    ) -> Optional[int]:
        """
        Find a user with a specific role by username pattern.
        Looks for users whose username starts with the role name.
        
        Role mappings:
        - foreman -> users starting with 'foreman' (e.g., foreman1)
        - delivery -> users starting with 'delivery' (e.g., delivery1)
        - storekeeper -> users starting with 'storekeeper' (e.g., storekeeper1)
        - agent -> users starting with 'agent' (e.g., agent1)
        """
        # Map role names to username prefixes
        role_prefix_map = {
            "foreman": "foreman",
            "delivery": "delivery",
            "delivery_driver": "delivery",
            "warehouse_staff": "foreman",  # foreman handles warehouse assembly
            "storekeeper": "storekeeper",
            "store_keeper": "storekeeper",
            "agent": "agent",
            "sales_rep": "agent",
        }
        
        prefix = role_prefix_map.get(role_name, role_name)
        
        # Find first active user matching the prefix (no admin fallback)
        result = await db.execute(
            select(User)
            .where(User.is_active == True)
            .where(User.username.like(f"{prefix}%"))
            .order_by(User.id)
            .limit(1)
        )
        user = result.scalar_one_or_none()
        
        if user:
            logger.debug(f"[OrderAutomation] Found user '{user.username}' for role '{role_name}'")
            return user.id
        
        logger.debug(f"[OrderAutomation] No active user found for role '{role_name}'")
        return None
    
    @staticmethod
    async def on_order_status_changed(
        db: AsyncSession,
        order: Order,
        old_status: str,
        new_status: str,
        changed_by_id: Optional[int] = None,
    ) -> None:
        """
        Trigger automation when order status changes.
        
        Args:
            db: Database session
            order: The Order with updated status
            old_status: Previous status value
            new_status: New status value
            changed_by_id: ID of user who changed the status
        """
        logger.info(f"[OrderAutomation] Order {order.id} status: {old_status} -> {new_status}")
        
        handler_name = ORDER_STATUS_HANDLERS.get(new_status)
        if not handler_name:
            return
        
        handler = getattr(OrderAutomationTriggers, handler_name, None)
        if handler:
            await handler(db, order, changed_by_id)
    
    @staticmethod
    async def handle_order_in_progress(
        db: AsyncSession,
        order: Order,
        user_id: Optional[int],
    ) -> None:
        """Handle order transitioning to IN_PROGRESS."""
        # Find linked automation task
        task = await OrderAutomationTriggers._get_order_automation_task(db, order.id)
        if not task:
            return
        
        # Update automation task status if needed
        if task.status == AutomationTaskStatus.pending:
            task.status = AutomationTaskStatus.in_progress
            await db.commit()
            logger.info(f"[OrderAutomation] Task {task.id} status -> in_progress")
    
    @staticmethod
    async def handle_order_awaiting_confirmation(
        db: AsyncSession,
        order: Order,
        user_id: Optional[int],
    ) -> None:
        """Handle order transitioning to AWAITING_CONFIRMATION."""
        # This could trigger a notification automation task
        logger.info(f"[OrderAutomation] Order {order.id} awaiting confirmation")
        # Future: Create a confirmation reminder task
    
    @staticmethod
    async def handle_order_completed(
        db: AsyncSession,
        order: Order,
        user_id: Optional[int],
    ) -> None:
        """Handle order completion - close automation task."""
        task = await OrderAutomationTriggers._get_order_automation_task(db, order.id)
        if not task:
            return
        
        if task.status not in (AutomationTaskStatus.completed, AutomationTaskStatus.cancelled):
            await AutomationService.update_task_status(
                db=db,
                task_id=task.id,
                new_status=AutomationTaskStatus.completed,
                user_id=user_id,
            )
            logger.info(f"[OrderAutomation] Task {task.id} closed (order completed)")
        
        # Phase 6.4: Send order completed notification
        try:
            from app.automation.notification_hooks import on_order_completed
            await on_order_completed(db, order)
        except Exception as e:
            logger.error(f"[OrderAutomation] Failed to send order completed notification: {e}")
    
    @staticmethod
    async def handle_order_cancelled(
        db: AsyncSession,
        order: Order,
        user_id: Optional[int],
    ) -> None:
        """Handle order cancellation - cancel automation task."""
        task = await OrderAutomationTriggers._get_order_automation_task(db, order.id)
        if not task:
            return
        
        if task.status not in (AutomationTaskStatus.completed, AutomationTaskStatus.cancelled):
            await AutomationService.update_task_status(
                db=db,
                task_id=task.id,
                new_status=AutomationTaskStatus.cancelled,
                user_id=user_id,
            )
            logger.info(f"[OrderAutomation] Task {task.id} cancelled (order cancelled)")
    
    @staticmethod
    async def _get_order_automation_task(
        db: AsyncSession,
        order_id: int,
    ) -> Optional[AutomationTask]:
        """Get the automation task linked to an order."""
        result = await db.execute(
            select(AutomationTask)
            .where(AutomationTask.related_order_id == order_id)
            .order_by(AutomationTask.created_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()
    
    @staticmethod
    async def get_order_automation_status(
        db: AsyncSession,
        order_id: int,
    ) -> dict:
        """
        Get automation status for an order.
        Returns task info with assignment progress.
        """
        task = await OrderAutomationTriggers._get_order_automation_task(db, order_id)
        if not task:
            return {"has_automation": False}
        
        # Load with assignments
        result = await db.execute(
            select(AutomationTask)
            .options(selectinload(AutomationTask.assignments))
            .where(AutomationTask.id == task.id)
        )
        task = result.scalar_one()
        
        total = len(task.assignments)
        completed = sum(1 for a in task.assignments if a.status == AssignmentStatus.done)
        
        return {
            "has_automation": True,
            "task_id": task.id,
            "task_status": task.status.value if hasattr(task.status, 'value') else task.status,
            "title": task.title,
            "total_assignments": total,
            "completed_assignments": completed,
            "progress_percent": int((completed / total * 100) if total > 0 else 0),
        }
