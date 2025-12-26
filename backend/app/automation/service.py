"""
Automation Engine Service Layer (Phase 6.1)
Core business logic for task-based workflow automation.
Phase 6.4 - Integrated notification hooks.
"""
import json
from datetime import datetime
from typing import Optional, Any

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models import AutomationTask, TaskAssignment, TaskEvent, User
from app.db.enums import (
    AutomationTaskType, 
    AutomationTaskStatus, 
    AssignmentStatus, 
    TaskEventType
)
from app.core.config import logger


class AutomationService:
    """
    Service layer for the automation engine.
    Provides methods for task lifecycle management.
    """
    
    # ---------------------- Task Operations ----------------------
    
    @staticmethod
    async def create_task(
        db: AsyncSession,
        task_type: AutomationTaskType,
        title: str,
        created_by_id: int,
        description: Optional[str] = None,
        related_order_id: Optional[int] = None,
        metadata: Optional[dict[str, Any]] = None,
    ) -> AutomationTask:
        """
        Create a new automation task.
        
        Args:
            db: Database session
            task_type: Type of task (restock, retail, etc.)
            title: Human-readable task title
            created_by_id: ID of the user creating the task
            description: Optional detailed description
            related_order_id: Optional linked order ID
            metadata: Optional JSON metadata
            
        Returns:
            The created AutomationTask
        """
        task = AutomationTask(
            task_type=task_type,
            status=AutomationTaskStatus.pending,
            title=title,
            description=description,
            created_by_id=created_by_id,
            related_order_id=related_order_id,
            task_metadata=json.dumps(metadata) if metadata else None,
        )
        db.add(task)
        await db.flush()  # Get the ID
        
        # Log the creation event
        await AutomationService._log_event(
            db=db,
            task_id=task.id,
            user_id=created_by_id,
            event_type=TaskEventType.created,
            metadata={"title": title, "task_type": task_type.value}
        )
        
        await db.commit()
        
        # Reload with relationships
        result = await db.execute(
            select(AutomationTask)
            .options(selectinload(AutomationTask.assignments))
            .where(AutomationTask.id == task.id)
        )
        task = result.scalar_one()
        
        logger.info(f"[Automation] Task {task.id} created: {title} (type={task_type.value})")
        
        return task
    
    @staticmethod
    async def get_task(
        db: AsyncSession,
        task_id: int,
        include_assignments: bool = True,
        include_events: bool = False,
    ) -> Optional[AutomationTask]:
        """
        Get a task by ID with optional related data.
        """
        query = select(AutomationTask).where(AutomationTask.id == task_id)
        
        if include_assignments:
            query = query.options(selectinload(AutomationTask.assignments))
        if include_events:
            query = query.options(selectinload(AutomationTask.events))
            
        result = await db.execute(query)
        return result.scalar_one_or_none()
    
    @staticmethod
    async def list_tasks(
        db: AsyncSession,
        status: Optional[AutomationTaskStatus] = None,
        task_type: Optional[AutomationTaskType] = None,
        created_by_id: Optional[int] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[AutomationTask]:
        """
        List tasks with optional filters.
        """
        query = select(AutomationTask).options(selectinload(AutomationTask.assignments))
        
        if status:
            query = query.where(AutomationTask.status == status)
        if task_type:
            query = query.where(AutomationTask.task_type == task_type)
        if created_by_id:
            query = query.where(AutomationTask.created_by_id == created_by_id)
            
        query = query.order_by(AutomationTask.created_at.desc()).limit(limit).offset(offset)
        
        result = await db.execute(query)
        return list(result.scalars().all())
    
    @staticmethod
    async def update_task_status(
        db: AsyncSession,
        task_id: int,
        new_status: AutomationTaskStatus,
        user_id: Optional[int] = None,
    ) -> Optional[AutomationTask]:
        """
        Update task status.
        """
        task = await AutomationService.get_task(db, task_id, include_assignments=False)
        if not task:
            return None
            
        old_status = task.status
        task.status = new_status
        
        # Log status change
        event_type = TaskEventType.closed if new_status == AutomationTaskStatus.completed else TaskEventType.cancelled
        await AutomationService._log_event(
            db=db,
            task_id=task_id,
            user_id=user_id,
            event_type=event_type,
            metadata={"old_status": old_status.value, "new_status": new_status.value}
        )
        
        await db.commit()
        await db.refresh(task)
        
        logger.info(f"[Automation] Task {task_id} status: {old_status.value} → {new_status.value}")
        
        return task
    
    # ---------------------- Assignment Operations ----------------------
    
    @staticmethod
    async def assign_user_to_task(
        db: AsyncSession,
        task_id: int,
        user_id: int,
        role_hint: Optional[str] = None,
        notes: Optional[str] = None,
        assigned_by_id: Optional[int] = None,
    ) -> Optional[TaskAssignment]:
        """
        Assign a user to a task.
        
        Args:
            db: Database session
            task_id: ID of the task
            user_id: ID of the user to assign
            role_hint: Optional role hint (e.g., "foreman", "delivery")
            notes: Optional notes about the assignment
            assigned_by_id: ID of the user making the assignment
            
        Returns:
            The created TaskAssignment or None if task doesn't exist
        """
        # Verify task exists
        task = await AutomationService.get_task(db, task_id, include_assignments=False)
        if not task:
            return None
        
        # Check if assignment already exists
        existing = await db.execute(
            select(TaskAssignment).where(
                TaskAssignment.task_id == task_id,
                TaskAssignment.user_id == user_id
            )
        )
        if existing.scalar_one_or_none():
            logger.warning(f"[Automation] User {user_id} already assigned to task {task_id}")
            return None
        
        # Create assignment
        assignment = TaskAssignment(
            task_id=task_id,
            user_id=user_id,
            role_hint=role_hint,
            status=AssignmentStatus.pending,
            notes=notes,
        )
        db.add(assignment)
        
        # Update task status to in_progress if it was pending
        if task.status == AutomationTaskStatus.pending:
            task.status = AutomationTaskStatus.in_progress
        
        # Log the assignment
        await AutomationService._log_event(
            db=db,
            task_id=task_id,
            user_id=assigned_by_id,
            event_type=TaskEventType.assigned,
            metadata={"assigned_user_id": user_id, "role_hint": role_hint}
        )
        
        await db.commit()
        await db.refresh(assignment)
        
        logger.info(f"[Automation] User {user_id} assigned to task {task_id} (role={role_hint})")
        
        # Phase 6.4: Send notification to assignee
        try:
            from app.automation.notification_hooks import on_task_assigned
            await on_task_assigned(db, task, user_id, assigned_by_id)
        except Exception as e:
            logger.error(f"[Automation] Failed to send assignment notification: {e}")
        
        return assignment
    
    @staticmethod
    async def get_assignment(
        db: AsyncSession,
        assignment_id: int,
    ) -> Optional[TaskAssignment]:
        """Get an assignment by ID."""
        result = await db.execute(
            select(TaskAssignment).where(TaskAssignment.id == assignment_id)
        )
        return result.scalar_one_or_none()
    
    @staticmethod
    async def get_user_assignments(
        db: AsyncSession,
        user_id: int,
        status: Optional[AssignmentStatus] = None,
    ) -> list[TaskAssignment]:
        """Get all assignments for a user."""
        query = select(TaskAssignment).where(TaskAssignment.user_id == user_id)
        
        if status:
            query = query.where(TaskAssignment.status == status)
            
        query = query.order_by(TaskAssignment.assigned_at.desc())
        
        result = await db.execute(query)
        return list(result.scalars().all())
    
    @staticmethod
    async def complete_assignment(
        db: AsyncSession,
        task_id: int,
        user_id: int,
        notes: Optional[str] = None,
    ) -> Optional[TaskAssignment]:
        """
        Mark an assignment as complete.
        
        Args:
            db: Database session
            task_id: ID of the task
            user_id: ID of the user completing their assignment
            notes: Optional completion notes
            
        Returns:
            The updated TaskAssignment or None if not found
        """
        # Find the assignment
        result = await db.execute(
            select(TaskAssignment).where(
                TaskAssignment.task_id == task_id,
                TaskAssignment.user_id == user_id
            )
        )
        assignment = result.scalar_one_or_none()
        
        if not assignment:
            logger.warning(f"[Automation] Assignment not found: task={task_id}, user={user_id}")
            return None
        
        if assignment.status == AssignmentStatus.done:
            logger.warning(f"[Automation] Assignment already completed: task={task_id}, user={user_id}")
            return assignment
        
        # Update assignment
        assignment.status = AssignmentStatus.done
        assignment.completed_at = datetime.utcnow()
        if notes:
            assignment.notes = notes
        
        # Log the completion
        await AutomationService._log_event(
            db=db,
            task_id=task_id,
            user_id=user_id,
            event_type=TaskEventType.step_completed,
            metadata={"assignment_id": assignment.id, "notes": notes}
        )
        
        await db.commit()
        await db.refresh(assignment)
        
        logger.info(f"[Automation] Assignment completed: task={task_id}, user={user_id}")
        
        # Check if all assignments are done
        await AutomationService.close_task_if_all_done(db, task_id)
        
        return assignment
    
    @staticmethod
    async def close_task_if_all_done(
        db: AsyncSession,
        task_id: int,
    ) -> bool:
        """
        Close the task if all assignments are completed.
        
        Returns:
            True if task was closed, False otherwise
        """
        task = await AutomationService.get_task(db, task_id, include_assignments=True)
        if not task:
            return False
        
        # Already completed or cancelled
        if task.status in (AutomationTaskStatus.completed, AutomationTaskStatus.cancelled):
            return False
        
        # Check if there are any assignments
        if not task.assignments:
            return False
        
        # Check if all non-skipped assignments are done
        pending_count = sum(
            1 for a in task.assignments 
            if a.status not in (AssignmentStatus.done, AssignmentStatus.skipped)
        )
        
        if pending_count == 0:
            task.status = AutomationTaskStatus.completed
            
            await AutomationService._log_event(
                db=db,
                task_id=task_id,
                user_id=None,  # System action
                event_type=TaskEventType.closed,
                metadata={"reason": "all_assignments_completed"}
            )
            
            await db.commit()
            
            logger.info(f"[Automation] Task {task_id} auto-closed: all assignments completed")
            
            # Phase 6.4: Send auto-close notification
            try:
                from app.automation.notification_hooks import on_task_auto_closed
                await on_task_auto_closed(db, task, "all assignments completed")
            except Exception as e:
                logger.error(f"[Automation] Failed to send auto-close notification: {e}")
            
            return True
        
        return False
    
    # ---------------------- Event Logging ----------------------
    
    @staticmethod
    async def _log_event(
        db: AsyncSession,
        task_id: int,
        user_id: Optional[int],
        event_type: TaskEventType,
        metadata: Optional[dict[str, Any]] = None,
    ) -> TaskEvent:
        """
        Log a task event for audit purposes.
        """
        event = TaskEvent(
            task_id=task_id,
            user_id=user_id,
            event_type=event_type,
            event_metadata=json.dumps(metadata) if metadata else None,
        )
        db.add(event)
        await db.flush()
        return event
    
    @staticmethod
    async def get_task_events(
        db: AsyncSession,
        task_id: int,
    ) -> list[TaskEvent]:
        """Get all events for a task."""
        result = await db.execute(
            select(TaskEvent)
            .where(TaskEvent.task_id == task_id)
            .order_by(TaskEvent.created_at)
        )
        return list(result.scalars().all())
    
    # ---------------------- Permission Checks ----------------------
    
    @staticmethod
    async def can_manage_task(
        db: AsyncSession,
        task_id: int,
        user_id: int,
    ) -> bool:
        """
        Check if a user can manage (modify) a task.
        Returns True if user is the creator or a system admin.
        """
        task = await AutomationService.get_task(db, task_id, include_assignments=False)
        if not task:
            return False
        
        # Creator can manage
        if task.created_by_id == user_id:
            return True
        
        # Check if user is system admin
        result = await db.execute(
            select(User).where(User.id == user_id)
        )
        user = result.scalar_one_or_none()
        
        return user and user.is_system_admin
    
    @staticmethod
    async def is_assigned_to_task(
        db: AsyncSession,
        task_id: int,
        user_id: int,
    ) -> bool:
        """Check if a user is assigned to a task."""
        result = await db.execute(
            select(TaskAssignment).where(
                TaskAssignment.task_id == task_id,
                TaskAssignment.user_id == user_id
            )
        )
        return result.scalar_one_or_none() is not None
