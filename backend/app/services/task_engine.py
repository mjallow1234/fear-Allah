from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from app.db.models import Order, Task
from app.db.enums import OrderType, OrderStatus, TaskStatus
import logging
import os

logger = logging.getLogger(__name__)

# Check if automations are enabled (Phase 6.2)
AUTOMATIONS_ENABLED = os.environ.get("AUTOMATIONS_ENABLED", "true").lower() == "true"

# Workflow definitions with accountability steps
# Each step has a contextual action label for the UI button
WORKFLOWS = {
    OrderType.agent_restock.value: [
        # Foreman: 2 steps
        {"step_key": "assemble_items", "title": "Assemble Items", "action_label": "Assembled", "assigned_to": "foreman", "required": True},
        {"step_key": "foreman_handover", "title": "Hand Over to Delivery", "action_label": "Handed Over For Delivery", "assigned_to": "foreman", "required": True},
        # Delivery: 2 steps
        {"step_key": "delivery_received", "title": "Delivery Receives from Foreman", "action_label": "Received from Foreman", "assigned_to": "delivery", "required": True},
        {"step_key": "deliver_items", "title": "Deliver to Agent", "action_label": "Delivered to Agent", "assigned_to": "delivery", "required": True},
        # Agent: 1 step
        {"step_key": "confirm_received", "title": "Agent Confirms Receipt", "action_label": "Received", "assigned_to": "requester", "required": True},
    ],
    OrderType.agent_retail.value: [
        {"step_key": "accept_delivery", "title": "Accept Delivery Request", "action_label": "Accepted", "assigned_to": "delivery", "required": True},
        {"step_key": "deliver_items", "title": "Deliver Items", "action_label": "Delivered", "assigned_to": "delivery", "required": True},
    ],
    OrderType.store_keeper_restock.value: [
        # Foreman: 2 steps
        {"step_key": "assemble_items", "title": "Assemble Items", "action_label": "Assembled", "assigned_to": "foreman", "required": True},
        {"step_key": "foreman_handover", "title": "Hand Over to Delivery", "action_label": "Handed Over For Delivery", "assigned_to": "foreman", "required": True},
        # Delivery: 2 steps
        {"step_key": "delivery_received", "title": "Delivery Receives from Foreman", "action_label": "Received from Foreman", "assigned_to": "delivery", "required": True},
        {"step_key": "deliver_items", "title": "Deliver to Store", "action_label": "Delivered to Store", "assigned_to": "delivery", "required": True},
        # Store Keeper: 1 step
        {"step_key": "confirm_received", "title": "Store Keeper Confirms Receipt", "action_label": "Received", "assigned_to": "requester", "required": True},
    ],
    OrderType.customer_wholesale.value: [
        # Foreman: 2 steps
        {"step_key": "assemble_items", "title": "Assemble Items", "action_label": "Assembled", "assigned_to": "foreman", "required": True},
        {"step_key": "foreman_handover", "title": "Hand Over to Delivery", "action_label": "Handed Over For Delivery", "assigned_to": "foreman", "required": True},
        # Delivery: 2 steps
        {"step_key": "delivery_received", "title": "Delivery Receives from Foreman", "action_label": "Received from Foreman", "assigned_to": "delivery", "required": True},
        {"step_key": "deliver_items", "title": "Deliver to Customer", "action_label": "Delivered to Customer", "assigned_to": "delivery", "required": True},
        # No customer confirmation needed for wholesale
    ],
}


async def emit_event(event_name: str, payload: dict):
    """Event emission hook - now emits real Socket.IO events."""
    logger.info("Event emitted: %s %s", event_name, payload)
    
    # Import socket functions here to avoid circular imports
    try:
        from app.realtime.socket import emit_order_updated, emit_order_created, emit_task_completed
        
        if event_name == 'order.status_changed' or event_name == 'order.completed':
            await emit_order_updated(
                order_id=payload.get('order_id'),
                status=payload.get('status'),
                order_type=payload.get('order_type')
            )
        elif event_name == 'order.submitted':
            await emit_order_created(
                order_id=payload.get('order_id'),
                status=payload.get('status'),
                order_type=payload.get('order_type')
            )
        elif event_name == 'task.completed':
            await emit_task_completed(
                task_id=payload.get('task_id'),
                step_key=payload.get('step_key'),
                order_id=payload.get('order_id')
            )
    except Exception as e:
        logger.warning(f"Failed to emit socket event {event_name}: {e}")


