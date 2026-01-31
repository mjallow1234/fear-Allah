from datetime import datetime
import json
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

    # Normalize metadata into a dict regardless of how it was passed (dict or JSON/string)
    meta_dict = {}
    if isinstance(metadata, dict):
        meta_dict = dict(metadata)
    else:
        try:
            meta_dict = json.loads(metadata) if metadata else {}
        except Exception:
            try:
                import ast
                meta_dict = ast.literal_eval(metadata) if metadata else {}
            except Exception:
                meta_dict = {}

    # If payload looks like a form payload (top-level fields), normalize under 'form_payload'
    if 'form_payload' not in meta_dict and isinstance(metadata, dict) and ('fields' in metadata or 'responses' in metadata):
        meta_dict['form_payload'] = metadata

    # If a form_payload is present, optionally persist normalized top-level fields
    form_payload = meta_dict.get('form_payload')
    if isinstance(form_payload, dict):
        # Persist items/customer info into order columns for easier querying
        try:
            items_from_form = form_payload.get('items') or (form_payload.get('form_payload') or {}).get('items') if isinstance(form_payload, dict) else None
            if items_from_form is not None:
                items_list = items_from_form if isinstance(items_from_form, list) else []
                items_val = json.dumps(items_list)
            else:
                # If API passed a python list in 'items' param, prefer that
                try:
                    items_list = items if isinstance(items, list) else (json.loads(items) if items else [])
                except Exception:
                    items_list = []
                items_val = json.dumps(items_list) if items_list is not None else None
        except Exception:
            items_val = json.dumps(items) if items is not None else None

        customer_name_val = customer_name or form_payload.get('customer_name') or (form_payload.get('customer') or {}).get('name') if isinstance(form_payload, dict) else customer_name
        customer_phone_val = customer_phone or form_payload.get('customer_phone') or (form_payload.get('customer') or {}).get('phone') if isinstance(form_payload, dict) else customer_phone
    else:
        # Non-form path: ensure items stored as JSON string when possible
        try:
            items_list = items if isinstance(items, list) else (json.loads(items) if items else [])
            items_val = json.dumps(items_list) if items_list is not None else None
        except Exception:
            items_val = items
        customer_name_val = customer_name
        customer_phone_val = customer_phone

    # Ensure meta includes delivery_location and quantities derived from items when possible
    # Do not overwrite existing explicit meta entries
    if 'delivery_location' not in meta_dict:
        # Try to find delivery_location in form_payload or top-level meta
        dl = None
        if isinstance(form_payload, dict):
            dl = form_payload.get('delivery_location') or (form_payload.get('delivery') or {}).get('location')
        dl = dl or meta_dict.get('delivery_location')
        if dl is not None:
            meta_dict['delivery_location'] = dl

    if 'quantities' not in meta_dict:
        try:
            qtys = None
            # try extracting from items_list computed above
            if 'items_list' in locals() and isinstance(items_list, list) and len(items_list) > 0:
                q = []
                for it in items_list:
                    if isinstance(it, dict):
                        qv = it.get('quantity') or it.get('qty')
                        try:
                            q.append(int(qv) if qv is not None else None)
                        except Exception:
                            q.append(None)
                    else:
                        q.append(None)
                qtys = q
            if qtys is not None:
                meta_dict['quantities'] = qtys
        except Exception:
            pass
    else:
        items_val = items
        customer_name_val = customer_name
        customer_phone_val = customer_phone

    # Create the order; store meta as a JSON string for consistent reading later
    try:
        meta_json = json.dumps(meta_dict) if meta_dict else None
    except Exception:
        meta_json = str(meta_dict) if meta_dict else None

    # Temporary runtime verification log (remove after verification)
    try:
        logger.info(
            "[ORDER-CREATE] create_order meta=%s",
            meta_dict,
        )
    except Exception:
        logger.warning("[ORDER-CREATE] failed to log meta_dict")

    order = Order(
        order_type=order_type,
        status=OrderStatus.submitted.value,
        items=items_val,
        meta=meta_json,
        # Track creator for notifications and attribution
        created_by_id=created_by_id,
        # Capture channel context when available
        channel_id=channel_id,
        # Forms Extension fields
        reference=reference,
        priority=priority,
        requested_delivery_date=requested_delivery_date,
        customer_name=customer_name_val,
        customer_phone=customer_phone_val,
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

    # If no immediate sequential next task was activated above, ensure we still
    # activate the next pending *required* workflow step (if any).
    # This avoids treating "no more steps for current role" as workflow completion
    # and ensures downstream roles receive an ACTIVE task when appropriate.
    if next_task is None:
        try:
            pending_q = select(Task.id).where(
                Task.order_id == task.order_id,
                Task.required == True,
                Task.status == TaskStatus.pending.value,
            ).order_by(Task.id).limit(1)
            pend_res = await session.execute(pending_q)
            pending_id = pend_res.scalar_one_or_none()
            if pending_id is not None:
                upd_p = (
                    update(Task)
                    .where(Task.id == pending_id)
                    .where(Task.status == TaskStatus.pending.value)
                    .values(status=TaskStatus.active.value, activated_at=datetime.utcnow())
                )
                res_upd_p = await session.execute(upd_p)
                if res_upd_p.rowcount == 1:
                    qn2 = select(Task).where(Task.id == pending_id)
                    rqn2 = await session.execute(qn2)
                    next_task = rqn2.scalar_one()
        except Exception as e:
            logger.warning(f"[TaskEngine] Failed to activate next pending required task for order {task.order_id}: {e}")

    # Recompute order status inside same session
    o_q = select(Order).where(Order.id == task.order_id)
    o_res = await session.execute(o_q)
    order = o_res.scalar_one()
    old_status = order.status
    # Safely call recompute_order_status only if implemented (avoid NameError/crash)
    ros = globals().get("recompute_order_status")
    if callable(ros):
        try:
            new_status, changed = await ros(session, order)
        except Exception as e:
            logger.warning(f"recompute_order_status failed: {e}")
            new_status, changed = order.status, False
    else:
        logger.warning("recompute_order_status not available, skipping")
        new_status, changed = order.status, False

    # Safety check: only consider an order COMPLETED when ALL required workflow tasks are done.
    # Prevent premature completion when there are remaining required workflow steps (e.g., next role's steps).
    try:
        if str(new_status).upper() == 'COMPLETED':
            from app.db.models import Task as OrderTask
            from app.db.enums import TaskStatus as OrderTaskStatus

            remaining_q = select(OrderTask.id).where(
                OrderTask.order_id == order.id,
                OrderTask.required == True,
                OrderTask.status != OrderTaskStatus.done.value,
            ).limit(1)
            rem_res = await session.execute(remaining_q)
            remaining = rem_res.scalar_one_or_none()
            if remaining:
                logger.info(f"[TaskEngine] Suppressing order completion for order {order.id}: remaining workflow tasks exist (task id {remaining})")
                # Cancel the completion transition
                new_status = order.status
                changed = False
    except Exception as e:
        logger.warning(f"[TaskEngine] Failed to verify remaining workflow tasks before completing order {order.id}: {e}")

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

    # --- Delivery assignment lifecycle: ensure delivery assignments only mark DONE when all delivery workflow steps are complete ---
    try:
        # Determine the role assigned to the completed workflow step (if any)
        wf_def = WORKFLOWS.get(order.order_type, [])
        step_role = None
        for s in wf_def:
            if s.get('step_key') == task.step_key:
                step_role = s.get('assigned_to')
                break

        if step_role == 'delivery':
            # Find the order's automation task and delivery assignments
            try:
                from app.automation.order_triggers import OrderAutomationTriggers
                from app.db.models import Task as OrderTask, TaskAssignment
                from app.db.enums import TaskStatus as OrderTaskStatus, AssignmentStatus

                automation_task = await OrderAutomationTriggers._get_order_automation_task(session, order.id)
                if automation_task:
                    # Compute remaining required delivery steps for the order
                    role_steps = [s['step_key'] for s in wf_def if s.get('assigned_to') == 'delivery' and s.get('required', True)]
                    has_remaining = False
                    if role_steps:
                        remaining_q = select(OrderTask.id).where(
                            OrderTask.order_id == order.id,
                            OrderTask.step_key.in_(role_steps),
                            OrderTask.status != OrderTaskStatus.done.value,
                        ).limit(1)
                        rem_res = await session.execute(remaining_q)
                        has_remaining = rem_res.scalar_one_or_none() is not None

                    if not has_remaining:
                        # No remaining delivery workflow steps - mark delivery assignments DONE for this automation task
                        now = datetime.utcnow()
                        await session.execute(
                            update(TaskAssignment)
                            .where(TaskAssignment.task_id == automation_task.id)
                            .where(TaskAssignment.role_hint == 'delivery')
                            .where(TaskAssignment.status != AssignmentStatus.done)
                            .values(status=AssignmentStatus.done, completed_at=now)
                        )
                        logger.info(f"[TaskEngine] Marked delivery assignments DONE for automation task {automation_task.id} as all delivery steps completed for order {order.id}")
            except Exception as e:
                logger.warning(f"[TaskEngine] Failed to evaluate delivery assignment completion for order {order.id}: {e}")
    except Exception as e:
        logger.warning(f"[TaskEngine] Error in delivery assignment post-complete check: {e}")

    return task, next_task, order

    return task, next_task, order