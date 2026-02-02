"""
Automation Engine API Endpoints (Phase 6.1)
Task management endpoints for the new automation engine.
"""
from typing import Optional, Union

from fastapi import APIRouter, Depends, HTTPException, status
from app.db.models import TaskAssignment
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_current_user
from app.core.logging import automation_logger
from app.db.database import get_db
from app.db.models import User
from app.db.enums import AutomationTaskType, AutomationTaskStatus
from app.automation.service import AutomationService, ClaimConflictError, ClaimPermissionError, ClaimInvalidStateError, ClaimNotFoundError
from app.automation.schemas import (
    TaskCreate,
    TaskResponse,
    TaskListResponse,
    AssignmentCreate,
    AssignmentResponse,
    AssignmentComplete,
    TaskEventResponse,
    ClaimRequest,
)

router = APIRouter(prefix="/automation", tags=["Automation"])


async def _get_user(db: AsyncSession, user_id: int) -> User:
    """Helper to get User model from user_id."""
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return user


# Helper: normalize form-based payloads (best-effort)
# Returns dict with possible keys: items, customer_name, customer_phone, delivery_location, form_payload
def _extract_from_form_payload(meta: dict) -> dict:
    """Best-effort extraction from dynamic form payloads or responses.

    This function is intentionally permissive and searches common shapes:
    - `form_payload` object with `fields` list of {name,type,value}
    - `responses` list or dicts containing name/question/answer/value
    - Flat mappings where keys may be 'items', 'products', 'line_items', 'customer_name', 'phone', etc.
    """
    if not isinstance(meta, dict):
        return {}

    # Prefer explicit keys if present
    form_src = meta.get('form_payload') or meta.get('responses')

    items = None
    customer_name = None
    customer_phone = None
    delivery_location = None

    def scan_obj(obj):
        nonlocal items, customer_name, customer_phone, delivery_location
        if isinstance(obj, dict):
            # Special handling for common form field shapes
            # e.g., {'name':'products', 'type':'items', 'value': [...]}
            if 'type' in obj and ('value' in obj or 'answer' in obj):
                ftype = str(obj.get('type') or '').lower()
                fname = str(obj.get('name') or '').lower()
                val = obj.get('value') if 'value' in obj else obj.get('answer')
                if items is None and (ftype in ('items', 'products', 'line_items') or fname in ('items', 'products', 'line_items')):
                    if isinstance(val, list):
                        items = val
                if customer_name is None and fname in ('customer_name',) and isinstance(val, str):
                    # Only treat explicit 'customer_name' as customer name — avoid generic 'name' that is field metadata
                    customer_name = val
                if customer_phone is None and fname in ('phone', 'mobile') and isinstance(val, str):
                    customer_phone = val
                if delivery_location is None and fname in ('address', 'location', 'delivery_location') and isinstance(val, str):
                    delivery_location = val

                # Recurse into the value but avoid treating field metadata keys (like 'name') as actual values
                scan_obj(val)
                return

            for k, v in obj.items():
                lk = str(k).lower()
                # Items candidates on keys
                if items is None and lk in ('items', 'products', 'line_items'):
                    if isinstance(v, list):
                        items = v
                # Name candidates
                if customer_name is None and any(x in lk for x in ('customer_name', 'name')):
                    if isinstance(v, str):
                        customer_name = v
                # Phone candidates
                if customer_phone is None and any(x in lk for x in ('phone', 'mobile')):
                    if isinstance(v, str):
                        customer_phone = v
                # Delivery/location
                if delivery_location is None and any(x in lk for x in ('address', 'location', 'delivery_location')):
                    if isinstance(v, str):
                        delivery_location = v
                # Recurse
                scan_obj(v)
        elif isinstance(obj, list):
            for it in obj:
                scan_obj(it)
        return

    # Try scanning the explicit form object first
    if form_src is not None:
        scan_obj(form_src)

    # If items still not found, scan top-level meta keys for form-like data
    if items is None:
        scan_obj(meta)

    return {
        'items': items,
        'customer_name': customer_name,
        'customer_phone': customer_phone,
        'delivery_location': delivery_location,
        'form_payload': form_src,
    }


