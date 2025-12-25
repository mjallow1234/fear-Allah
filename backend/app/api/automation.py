"""
Automation Engine API Endpoints (Phase 6.1)
Task management endpoints for the new automation engine.
"""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_current_user
from app.db.database import get_db
from app.db.models import User
from app.db.enums import AutomationTaskType, AutomationTaskStatus
from app.automation.service import AutomationService
from app.automation.schemas import (
    TaskCreate,
    TaskResponse,
    TaskListResponse,
    AssignmentCreate,
    AssignmentResponse,
    AssignmentComplete,
    TaskEventResponse,
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
    
    task = await AutomationService.create_task(
        db=db,
        task_type=payload.task_type,
        title=payload.title,
        created_by_id=user_id,
        description=payload.description,
        related_order_id=payload.related_order_id,
        metadata=payload.metadata,
    )
    
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
    
    # Only creator or system admin can see events
    if task.created_by_id != user_id and not user.is_system_admin:
        raise HTTPException(status_code=403, detail="Access denied")
    
    events = await AutomationService.get_task_events(db, task_id)
    
    return [_event_to_response(e) for e in events]


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
    """
    user_id = current_user["user_id"]
    
    assignment = await AutomationService.complete_assignment(
        db=db,
        task_id=task_id,
        user_id=user_id,
        notes=payload.notes,
    )
    
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
    
    return TaskResponse(
        id=task.id,
        task_type=task.task_type,
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