async def create_order(
    session: AsyncSession, 
    order_type: str, 
    items: str = None, 
    metadata: str = None, 
    created_by_id: int = None,
    channel_id: int | None = None,
    # Forms Extension fields
    reference: str = None,
    priority: str = None,
    requested_delivery_date = None,
    customer_name: str = None,
    customer_phone: str = None,
    payment_method: str = None,
    internal_comment: str = None,
):
    """Create order and associated tasks. First task becomes ACTIVE."""
    # Normalize order_type to lowercase to accept both AGENT_RESTOCK and agent_restock
    order_type = order_type.lower() if order_type else order_type
    
    if order_type not in WORKFLOWS:
        raise ValueError("Invalid order_type")

    order = Order(
        order_type=order_type, 
        status=OrderStatus.submitted.value, 
        items=items, 
        meta=metadata,
        # Track creator for notifications and attribution
        created_by_id=created_by_id,
        # Capture channel context when available
        channel_id=channel_id,
        # Forms Extension fields
        reference=reference,
        priority=priority,
        requested_delivery_date=requested_delivery_date,
        customer_name=customer_name,
        customer_phone=customer_phone,
        payment_method=payment_method,
        internal_comment=internal_comment,
    )
    session.add(order)
    await session.flush()  # ensure order.id
    print(f"[task_engine] created order id={order.id}")

    tasks_cfg = WORKFLOWS[order_type]
    tasks = []
    for i, tcfg in enumerate(tasks_cfg):
        t = Task(order_id=order.id, step_key=tcfg["step_key"], title=tcfg["title"], required=tcfg.get("required", True))
        # first task active
        if i == 0:
            t.status = TaskStatus.active.value
            t.activated_at = datetime.utcnow()
        else:
            t.status = TaskStatus.pending.value
        session.add(t)
        tasks.append(t)

    await session.commit()

    # Emit order.submitted with order_type for frontend
    await emit_event('order.submitted', {"order_id": order.id, "status": order.status, "order_type": order.order_type})
    
    # Trigger automation (Phase 6.2)
    if AUTOMATIONS_ENABLED and created_by_id:
        try:
            from app.automation.order_triggers import OrderAutomationTriggers
            await OrderAutomationTriggers.on_order_created(session, order, created_by_id)
        except Exception as e:
            # Log full traceback for easier debugging when automation triggers fail
            import traceback, sys
            logger.error(f"[Automation] Failed to trigger order automation: {e}\n{traceback.format_exc()}")
            # Print to stderr as well so pytest captures full traceback in output
            print(traceback.format_exc(), file=sys.stderr)
    """Recompute order status based on tasks. Returns (new_status, changed_flag).
    NOTE: This function does NOT commit; caller must commit.
    """
    # Load tasks
    q = select(Task).where(Task.order_id == order.id).order_by(Task.id)
    result = await session.execute(q)
    tasks = result.scalars().all()

    # Recompute order status based on tasks. Do not return here; persist changes and return the Order object at the end.
    status_changed = False

    # Detect awaiting confirmation patterns (deliver done, confirm_received pending)
    deliver_done = any(t.step_key == 'deliver_items' and t.status == TaskStatus.done.value for t in tasks)
    confirm_pending = any(t.step_key == 'confirm_received' and t.status != TaskStatus.done.value for t in tasks)
    if deliver_done and confirm_pending:
        new_status = OrderStatus.awaiting_confirmation.value
        if order.status != new_status:
            order.status = new_status
            session.add(order)
            status_changed = True

    # If any ACTIVE -> IN_PROGRESS
    elif any(t.status == TaskStatus.active.value for t in tasks):
        new_status = OrderStatus.in_progress.value
        if order.status != new_status:
            order.status = new_status
            session.add(order)
            status_changed = True

    # If all required tasks done -> COMPLETED
    else:
        required_tasks = [t for t in tasks if t.required]
        if required_tasks and all(t.status == TaskStatus.done.value for t in required_tasks):
            new_status = OrderStatus.completed.value
            if order.status != new_status:
                order.status = new_status
                session.add(order)
                status_changed = True

    # Commit any status change so callers see the updated order
    if status_changed:
        await session.commit()
        await session.refresh(order)

    return order


