"""
Sales Automation Triggers (Phase 6.3)
Hooks for triggering automation tasks based on sales and inventory events.
Phase 6.4 - Integrated notification hooks.
"""
import os
import logging

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Inventory, Sale, AutomationTask
from app.db.enums import AutomationTaskType, AutomationTaskStatus
from app.automation.service import AutomationService

logger = logging.getLogger(__name__)

# Feature flag
SALES_AUTOMATION_ENABLED = os.environ.get("SALES_AUTOMATION_ENABLED", "true").lower() == "true"


class SalesAutomationTriggers:
    """
    Automation triggers for sales and inventory events.
    Creates automation tasks when certain conditions are met.
    """
    
    @staticmethod
    async def on_sale_recorded(
        db: AsyncSession,
        sale: Sale,
    ) -> None:
        """
        Hook called when a sale is recorded.
        Can create follow-up automation tasks (e.g., delivery confirmation, commission review).
        
        Args:
            db: Database session
            sale: The recorded sale
        """
        if not SALES_AUTOMATION_ENABLED:
            return
        
        # Phase 6.4: Send sale notification
        try:
            from app.automation.notification_hooks import on_sale_recorded
            await on_sale_recorded(
                db=db,
                sale_id=sale.id,
                total_amount=sale.total_amount,
                product_name=None,  # Could be fetched from inventory
                agent_id=sale.sold_by_user_id,
                notify_admins=True,
            )
        except Exception as e:
            logger.error(f"[SalesAutomation] Failed to send sale notification: {e}")
        
        # For now, just log. Future: create delivery confirmation task, etc.
        logger.info(f"[SalesAutomation] Sale {sale.id} recorded, channel={sale.sale_channel}")
        
        # Example: Create a review task for large sales
        if sale.total_amount >= 10000:  # Threshold for high-value sale review
            try:
                await AutomationService.create_task(
                    db=db,
                    task_type=AutomationTaskType.sale,
                    title=f"Review High-Value Sale #{sale.id}",
                    created_by_id=sale.sold_by_user_id,
                    description=f"High-value sale of {sale.total_amount} requires review",
                    metadata={
                        "trigger": "high_value_sale",
                        "sale_id": sale.id,
                        "amount": sale.total_amount,
                    }
                )
                logger.info(f"[SalesAutomation] Created review task for high-value sale {sale.id}")
            except Exception as e:
                logger.warning(f"[SalesAutomation] Failed to create high-value sale task: {e}")
    
    @staticmethod
    async def on_low_stock(
        db: AsyncSession,
        inventory_item: Inventory,
        triggered_by_user_id: int,
    ) -> None:
        """
        Hook called when inventory falls below threshold.
        Creates a restock automation task.
        
        Args:
            db: Database session
            inventory_item: The inventory item with low stock
            triggered_by_user_id: User who triggered the event (via sale)
        """
        if not SALES_AUTOMATION_ENABLED:
            return
        
        # Check if there's already a pending/in-progress restock task for this product
        from sqlalchemy import select
        existing_q = (
            select(AutomationTask)
            .where(AutomationTask.task_type == AutomationTaskType.restock)
            .where(AutomationTask.status.in_([AutomationTaskStatus.pending, AutomationTaskStatus.in_progress]))
            .where(AutomationTask.task_metadata.like(f'%"product_id": {inventory_item.product_id}%'))
        )
        existing_res = await db.execute(existing_q)
        existing_task = existing_res.scalar_one_or_none()
        
        if existing_task:
            logger.info(f"[SalesAutomation] Skipping low stock task creation - existing task {existing_task.id}")
            return
        
        # Create restock automation task
        try:
            task = await AutomationService.create_task(
                db=db,
                task_type=AutomationTaskType.restock,
                title=f"Low Stock Alert: {inventory_item.product_name or f'Product {inventory_item.product_id}'}",
                created_by_id=triggered_by_user_id,
                description=f"Stock level ({inventory_item.total_stock}) is below threshold ({inventory_item.low_stock_threshold}). Restock needed.",
                metadata={
                    "trigger": "low_stock",
                    "inventory_id": inventory_item.id,
                    "product_id": inventory_item.product_id,
                    "product_name": inventory_item.product_name,
                    "current_stock": inventory_item.total_stock,
                    "threshold": inventory_item.low_stock_threshold,
                }
            )
            
            # Auto-assign to warehouse role (if user exists)
            # For now, assign to the system/admin user or a default warehouse user
            try:
                from app.db.models import User
                from sqlalchemy import select as sel
                
                # Find a user with warehouse role or system_admin
                warehouse_q = sel(User).where(
                    (User.role == 'system_admin') | (User.is_system_admin == True)
                ).limit(1)
                warehouse_res = await db.execute(warehouse_q)
                warehouse_user = warehouse_res.scalar_one_or_none()
                
                if warehouse_user:
                    await AutomationService.assign_user_to_task(
                        db=db,
                        task_id=task.id,
                        user_id=warehouse_user.id,
                        role_hint="warehouse",
                        assigned_by_id=triggered_by_user_id,
                    )
            except Exception as assign_err:
                logger.warning(f"[SalesAutomation] Could not auto-assign low stock task: {assign_err}")
            
            logger.info(
                f"[SalesAutomation] Created low stock task {task.id} for product {inventory_item.product_id}"
            )
            
            # Phase 6.4: Send low stock notification
            try:
                from app.automation.notification_hooks import on_low_stock_alert
                await on_low_stock_alert(
                    db=db,
                    inventory_id=inventory_item.id,
                    product_name=inventory_item.product_name or f"Product {inventory_item.product_id}",
                    current_quantity=inventory_item.total_stock,
                    reorder_level=inventory_item.low_stock_threshold,
                    notify_admins=True,
                )
            except Exception as notif_err:
                logger.error(f"[SalesAutomation] Failed to send low stock notification: {notif_err}")
            
        except Exception as e:
            logger.error(f"[SalesAutomation] Failed to create low stock task: {e}")
    
    @staticmethod
    async def on_inventory_restocked(
        db: AsyncSession,
        inventory_item: Inventory,
        quantity_added: int,
        performed_by_id: int,
    ) -> None:
        """
        Hook called when inventory is restocked.
        Can close related low-stock automation tasks.
        
        Args:
            db: Database session
            inventory_item: The restocked inventory item
            quantity_added: Amount that was added
            performed_by_id: User who performed the restock
        """
        if not SALES_AUTOMATION_ENABLED:
            return
        
        # Phase 6.4: Send restock notification
        try:
            from app.automation.notification_hooks import on_inventory_restocked
            await on_inventory_restocked(
                db=db,
                inventory_id=inventory_item.id,
                product_name=inventory_item.product_name or f"Product {inventory_item.product_id}",
                quantity_added=quantity_added,
                new_quantity=inventory_item.total_stock,
                restocked_by_id=performed_by_id,
                notify_admins=True,
            )
        except Exception as notif_err:
            logger.error(f"[SalesAutomation] Failed to send restock notification: {notif_err}")
        
        # Check if stock is now above threshold
        if inventory_item.total_stock > inventory_item.low_stock_threshold:
            # Find and close any pending low-stock tasks for this product
            from sqlalchemy import select
            tasks_q = (
                select(AutomationTask)
                .where(AutomationTask.task_type == AutomationTaskType.restock)
                .where(AutomationTask.status.in_([AutomationTaskStatus.pending, AutomationTaskStatus.in_progress]))
                .where(AutomationTask.task_metadata.like(f'%"product_id": {inventory_item.product_id}%'))
            )
            tasks_res = await db.execute(tasks_q)
            tasks = tasks_res.scalars().all()
            
            for task in tasks:
                await AutomationService.update_task_status(
                    db=db,
                    task_id=task.id,
                    new_status=AutomationTaskStatus.completed,
                    user_id=performed_by_id,
                )
                logger.info(f"[SalesAutomation] Closed low stock task {task.id} after restock")

