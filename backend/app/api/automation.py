"""
Automation Engine API Endpoints (Phase 6.1)
Task management endpoints for the new automation engine.
"""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_current_user
from app.core.logging import automation_logger
from app.db.database import get_db
from app.db.models import User
from app.db.enums import AutomationTaskType, AutomationTaskStatus
from app.automation.service import AutomationService, ClaimConflictError, ClaimPermissionError, ClaimNotFoundError
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
    
    return TaskListResponse(
        tasks=[_task_to_response(t) for t in tasks],
        total=len(tasks),
    )


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
    
    return _task_to_response(task)


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
    user = await _get_user(db, user_id)

    # If override requested, ensure user is admin
    if payload.override and not user.is_system_admin:
        raise HTTPException(status_code=403, detail="Only admins can override claims")

    try:
        task = await AutomationService.claim_task(db=db, task_id=task_id, user_id=user_id, override=payload.override)
    except ClaimNotFoundError:
        raise HTTPException(status_code=404, detail="Task not found")
    except ClaimPermissionError:
        raise HTTPException(status_code=403, detail="You are not allowed to claim this task")
    except ClaimConflictError:
        raise HTTPException(status_code=409, detail="Task already claimed")
    except Exception as e:
        automation_logger.error("Claim failed", error=e, task_id=task_id, user_id=user_id)
        raise HTTPException(status_code=500, detail=str(e))

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


@router.post("/tasks/{task_id}/complete", response_model=AssignmentResponse)
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
        raise HTTPException(status_code=404, detail=str(e))
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        # Catch unexpected exceptions to log stack trace for debugging
        automation_logger.error("Unhandled exception while completing assignment", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal Server Error")
    
    if not assignment:
        raise HTTPException(status_code=404, detail="Assignment not found or you are not assigned to this task")
    
    return _assignment_to_response(assignment)


@router.get("/my-assignments", response_model=list[AssignmentResponse])
async def get_my_assignments(
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Get all assignments for the current user."""
    user_id = current_user["user_id"]
    assignments = await AutomationService.get_user_assignments(db, user_id)
    return [_assignment_to_response(a) for a in assignments]


# ---------------------- Response Helpers ----------------------

def _task_to_response(task) -> TaskResponse:
    """Convert task model to response schema."""
    import json
    # Handle assignments - check if loaded to avoid lazy loading issues
    assignments = []
    try:
        # Only access if already loaded
        if hasattr(task, '_sa_instance_state') and 'assignments' in task.__dict__:
            assignments = [_assignment_to_response(a) for a in (task.assignments or [])]
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

    return TaskResponse(
        id=task.id,
        task_type=task_type_value,
        status=task.status,
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
    return AssignmentResponse(
        id=assignment.id,
        task_id=assignment.task_id,
        user_id=assignment.user_id,
        role_hint=assignment.role_hint,
        status=assignment.status,
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