async def atomic_complete_task(session: AsyncSession, task_id: int, user_id: int, commit: bool = True) -> int:
    """Perform a single atomic UPDATE to mark the task DONE without loading the ORM object first.
    Returns the number of rows updated (0 or 1). If commit=True, commits after the update.
    """
    now = datetime.utcnow()
    upd = (
        update(Task)
        .where(Task.id == task_id)
        .where(Task.status == TaskStatus.active.value)
        .where((Task.assigned_user_id == None) | (Task.assigned_user_id == user_id))
        .values(status=TaskStatus.done.value, completed_at=now, version=Task.version + 1)
    )
    res = await session.execute(upd)
    if commit:
        await session.commit()
    return res.rowcount


async def complete_task(session: AsyncSession, task_id: int, user_id: int):
    """Complete a task with validations and activate next.
    Implementation uses a single atomic UPDATE (no pre-load) to mark the task done.
    """
    next_task = None

    # Attempt atomic update without loading the task first
    rowcount = await atomic_complete_task(session, task_id, user_id, commit=False)

    if rowcount == 0:
        # Determine why the update didn't apply and raise appropriate error
        q = select(Task).where(Task.id == task_id)
        r = await session.execute(q)
        current = r.scalar_one_or_none()
        if not current:
            raise ValueError("Task not found")
        if current.assigned_user_id is not None and current.assigned_user_id != user_id:
            raise PermissionError("Not task owner")
        if current.status != TaskStatus.active.value:
            raise PermissionError("Task is not active")
        # If we get here, it's a concurrent modification
        raise RuntimeError("Conflict: task was modified concurrently")

    # At this point the task row has been updated in this session but not yet committed.
    # Load the updated task, find next task and recompute order status, then commit.
    q = select(Task).where(Task.id == task_id)
    res_refresh = await session.execute(q)
    task = res_refresh.scalar_one()

    # Activate next task if exists (conditional update)
    next_q = select(Task.id).where(Task.order_id == task.order_id, Task.id > task.id).order_by(Task.id).limit(1)
    res2 = await session.execute(next_q)
    next_id = res2.scalar_one_or_none()
    if next_id is not None:
        upd2 = (
            update(Task)
            .where(Task.id == next_id)
            .where(Task.status == TaskStatus.pending.value)
            .values(status=TaskStatus.active.value, activated_at=datetime.utcnow())
        )
        res_upd2 = await session.execute(upd2)
        if res_upd2.rowcount == 1:
            # fetch next task for event payload
            qn = select(Task).where(Task.id == next_id)
            rqn = await session.execute(qn)
            next_task = rqn.scalar_one()

    # Recompute order status inside same session
    o_q = select(Order).where(Order.id == task.order_id)
    o_res = await session.execute(o_q)
    order = o_res.scalar_one()
    old_status = order.status
    new_status, changed = await recompute_order_status(session, order)

    # Flush and commit so we emit events after commit
    await session.flush()
    await session.commit()

    # Emit events after commit with order_type for frontend
    await emit_event('task.completed', {"task_id": task.id, "step_key": task.step_key, "order_id": order.id})
    if next_task:
        await emit_event('task.activated', {"task_id": next_task.id, "assigned_user_id": next_task.assigned_user_id})
    if changed:
        if new_status == 'completed':
            await emit_event('order.completed', {"order_id": order.id, "status": order.status, "order_type": order.order_type})
        await emit_event('order.status_changed', {"order_id": order.id, "status": order.status, "order_type": order.order_type})
        
        # Trigger automation on status change (Phase 6.2)
        if AUTOMATIONS_ENABLED:
            try:
                from app.automation.order_triggers import OrderAutomationTriggers
                await OrderAutomationTriggers.on_order_status_changed(
                    session, order, old_status, new_status, user_id
                )
            except Exception as e:
                logger.warning(f"[Automation] Failed to trigger status change automation: {e}")

    return task, next_task, order

    return task, next_task, order