# ---------------------- Task Endpoints ----------------------

@router.post("/tasks", response_model=TaskResponse, status_code=status.HTTP_201_CREATED)
async def create_task(
    payload: TaskCreate,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """
    Create a new automation task.
    
    Only system admins or authorized users can create tasks.
    """
    user_id = current_user["user_id"]
    
    automation_logger.info(
        "Creating automation task",
        user_id=user_id,
        task_type=payload.task_type,
        title=payload.title,
    )
    
    # Normalize task_type to enum value (case-insensitive)
    try:
        from app.db.enums import AutomationTaskType as ATT
        try:
            task_type_enum = ATT(payload.task_type.lower())
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid task_type")

        task = await AutomationService.create_task(
            db=db,
            task_type=task_type_enum,
            title=payload.title,
            created_by_id=user_id,
            description=payload.description,
            related_order_id=payload.related_order_id,
            metadata=payload.metadata,
            required_role=payload.required_role,
        )
        automation_logger.info(
            "Automation task created",
            task_id=task.id,
            task_type=payload.task_type,
            user_id=user_id,
        )
    except Exception as e:
        automation_logger.error(
            "Automation task creation failed",
            error=e,
            user_id=user_id,
            task_type=payload.task_type,
        )
        raise
    
    return _task_to_response(task)


@router.get("/tasks", response_model=TaskListResponse)
async def list_tasks(
    status: Optional[AutomationTaskStatus] = None,
    task_type: Optional[AutomationTaskType] = None,
    limit: int = 50,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """
    List automation tasks with optional filters.
    
    System admins see all tasks; regular users see only their own.
    """
    user_id = current_user["user_id"]
    user = await _get_user(db, user_id)
    
    # Filter by creator unless system admin
    created_by_id = None if user.is_system_admin else user_id
    
    tasks = await AutomationService.list_tasks(
        db=db,
        status=status,
        task_type=task_type,
        created_by_id=created_by_id,
        limit=limit,
        offset=offset,
        current_user=user,
    )

    # Enrich tasks with order details when present (best-effort)
    enriched = []
    from app.db.models import Order
    import json as _json
    for t in tasks:
        resp = _task_to_response(t)
        if getattr(t, 'related_order_id', None):
            try:
                res = await db.execute(select(Order).where(Order.id == t.related_order_id))
                order = res.scalar_one_or_none()
                if order:
                    import ast
                    order_items = None
                    try:
                        order_items = _json.loads(order.items) if order.items else None
                    except Exception:
                        try:
                            order_items = ast.literal_eval(order.items) if order.items else None
                        except Exception:
                            order_items = None

                    meta = None
                    try:
                        meta = _json.loads(order.meta) if order.meta else None
                    except Exception:
                        try:
                            meta = ast.literal_eval(order.meta) if order.meta else None
                        except Exception:
                            meta = None

                    # Fallbacks: sometimes items or customer info live inside meta/form payloads
                    if not order_items and isinstance(meta, dict):
                        # First, try legacy keys
                        order_items = meta.get('items') or meta.get('line_items')

                        # Try to extract from dynamic form payload or responses
                        form_info = _extract_from_form_payload(meta)
                        if not order_items and form_info.get('items'):
                            order_items = form_info.get('items')

                        # If form_info found fields, use them as fallbacks
                        quantities = None
                        if isinstance(order_items, list):
                            try:
                                quantities = [int(i.get('quantity') if isinstance(i.get('quantity'), (int, str)) else (i.get('qty') or None)) if isinstance(i, dict) else None for i in order_items]
                            except Exception:
                                quantities = None

                        delivery_location = None
                        if isinstance(meta, dict):
                            delivery_location = meta.get('delivery_location') or (meta.get('delivery') or {}).get('location') or form_info.get('delivery_location')

                        customer_name = order.customer_name or (meta.get('customer_name') if isinstance(meta, dict) else None) or (meta.get('customer') or {}).get('name') if isinstance(meta, dict) else order.customer_name
                        if not customer_name:
                            customer_name = form_info.get('customer_name')

                        customer_phone = order.customer_phone or (meta.get('customer_phone') if isinstance(meta, dict) else None) or (meta.get('customer') or {}).get('phone') if isinstance(meta, dict) else order.customer_phone
                        if not customer_phone:
                            customer_phone = form_info.get('customer_phone')

                        # If we found a form payload, include it under meta for UI
                        if form_info.get('form_payload'):
                            # Preserve original meta but include normalized form under 'form_payload'
                            try:
                                meta = dict(meta)
                                meta['form_payload'] = form_info.get('form_payload')
                            except Exception:
                                pass
                    else:
                        quantities = None
                        if isinstance(order_items, list):
                            try:
                                quantities = [int(i.get('quantity')) if isinstance(i.get('quantity'), (int, str)) else None for i in order_items]
                            except Exception:
                                quantities = None

                        delivery_location = None
                        if isinstance(meta, dict):
                            delivery_location = meta.get('delivery_location') or (meta.get('delivery') or {}).get('location') or (meta.get('form_payload') or {}).get('delivery_location')

                        customer_name = order.customer_name or (meta.get('customer_name') if isinstance(meta, dict) else None) or (meta.get('customer') or {}).get('name') if isinstance(meta, dict) else order.customer_name
                        customer_phone = order.customer_phone or (meta.get('customer_phone') if isinstance(meta, dict) else None) or (meta.get('customer') or {}).get('phone') if isinstance(meta, dict) else order.customer_phone

                    order_details = {
                        'order_type': (order.order_type.name if hasattr(order.order_type, 'name') else str(order.order_type)).upper(),
                        'items': order_items,
                        'quantities': quantities,
                        'delivery_location': delivery_location,
                        'customer_name': customer_name,
                        'customer_phone': customer_phone,
                        'meta': meta,
                    }
                    data = resp.model_dump()
                    data['order_details'] = order_details
                    resp = TaskResponse.model_validate(data)
            except Exception:
                pass
        enriched.append(resp)

    return TaskListResponse(
        tasks=enriched,
        total=len(enriched),
    )


@router.get("/available-tasks", response_model=TaskListResponse)
async def available_tasks(
    role: str,
    limit: int = 50,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
):
    """Get tasks available to a role (unclaimed tasks with required_role == role)."""
    tasks = await AutomationService.available_tasks_for_role(db=db, role=role, limit=limit, offset=offset)
    return TaskListResponse(tasks=[_task_to_response(t) for t in tasks], total=len(tasks))


@router.get("/tasks/{task_id}", response_model=TaskResponse)
async def get_task(
    task_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Get a task by ID."""
    user_id = current_user["user_id"]
    user = await _get_user(db, user_id)
    
    task = await AutomationService.get_task(db, task_id, include_assignments=True)
    
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    # Check access: creator, assignee, or system admin
    is_assignee = await AutomationService.is_assigned_to_task(db, task_id, user_id)
    can_view = (
        task.created_by_id == user_id or
        is_assignee or
        user.is_system_admin
    )
    
    if not can_view:
        raise HTTPException(status_code=403, detail="Access denied")

    # Build base response
    resp = _task_to_response(task)

    # Enrich with order details snapshot when available (read-only)
    if getattr(task, 'related_order_id', None):
        try:
            from app.db.models import Order
            import json as _json
            res = await db.execute(select(Order).where(Order.id == task.related_order_id))
            order = res.scalar_one_or_none()
            if order:
                import ast
                order_items = None
                try:
                    order_items = _json.loads(order.items) if order.items else None
                except Exception:
                    try:
                        # Fallback for Python repr strings (legacy storage)
                        order_items = ast.literal_eval(order.items) if order.items else None
                    except Exception:
                        order_items = None
                meta = None
                try:
                    meta = _json.loads(order.meta) if order.meta else None
                except Exception:
                    try:
                        meta = ast.literal_eval(order.meta) if order.meta else None
                    except Exception:
                        meta = None

                # Fallbacks for items/customer info and support form-based responses
                if not order_items and isinstance(meta, dict):
                    # Legacy direct keys
                    order_items = meta.get('items') or meta.get('line_items')

                    # Try to extract from dynamic form payload / responses
                    form_info = _extract_from_form_payload(meta)
                    if not order_items and form_info.get('items'):
                        order_items = form_info.get('items')

                    quantities = None
                    if isinstance(order_items, list):
                        try:
                            quantities = [int(i.get('quantity') if isinstance(i.get('quantity'), (int, str)) else (i.get('qty') or None)) if isinstance(i, dict) else None for i in order_items]
                        except Exception:
                            quantities = None

                    delivery_location = None
                    if isinstance(meta, dict):
                        delivery_location = meta.get('delivery_location') or (meta.get('delivery') or {}).get('location') or form_info.get('delivery_location')

                    customer_name = order.customer_name or (meta.get('customer_name') if isinstance(meta, dict) else None) or (meta.get('customer') or {}).get('name') if isinstance(meta, dict) else order.customer_name
                    if not customer_name:
                        customer_name = form_info.get('customer_name')

                    customer_phone = order.customer_phone or (meta.get('customer_phone') if isinstance(meta, dict) else None) or (meta.get('customer') or {}).get('phone') if isinstance(meta, dict) else order.customer_phone
                    if not customer_phone:
                        customer_phone = form_info.get('customer_phone')

                    # Preserve original meta and attach form_payload for UI rendering
                    if form_info.get('form_payload'):
                        try:
                            meta = dict(meta)
                            meta['form_payload'] = form_info.get('form_payload')
                        except Exception:
                            pass
                else:
                    quantities = None
                    if isinstance(order_items, list):
                        try:
                            quantities = [int(i.get('quantity')) if isinstance(i.get('quantity'), (int, str)) else None for i in order_items]
                        except Exception:
                            quantities = None

                    delivery_location = None
                    if isinstance(meta, dict):
                        delivery_location = meta.get('delivery_location') or (meta.get('delivery') or {}).get('location') or (meta.get('form_payload') or {}).get('delivery_location')

                    customer_name = order.customer_name or (meta.get('customer_name') if isinstance(meta, dict) else None) or ((meta.get('customer') or {}).get('name') if isinstance(meta, dict) else None)
                    customer_phone = order.customer_phone or (meta.get('customer_phone') if isinstance(meta, dict) else None) or ((meta.get('customer') or {}).get('phone') if isinstance(meta, dict) else None)

                order_details = {
                    'order_type': (order.order_type.name if hasattr(order.order_type, 'name') else str(order.order_type)).upper(),
                    'items': order_items,
                    'quantities': quantities,
                    'delivery_location': delivery_location,
                    'customer_name': customer_name,
                    'customer_phone': customer_phone,
                    'meta': meta,
                }

                # Inject order_details into response (create new validated model)
                data = resp.model_dump()
                data['order_details'] = order_details
                return TaskResponse.model_validate(data)
        except Exception:
            # Best-effort: do not fail if enrichment fails
            pass

    return resp


@router.get("/tasks/{task_id}/events", response_model=list[TaskEventResponse])
async def get_task_events(
    task_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Get all events for a task (audit trail)."""
    user_id = current_user["user_id"]
    user = await _get_user(db, user_id)
    
    task = await AutomationService.get_task(db, task_id, include_assignments=False)
    
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    # Creator, assignees, or system admin can see events
    is_assignee = await AutomationService.is_assigned_to_task(db, task_id, user_id)
    can_view = (
        task.created_by_id == user_id or
        is_assignee or
        user.is_system_admin
    )
    
    if not can_view:
        raise HTTPException(status_code=403, detail="Access denied")
    
    events = await AutomationService.get_task_events(db, task_id)
    
    return [_event_to_response(e) for e in events]


@router.get("/tasks/{task_id}/workflow-step")
async def get_active_workflow_step(
    task_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """
    Get the current active workflow step for an automation task.
    
    Returns the active step details including the action label for the UI button.
    Also returns which role each step is assigned to.
    """
    from app.db.models import Task, AutomationTask, TaskAssignment
    from app.db.enums import TaskStatus
    from app.services.task_engine import WORKFLOWS
    
    user_id = current_user["user_id"]
    
    # Get the automation task
    result = await db.execute(
        select(AutomationTask).where(AutomationTask.id == task_id)
    )
    automation_task = result.scalar_one_or_none()
    
    if not automation_task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    if not automation_task.related_order_id:
        return {"active_step": None, "all_steps": [], "my_steps": []}
    
    # Get order to determine workflow type
    from app.db.models import Order
    order_result = await db.execute(
        select(Order).where(Order.id == automation_task.related_order_id)
    )
    order = order_result.scalar_one_or_none()
    
    if not order:
        return {"active_step": None, "all_steps": [], "my_steps": []}
    
    # Get user's assignment to determine their role
    assignment_result = await db.execute(
        select(TaskAssignment).where(
            TaskAssignment.task_id == task_id,
            TaskAssignment.user_id == user_id
        )
    )
    user_assignment = assignment_result.scalar_one_or_none()
    user_role = user_assignment.role_hint if user_assignment else None
    
    # Get workflow definition
    workflow_def = WORKFLOWS.get(order.order_type, [])
    
    # Get all workflow tasks for this order
    tasks_result = await db.execute(
        select(Task).where(Task.order_id == automation_task.related_order_id).order_by(Task.id)
    )
    workflow_tasks = tasks_result.scalars().all()
    
    # Build step info list
    steps = []
    my_steps = []
    active_step = None
    
    for task in workflow_tasks:
        # Find matching workflow definition for action_label and assigned_to
        step_def = next((s for s in workflow_def if s["step_key"] == task.step_key), None)
        action_label = step_def.get("action_label", "Complete") if step_def else "Complete"
        assigned_to = step_def.get("assigned_to", "unknown") if step_def else "unknown"
        
        is_active = task.status == TaskStatus.active or task.status == TaskStatus.active.value
        is_done = task.status == TaskStatus.done or task.status == TaskStatus.done.value
        
        step_info = {
            "id": task.id,
            "step_key": task.step_key,
            "title": task.title,
            "action_label": action_label,
            "assigned_to": assigned_to,
            "status": task.status.value if hasattr(task.status, 'value') else task.status,
            "is_active": is_active,
            "is_done": is_done,
        }
        steps.append(step_info)
        
        # Check if this step belongs to the current user's role
        if user_role and assigned_to == user_role:
            my_steps.append(step_info)
        # Special case: requester role matches the automation task creator (order requester)
        elif assigned_to == "requester" and automation_task.created_by_id == user_id:
            my_steps.append(step_info)
        
        if is_active:
            active_step = step_info
    
    return {
        "active_step": active_step,
        "all_steps": steps,
        "my_steps": my_steps,
        "my_role": user_role,
        "order_type": order.order_type,
    }


@router.post("/tasks/{task_id}/cancel", response_model=TaskResponse)
async def cancel_task(
    task_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Cancel a task."""
    user_id = current_user["user_id"]
    
    can_manage = await AutomationService.can_manage_task(db, task_id, user_id)
    
    if not can_manage:
        raise HTTPException(status_code=403, detail="Only creator or admin can cancel")
    
    task = await AutomationService.update_task_status(
        db=db,
        task_id=task_id,
        new_status=AutomationTaskStatus.cancelled,
        user_id=user_id,
    )
    
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    return _task_to_response(task)


@router.post("/tasks/{task_id}/claim", response_model=TaskResponse)
async def claim_task_endpoint(
    task_id: int,
    payload: ClaimRequest,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Claim a task. Admins may pass override=True to take over an existing claim."""
    user_id = current_user["user_id"]

    # NOTE: Do not perform permission lookups here. Authorization is enforced in AutomationService.claim_task().
    try:
        task = await AutomationService.claim_task(db=db, task_id=task_id, user_id=user_id, override=payload.override)
    except ClaimNotFoundError:
        raise HTTPException(status_code=404, detail="Task not found")
    except ClaimPermissionError:
        raise HTTPException(status_code=403, detail="You are not allowed to claim this task")
    except ClaimConflictError:
        raise HTTPException(status_code=409, detail="Task already claimed")
    except ClaimInvalidStateError:
        raise HTTPException(status_code=400, detail="Task is not open for claim")
    except Exception as e:
        automation_logger.error("Claim failed", error=e, task_id=task_id, user_id=user_id)
        raise HTTPException(status_code=500, detail=str(e))

    return _task_to_response(task)


@router.post("/tasks/{task_id}/reassign", response_model=TaskResponse)
async def reassign_task_endpoint(
    task_id: int,
    payload: dict,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Admin-only: reassign claimed user on a task."""
    user_id = current_user["user_id"]
    user = await _get_user(db, user_id)
    if not user.is_system_admin:
        raise HTTPException(status_code=403, detail="Only system admins can reassign tasks")

    new_user_id = payload.get('new_user_id')
    if not new_user_id:
        raise HTTPException(status_code=400, detail="new_user_id is required")

    task = await AutomationService.reassign_task(db=db, task_id=task_id, new_user_id=new_user_id, acting_user_id=user_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    return _task_to_response(task)


@router.post("/assignments/{assignment_id}/reassign", response_model=AssignmentResponse)
async def reassign_assignment_endpoint(
    assignment_id: int,
    payload: dict,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Admin-only: reassign an assignment to a different user or role."""
    user_id = current_user["user_id"]
    user = await _get_user(db, user_id)
    if not user.is_system_admin:
        raise HTTPException(status_code=403, detail="Only system admins can reassign assignments")

    new_user_id = payload.get('new_user_id')
    new_role = payload.get('new_role_hint')

    assignment = await AutomationService.reassign_assignment(db=db, assignment_id=assignment_id, new_user_id=new_user_id, new_role_hint=new_role, acting_user_id=user_id)
    if not assignment:
        raise HTTPException(status_code=404, detail="Assignment not found")

    return _assignment_to_response(assignment)


@router.post("/assignments/{assignment_id}/complete", response_model=AssignmentResponse)
async def complete_assignment_by_id(
    assignment_id: int,
    payload: AssignmentComplete,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Complete an assignment by assignment id.

    This endpoint is assignment-scoped and will complete the specific assignment
    if the caller is the assigned user or a system admin. It avoids ambiguity
    where a task-level complete call may result in force-completion.
    """
    user_id = current_user["user_id"]

    try:
        assignment = await AutomationService.complete_assignment_by_assignment_id(
            db=db,
            assignment_id=assignment_id,
            user_id=user_id,
            notes=payload.notes,
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:
        import traceback
        automation_logger.error("Unhandled exception while completing assignment by id")
        traceback.print_exc()
        raise

    return _assignment_to_response(assignment)


@router.post("/tasks/{task_id}/delete", response_model=TaskResponse)
async def delete_task_endpoint(
    task_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Admin-only: soft delete (cancel) a task."""
    user_id = current_user["user_id"]
    user = await _get_user(db, user_id)
    if not user.is_system_admin:
        raise HTTPException(status_code=403, detail="Only system admins can delete tasks")

    task = await AutomationService.soft_delete_task(db=db, task_id=task_id, acting_user_id=user_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    return _task_to_response(task)
# ---------------------- Assignment Endpoints ----------------------

@router.post("/tasks/{task_id}/assign", response_model=AssignmentResponse, status_code=status.HTTP_201_CREATED)
async def assign_user(
    task_id: int,
    payload: AssignmentCreate,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """
    Assign a user to a task.
    
    Only task creator or system admin can assign users.
    """
    user_id = current_user["user_id"]
    
    can_manage = await AutomationService.can_manage_task(db, task_id, user_id)
    
    if not can_manage:
        raise HTTPException(status_code=403, detail="Only creator or admin can assign")
    
    assignment = await AutomationService.assign_user_to_task(
        db=db,
        task_id=task_id,
        user_id=payload.user_id,
        role_hint=payload.role_hint,
        notes=payload.notes,
        assigned_by_id=user_id,
    )
    
    if not assignment:
        raise HTTPException(status_code=400, detail="Could not create assignment (task not found or user already assigned)")
    
    return _assignment_to_response(assignment)


@router.post("/tasks/{task_id}/claim", response_model=TaskResponse)
async def claim_task_endpoint(
    task_id: int,
    payload: ClaimRequest | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """
    Claim an available automation task and create a TaskAssignment.
    """
    user_id = current_user["user_id"]
    override = False
    if payload is not None:
        try:
            override = bool(payload.override)
        except Exception:
            override = False

    try:
        task = await AutomationService.claim_task(
            db=db,
            task_id=task_id,
            user_id=user_id,
            override=override,
        )
    except ClaimPermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except ClaimConflictError as e:
        raise HTTPException(status_code=409, detail=str(e))
    except ClaimInvalidStateError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except ClaimNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        automation_logger.error("Unhandled error during claim", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal Server Error")

    return _task_to_response(task)


@router.post("/tasks/{task_id}/complete", response_model=Union[AssignmentResponse, TaskResponse])
async def complete_my_assignment(
    task_id: int,
    payload: AssignmentComplete,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """
    Mark your own assignment as complete.
    
    Only the assigned user can complete their assignment.
    Validates that the corresponding workflow task is active before allowing completion.

    Admins: can force-complete a task when there are no assignments. In that case
    the task is marked completed and a `TaskResponse` is returned (and an audit
    log is created).
    """
    user_id = current_user["user_id"]
    
    try:
        assignment = await AutomationService.complete_assignment(
            db=db,
            task_id=task_id,
            user_id=user_id,
            notes=payload.notes,
        )
    except ValueError as e:
        # If assignment not found, allow system admins to force-complete a task
        # only when there are no assignments present.
        try:
            user = await _get_user(db, user_id)
        except Exception:
            raise HTTPException(status_code=404, detail=str(e))

        if user.is_system_admin:
            # Load the task with assignments to check if any exist
            task = await AutomationService.get_task(db, task_id, include_assignments=True)
            if not task:
                raise HTTPException(status_code=404, detail="Task not found")

            if task.assignments:
                # There are assignments; the admin should use the assignment-complete flow
                raise HTTPException(status_code=400, detail="Cannot force-complete: task has assignments")

            # Perform force-complete via existing update method to ensure consistency
            task = await AutomationService.update_task_status(
                db=db,
                task_id=task_id,
                new_status=AutomationTaskStatus.completed,
                user_id=user_id,
            )

            if not task:
                raise HTTPException(status_code=404, detail="Task not found")

            # Audit the admin action
            try:
                from app.services.audit import log_audit_from_user, AuditActions
                await log_audit_from_user(db, user, action=AuditActions.TASK_COMPLETE, target_type='task', target_id=task.id, description='admin force-complete task with no assignments')
            except Exception:
                pass

            return _task_to_response(task)
        else:
            raise HTTPException(status_code=404, detail=str(e))
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        import traceback
        automation_logger.error("Unhandled exception while completing assignment")
        traceback.print_exc()
        raise
    
    if not assignment:
        raise HTTPException(status_code=404, detail="Assignment not found or you are not assigned to this task")
    
    return _assignment_to_response(assignment)


@router.get("/my-assignments", response_model=list[AssignmentResponse])
async def get_my_assignments(
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
    search: Optional[str] = None,
    order_type: Optional[str] = None,
):
    """Get all assignments for the current user.

    System admins receive ALL assignments (visibility override).
    
    Optional filters:
    - search: numeric value to match order ID (primary) or task ID (secondary)
    - order_type: filter by order type (e.g., agent_retail, agent_restock)
    """
    from app.db.models import AutomationTask as ATModel, Order as OrderModel
    from app.db.enums import OrderType as OT

    user_id = current_user["user_id"]
    user = await _get_user(db, user_id)

    # Base query with joins needed for filtering
    # Always join to AutomationTask and Order for consistent filtering
    query = (
        select(TaskAssignment)
        .join(ATModel, TaskAssignment.task_id == ATModel.id)
        .outerjoin(OrderModel, ATModel.related_order_id == OrderModel.id)
    )

    if not user.is_system_admin:
        query = query.where(TaskAssignment.user_id == user_id)

    # Apply search filter - prioritize order ID match
    if search:
        try:
            search_id = int(search)
            # Primary: match order ID; Secondary: match task ID
            query = query.where(
                (OrderModel.id == search_id) | (ATModel.id == search_id)
            )
        except ValueError:
            # Non-numeric search - ignore for now
            pass

    # Apply order_type filter - strictly on orders.order_type
    if order_type:
        query = query.where(OrderModel.order_type == order_type)

    result = await db.execute(query)
    assignments = list(result.scalars().all())

    return [_assignment_to_response(a) for a in assignments]


# ---------------------- Response Helpers ----------------------

def _task_to_response(task) -> TaskResponse:
    """Convert task model to response schema."""
    import json
    from datetime import datetime
    from app.db.enums import AssignmentStatus as AS

    # Handle assignments - check if loaded to avoid lazy loading issues
    assignments = []
    try:
        # Only access if already loaded
        if hasattr(task, '_sa_instance_state') and 'assignments' in task.__dict__:
            for a in (task.assignments or []):
                status_value = a.status
                completed_at = a.completed_at

                # If the task is completed, ensure assignments are presented as completed (read-only fix)
                if task.status == AutomationTaskStatus.completed:
                    if a.status not in (AS.done, AS.skipped):
                        status_value = AS.done
                        if not completed_at:
                            completed_at = datetime.utcnow()

                # Build the assignment response ensuring presentation-level consistency
                assignments.append(AssignmentResponse(
                    id=a.id,
                    task_id=a.task_id,
                    user_id=a.user_id,
                    role_hint=a.role_hint,
                    status=status_value,
                    notes=a.notes,
                    assigned_at=a.assigned_at,
                    completed_at=completed_at,
                ))
    except Exception:
        pass
    
    # Normalize task_type to enum NAME (uppercase) for consistency with API tests
    task_type_value = None
    if hasattr(task.task_type, 'name'):
        task_type_value = task.task_type.name.upper()
    elif hasattr(task.task_type, 'value'):
        task_type_value = str(task.task_type.value).upper()
    else:
        task_type_value = str(task.task_type).upper()

    # Preserve status value (may be enum or string); Pydantic will validate/convert
    status_value = task.status

    return TaskResponse(
        id=task.id,
        task_type=task_type_value,
        status=status_value,
        title=task.title,
        description=task.description,
        created_by_id=task.created_by_id,
        related_order_id=task.related_order_id,
        metadata=json.loads(task.task_metadata) if task.task_metadata else None,
        created_at=task.created_at,
        updated_at=task.updated_at,
        assignments=assignments,
    )


def _assignment_to_response(assignment) -> AssignmentResponse:
    """Convert assignment model to response schema."""
    # Preserve assignment status value (may be enum or string)
    status_value = assignment.status

    return AssignmentResponse(
        id=assignment.id,
        task_id=assignment.task_id,
        user_id=assignment.user_id,
        role_hint=assignment.role_hint,
        status=status_value,
        notes=assignment.notes,
        assigned_at=assignment.assigned_at,
        completed_at=assignment.completed_at,
    )


def _event_to_response(event) -> TaskEventResponse:
    """Convert event model to response schema."""
    import json
    return TaskEventResponse(
        id=event.id,
        task_id=event.task_id,
        user_id=event.user_id,
        event_type=event.event_type,
        metadata=json.loads(event.event_metadata) if event.event_metadata else None,
        created_at=event.created_at,
    )
