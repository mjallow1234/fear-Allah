"""
Automation Engine Service Layer (Phase 6.1)
Core business logic for task-based workflow automation.
Phase 6.4 - Integrated notification hooks.
Phase 6.5 - Make.com webhook integration.
"""
import json
from datetime import datetime, timezone
from typing import Optional, Any

from sqlalchemy import select, func, update
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
from app.automation.payloads import (
    build_task_created_payload,
    build_task_completed_payload,
    build_automation_triggered_payload,
    build_automation_failed_payload,
)
from app.integrations.make_webhook import emit_make_webhook


class ClaimError(Exception):
    """Base exception for claim-related failures."""


class ClaimConflictError(ClaimError):
    """Raised when a task is already claimed by someone else."""


class ClaimPermissionError(ClaimError):
    """Raised when a user is not permitted to claim a task."""


class ClaimNotFoundError(ClaimError):
    """Raised when a task to claim does not exist."""


class AutomationService:
    """
    Service layer for the automation engine.
    Provides methods for task lifecycle management.
    """
    
    @staticmethod
    async def claim_task(
        db: AsyncSession,
        task_id: int,
        user_id: int,
        override: bool = False,
    ) -> AutomationTask:
        """
        Atomically claim a task (OPEN -> CLAIMED) for a user.

        - Uses SELECT ... FOR UPDATE to lock the task row.
        - Enforces `required_role` if set on the task.
        - Allows system admins to override an existing claim when `override=True`.
        - Raises ClaimConflictError on double-claim without override.
        - Raises ClaimPermissionError when user role doesn't match required_role.
        - Emits TaskEvent and writes an AuditLog entry.
        """
        from app.audit.logger import log_audit

        # Lock the task row for update to prevent races
        result = await db.execute(
            select(AutomationTask).where(AutomationTask.id == task_id).with_for_update()
        )
        task = result.scalar_one_or_none()
        if not task:
            raise ClaimNotFoundError("Task not found")

        # Resolve user and check permissions
        user_result = await db.execute(select(User).where(User.id == user_id))
        user = user_result.scalar_one_or_none()
        if not user:
            raise ClaimPermissionError("User not found")

        # Enforce required_role if present
        if task.required_role and (user.role != task.required_role) and not user.is_system_admin:
            await log_audit(db, user, action="claim", resource="automation_task", resource_id=task.id, success=False, reason="permission_denied")
            raise ClaimPermissionError("User does not have required role to claim this task")

        # If task is already claimed by the same user, treat as idempotent success
        if task.status == AutomationTaskStatus.claimed and task.claimed_by_user_id == user_id:
            return task

        # If the task is CLAIMED by someone else and no override requested -> conflict
        if task.status == AutomationTaskStatus.claimed and task.claimed_by_user_id and task.claimed_by_user_id != user_id and not (user.is_system_admin and override):
            await log_audit(db, user, action="claim", resource="automation_task", resource_id=task.id, success=False, reason="already_claimed")
            raise ClaimConflictError("Task already claimed by another user")

        # Proceed with atomic update to claim the task (guards against races)
        user_result = await db.execute(select(User).where(User.id == user_id))
        user = user_result.scalar_one_or_none()
        if not user:
            raise ClaimPermissionError("User not found")

        # Enforce required_role if present
        if task.required_role and (user.role != task.required_role) and not user.is_system_admin:
            await log_audit(db, user, action="claim", resource="automation_task", resource_id=task.id, success=False, reason="permission_denied")
            raise ClaimPermissionError("User does not have required role to claim this task")

        # If another user already claimed - conflict unless admin override
        if task.claimed_by_user_id and task.claimed_by_user_id != user_id:
            if not (user.is_system_admin and override):
                await log_audit(db, user, action="claim", resource="automation_task", resource_id=task.id, success=False, reason="already_claimed")
                raise ClaimConflictError("Task already claimed by another user")

            # Admin override - record reassignment event
            prev = task.claimed_by_user_id
            task.claimed_by_user_id = user_id
            task.claimed_at = datetime.now(timezone.utc)
            task.status = AutomationTaskStatus.claimed

            await AutomationService._safe_log_event(
                db=db,
                task_id=task.id,
                user_id=user_id,
                event_type=TaskEventType.task_reassigned,
                metadata={"from_user_id": prev, "to_user_id": user_id}
            )

            await log_audit(db, user, action="claim_override", resource="automation_task", resource_id=task.id, success=True, reason="override")

            # Notify previous claimer, new assignee, other admins
            try:
                from app.services.notifications import notify_task_reassigned
                await notify_task_reassigned(db=db, task_id=task.id, task_title=task.title, from_user_id=prev, to_user_id=user_id)
            except Exception as e:
                logger.warning(f"[Automation] Failed to notify on task.reassigned: {e}")

            await db.commit()
            await db.refresh(task)
            return task

        # Normal claim path — perform an atomic UPDATE so concurrent claim attempts race on the DB
        now = datetime.now(timezone.utc)
        update_stmt = (
            update(AutomationTask)
            .where(
                AutomationTask.id == task.id,
                AutomationTask.status == AutomationTaskStatus.open,
                AutomationTask.claimed_by_user_id == None,
            )
            .values(claimed_by_user_id=user_id, claimed_at=now, status=AutomationTaskStatus.claimed)
        )
        res = await db.execute(update_stmt)

        if res.rowcount == 0:
            # Someone else won the race
            await log_audit(db, user, action="claim", resource="automation_task", resource_id=task.id, success=False, reason="race_conflict")
            raise ClaimConflictError("Task already claimed")

        # Log event and audit for successful claim
        await AutomationService._safe_log_event(
            db=db,
            task_id=task.id,
            user_id=user_id,
            event_type=TaskEventType.task_claimed,
            metadata={"action": "claim"}
        )

        await log_audit(db, user, action="claim", resource="automation_task", resource_id=task.id, success=True)

        # Notify other role members and admins about the claim
        try:
            from app.services.notifications import notify_task_claimed
            await notify_task_claimed(db=db, task_id=task.id, task_title=task.title, claimer_id=user_id, required_role=task.required_role)
        except Exception as e:
            logger.warning(f"[Automation] Failed to notify on task.claimed: {e}")

        # Commit and verify we still hold the claim (detect races where another committer overwrote us)
        await db.commit()
        await db.refresh(task)
        if task.claimed_by_user_id != user_id:
            # Lost the race
            await log_audit(db, user, action="claim", resource="automation_task", resource_id=task.id, success=False, reason="lost_race")
            raise ClaimConflictError("Task was claimed by another user")

        return task

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
        required_role: Optional[str] = None,
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
            status=(AutomationTaskStatus.open if required_role else AutomationTaskStatus.pending),
            title=title,
            description=description,
            created_by_id=created_by_id,
            related_order_id=related_order_id,
            task_metadata=json.dumps(metadata) if metadata else None,
            required_role=required_role,
        )
        db.add(task)
        await db.flush()  # Get the ID
        
        # Log the creation event
        # Persist creation event directly to avoid relying on runtime mutation of class attributes
        event = TaskEvent(
            task_id=task.id,
            user_id=created_by_id,
            event_type=TaskEventType.created,
            event_metadata=json.dumps({"title": title, "task_type": task_type.value}),
        )
        db.add(event)
        await db.flush()
        
        await db.commit()
        
        # Reload with relationships
        result = await db.execute(
            select(AutomationTask)
            .options(selectinload(AutomationTask.assignments))
            .where(AutomationTask.id == task.id)
        )
        task = result.scalar_one()
        
        logger.info(f"[Automation] Task {task.id} created: {title} (type={task_type.value})")
        
        # Emit Make.com webhook for task.created event
        try:
            # Get creator username for payload
            creator_username = None
            if created_by_id:
                user_result = await db.execute(select(User).where(User.id == created_by_id))
                creator = user_result.scalar_one_or_none()
                creator_username = creator.username if creator else None
            
            payload = build_task_created_payload(
                task_id=task.id,
                title=title,
                related_order_id=related_order_id,
                actor_user_id=created_by_id,
                actor_username=creator_username,
            )
            await emit_make_webhook(payload)
        except Exception as e:
            logger.warning(f"[Automation] Failed to emit task.created webhook: {e}")

        # If task has required_role, emit TASK_OPENED event and notify role members + admins
        if task.required_role:
            await AutomationService._safe_log_event(
                db=db,
                task_id=task.id,
                user_id=created_by_id,
                event_type=TaskEventType.task_opened,
                metadata={"required_role": task.required_role}
            )
            try:
                from app.services.notifications import notify_task_opened
                await notify_task_opened(db=db, task_id=task.id, task_title=task.title, required_role=task.required_role)
            except Exception as e:
                logger.warning(f"[Automation] Failed to notify on task.opened: {e}")

        # If this task is linked to an order, ensure template assignments are created.
        # This covers cases where tasks are created via API or other services without
        # the OrderAutomationTriggers helper (ensures assignments for foreman/delivery/requester).
        if related_order_id:
            try:
                from app.automation.order_triggers import ORDER_TASK_TEMPLATES, OrderAutomationTriggers
                from app.db.models import Order
                from app.db.enums import OrderType
                # Load the order to determine its type
                res = await db.execute(select(Order).where(Order.id == related_order_id))
                order = res.scalar_one_or_none()
                if order:
                    order_type = order.order_type.value if isinstance(order.order_type, OrderType) else order.order_type
                    template = ORDER_TASK_TEMPLATES.get(order_type)
                    if template:
                            # Only create assignments if none exist yet
                            if not task.assignments or len(task.assignments) == 0:
                                # Prefer the order creator as the 'created_by' for template assignment logic
                                cb = getattr(order, 'created_by_id', None) or created_by_id
                                await OrderAutomationTriggers._create_template_assignments(
                                    db=db,
                                    task=task,
                                    template=template,
                                    created_by_id=cb,
                                )
                                # Refresh task to include new assignments
                                result = await db.execute(
                                    select(AutomationTask).options(selectinload(AutomationTask.assignments)).where(AutomationTask.id == task.id)
                                )
                                task = result.scalar_one()
            except Exception as e:
                logger.warning(f"[Automation] Failed to auto-create assignments for related_order {related_order_id}: {e}")

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

        For non-admin users, include tasks they created OR tasks where they have a TaskAssignment.
        Use DISTINCT to avoid duplicates and preserve pagination.
        """
        from sqlalchemy import or_, exists
        from app.db.models import TaskAssignment

        query = select(AutomationTask).options(selectinload(AutomationTask.assignments))
        
        if status:
            query = query.where(AutomationTask.status == status)
        if task_type:
            query = query.where(AutomationTask.task_type == task_type)

        # If created_by_id is provided, we want tasks created by the user OR assigned to the user
        # Use EXISTS subquery instead of JOIN + DISTINCT to avoid dialect-specific DISTINCT ON issues
        if created_by_id:
            assignment_exists = (
                select(TaskAssignment.id)
                .where(TaskAssignment.task_id == AutomationTask.id)
                .where(TaskAssignment.user_id == created_by_id)
            )

            query = query.where(
                or_(
                    AutomationTask.created_by_id == created_by_id,
                    exists(assignment_exists),
                )
            )

        # Apply ordering and pagination
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
        await AutomationService._safe_log_event(
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
        
        # Check if assignment already exists for the same (task, user, role_hint).
        # This allows multiple placeholder assignments (user_id=None) for different role_hints.
        existing = await db.execute(
            select(TaskAssignment).where(
                TaskAssignment.task_id == task_id,
                TaskAssignment.user_id == user_id,
                TaskAssignment.role_hint == role_hint,
            )
        )
        if existing.scalar_one_or_none():
            if user_id is None:
                logger.warning(f"[Automation] Placeholder already assigned for role '{role_hint}' on task {task_id}")
            else:
                logger.warning(f"[Automation] User {user_id} already assigned to task {task_id} (role={role_hint})")
            return None

        # If we're assigning a concrete user and a placeholder exists for the same role_hint,
        # update that placeholder row to bind it to the concrete user (fix wrong assignments).
        if user_id is not None and role_hint:
            ph_q = await db.execute(
                select(TaskAssignment).where(
                    TaskAssignment.task_id == task_id,
                    TaskAssignment.role_hint == role_hint,
                    TaskAssignment.user_id == None,
                ).order_by(TaskAssignment.id)
            )
            placeholder = ph_q.scalar_one_or_none()
            if placeholder:
                placeholder.user_id = user_id
                placeholder.notes = notes or placeholder.notes
                db.add(placeholder)
                await db.flush()

                # Refresh task status and log event as usual
                task = await AutomationService.get_task(db, task_id, include_assignments=False)
                if task and task.status == AutomationTaskStatus.pending:
                    task.status = AutomationTaskStatus.in_progress

                evt = TaskEvent(
                    task_id=task_id,
                    user_id=assigned_by_id,
                    event_type=TaskEventType.assigned,
                    event_metadata=json.dumps({"assigned_user_id": user_id, "role_hint": role_hint}),
                )
                db.add(evt)
                await db.commit()
                await db.refresh(placeholder)

                logger.info(f"[Automation] Placeholder assignment {placeholder.id} bound to user {user_id} (role={role_hint})")
                return placeholder
        
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
        # Persist assignment event directly to avoid runtime attr dependency
        evt = TaskEvent(
            task_id=task_id,
            user_id=assigned_by_id,
            event_type=TaskEventType.assigned,
            event_metadata=json.dumps({"assigned_user_id": user_id, "role_hint": role_hint}),
        )
        db.add(evt)
        await db.flush()
        
        await db.commit()
        await db.refresh(assignment)
        
        logger.info(f"[Automation] User {user_id} assigned to task {task_id} (role={role_hint})")
        
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
        assignment_id: Optional[int] = None,
    ) -> Optional[TaskAssignment]:
        """
        Mark an assignment as complete.
        
        Validates that the corresponding workflow task (based on role_hint) is active
        before allowing completion. This enforces strict task ordering.
        
        Args:
            db: Database session
            task_id: ID of the automation task
            user_id: ID of the user completing their assignment
            notes: Optional completion notes
            
        Returns:
            The updated TaskAssignment or None if not found
        """
        # Find the assignment (prefer explicit assignment_id when provided)
        if assignment_id is not None:
            result = await db.execute(
                select(TaskAssignment).where(TaskAssignment.id == assignment_id)
            )
        else:
            # If the actor is a system admin, they are allowed to complete any assignment
            # for the task; select the first non-done assignment for the task.
            actor_result = await db.execute(select(User).where(User.id == user_id))
            actor = actor_result.scalar_one_or_none()
            is_admin = bool(actor and getattr(actor, 'is_system_admin', False))

            if is_admin:
                result = await db.execute(
                    select(TaskAssignment).where(
                        TaskAssignment.task_id == task_id,
                        TaskAssignment.status != AssignmentStatus.done,
                    ).order_by(TaskAssignment.id)
                )
            else:
                result = await db.execute(
                    select(TaskAssignment).where(
                        TaskAssignment.task_id == task_id,
                        TaskAssignment.user_id == user_id
                    )
                )

        # Use .scalars().first() to safely pick the first matching row (avoids MultipleResultsFound)
        assignment = result.scalars().first()

        logger.info(f"[Automation] DEBUG complete_assignment start: task={task_id}, user_id={user_id}, assignment_id={assignment_id}, is_admin={is_admin}")
        logger.info(f"[Automation] DEBUG selected assignment: {getattr(assignment, 'id', None)} user_id={getattr(assignment, 'user_id', None)} status={getattr(assignment, 'status', None)} role_hint={getattr(assignment, 'role_hint', None)}")

        if not assignment:
            logger.warning(f"[Automation] Assignment not found: task={task_id}, user={user_id}, assignment_id={assignment_id}")
            raise ValueError("Assignment not found")
        
        if assignment.status == AssignmentStatus.done:
            logger.warning(f"[Automation] Assignment already completed: task={task_id}, user={user_id}")
            return assignment

        try:
            # Determine if the actor is a system admin to allow bypassing workflow restrictions
            actor_result = await db.execute(select(User).where(User.id == user_id))
            actor = actor_result.scalar_one_or_none()
            is_admin = bool(actor and getattr(actor, 'is_system_admin', False))

            # --- Enforce workflow task ordering and auto-advance workflow ---
            # Check if the automation task is linked to an order and validate workflow task status
            from app.db.models import Task, AutomationTask
            from app.db.enums import TaskStatus
            from app.services.task_engine import complete_task as engine_complete_task
            
            automation_task_result = await db.execute(
                select(AutomationTask).where(AutomationTask.id == task_id)
            )
            automation_task = automation_task_result.scalar_one_or_none()
            
            workflow_task_to_complete = None
            has_more_steps = False  # Track if user has more workflow steps after current one
            
            if automation_task and automation_task.related_order_id and not is_admin:
                # Map role_hint to workflow step_key(s)
                # Each role is responsible for specific workflow steps
                role_to_steps = {
                    "foreman": ["assemble_items", "foreman_handover"],  # Foreman: assembles, then hands over to delivery
                    "delivery": ["delivery_received", "deliver_items", "accept_delivery"],  # Delivery: confirms receipt, then delivers
                    "requester": ["confirm_received"],  # Requester confirms final receipt
                }
                
                role_hint = assignment.role_hint
                allowed_steps = role_to_steps.get(role_hint, [])
                
                if allowed_steps:
                    # Find the ACTIVE workflow task that matches this role's responsibilities
                    step_result = await db.execute(
                        select(Task).where(
                            Task.order_id == automation_task.related_order_id,
                            Task.step_key.in_(allowed_steps)
                        ).order_by(Task.id)
                    )
                    role_tasks = step_result.scalars().all()
                    
                    # Find active task for this role
                    active_task_for_role = None
                    for t in role_tasks:
                        if t.status == TaskStatus.active or t.status == TaskStatus.active.value:
                            active_task_for_role = t
                            break
                    
                    if not active_task_for_role:
                        # Check what the current active task is for better error message
                        active_result = await db.execute(
                            select(Task).where(Task.order_id == automation_task.related_order_id)
                        )
                        all_tasks = active_result.scalars().all()
                        current_active = None
                        for t in all_tasks:
                            if t.status == TaskStatus.active or t.status == TaskStatus.active.value:
                                current_active = t
                                break
                        
                        current_step = current_active.title if current_active else "No active step"
                        current_key = current_active.step_key if current_active else "none"
                        
                        # Give helpful error message
                        if role_hint == "foreman":
                            raise PermissionError(f"Cannot complete yet - 'Assemble Items' is not the active step. Current: '{current_step}'")
                        elif role_hint == "delivery":
                            raise PermissionError(f"Cannot complete yet - no delivery step is active. Current: '{current_step}'. Wait for foreman to complete assembly.")
                        else:
                            raise PermissionError(f"Cannot complete yet - your step is not active. Current: '{current_step}'")
                    
                    # Store the workflow task to complete after assignment is marked done
                    workflow_task_to_complete = active_task_for_role
                    logger.info(f"[Automation] Will complete workflow task: {workflow_task_to_complete.step_key} (id={workflow_task_to_complete.id})")
                    
                    # Check if there are more pending workflow steps for this role after the current one
                    # Count how many of this role's steps are NOT yet done
                    pending_role_steps = sum(
                        1 for t in role_tasks 
                        if t.status != TaskStatus.done and t.status != TaskStatus.done.value
                    )
                    # After we complete the current step, there will be (pending_role_steps - 1) remaining
                    has_more_steps = (pending_role_steps > 1)

            # -------------------------------------------------------------------------
            # Cross-role acknowledgment logic:
            # - Foreman's assignment marked DONE when delivery acknowledges receipt (delivery_received)
            # - Delivery's assignment marked DONE when agent acknowledges receipt (confirm_received)
            # -------------------------------------------------------------------------
            now = datetime.utcnow()
            
            # Determine what acknowledgment step this is and if we should mark another role's assignment DONE
            acknowledges_role = None  # Which role's assignment gets marked DONE by this step
            if workflow_task_to_complete:
                step_key = workflow_task_to_complete.step_key
                # Delivery acknowledging receipt from foreman -> marks foreman DONE
                if step_key == "delivery_received":
                    acknowledges_role = "foreman"
                # Agent/requester acknowledging final receipt -> marks delivery DONE
                elif step_key == "confirm_received":
                    acknowledges_role = "delivery"
            
            # Mark the acknowledged role's assignment as DONE
            if acknowledges_role and automation_task:
                # Find the assignment for the acknowledged role
                ack_result = await db.execute(
                    select(TaskAssignment).where(
                        TaskAssignment.task_id == task_id,
                        TaskAssignment.role_hint == acknowledges_role
                    )
                )
                ack_assignment = ack_result.scalar_one_or_none()
                if ack_assignment and ack_assignment.status != AssignmentStatus.done:
                    await db.execute(
                        update(TaskAssignment)
                        .where(TaskAssignment.id == ack_assignment.id)
                        .values(status=AssignmentStatus.done, completed_at=now)
                    )
                    logger.info(f"[Automation] Cross-role acknowledgment: {role_hint} acknowledged receipt, marking {acknowledges_role}'s assignment as DONE")
        except Exception:
            logger.exception("Error completing assignment")
            raise
        
        # For the current user's assignment:
        # - Don't mark as DONE until the NEXT role acknowledges receipt
        # - Keep as IN_PROGRESS while completing steps
        # Only mark DONE if:
        #   1. This is the final step in the workflow (requester's confirm_received)
        #   2. Or no workflow info available (fallback)
        should_mark_done = False
        
        if workflow_task_to_complete:
            step_key = workflow_task_to_complete.step_key
            # Only the final acknowledgment step marks its own assignment DONE immediately
            if step_key == "confirm_received":
                should_mark_done = True
        elif not automation_task or not automation_task.related_order_id:
            # No workflow - fallback to old behavior
            should_mark_done = True
        
        if should_mark_done:
            # Mark assignment as DONE
            if is_admin:
                # System admins can complete any assignment regardless of ownership
                upd = (
                    update(TaskAssignment)
                    .where(TaskAssignment.id == assignment.id)
                    .where(TaskAssignment.status != AssignmentStatus.done)
                    .values(status=AssignmentStatus.done, completed_at=now)
                )
            else:
                upd = (
                    update(TaskAssignment)
                    .where(TaskAssignment.id == assignment.id)
                    .where(TaskAssignment.user_id == user_id)
                    .where(TaskAssignment.status != AssignmentStatus.done)
                    .values(status=AssignmentStatus.done, completed_at=now)
                )
        else:
            # Keep assignment as IN_PROGRESS (waiting for next role to acknowledge)
            if is_admin:
                upd = (
                    update(TaskAssignment)
                    .where(TaskAssignment.id == assignment.id)
                    .values(status=AssignmentStatus.in_progress)
                )
            else:
                upd = (
                    update(TaskAssignment)
                    .where(TaskAssignment.id == assignment.id)
                    .where(TaskAssignment.user_id == user_id)
                    .values(status=AssignmentStatus.in_progress)
                )
        logger.info(f"[Automation] DEBUG executing update for assignment={assignment.id}, is_admin={is_admin}, should_mark_done={should_mark_done}")
        res = await db.execute(upd)
        logger.info(f"[Automation] DEBUG update rowcount={getattr(res, 'rowcount', None)} for assignment={assignment.id}")
        if res.rowcount == 0:
            # Could be concurrent modification or permission issue
            logger.warning(f"[Automation] Failed to update assignment row: task={task_id}, assignment={assignment.id}")
            raise RuntimeError("Failed to complete assignment")

        # Log the completion event
        evt = TaskEvent(
            task_id=task_id,
            user_id=user_id,
            event_type=TaskEventType.step_completed,
            event_metadata=json.dumps({"assignment_id": assignment.id, "notes": notes}),
        )
        db.add(evt)
        await db.flush()
        
        # --- Complete the corresponding workflow task to advance the order ---
        if workflow_task_to_complete:
            try:
                logger.info(f"[Automation] Advancing workflow: completing task {workflow_task_to_complete.id} ({workflow_task_to_complete.step_key})")
                await engine_complete_task(db, workflow_task_to_complete.id, user_id)
                logger.info(f"[Automation] Workflow advanced: {workflow_task_to_complete.step_key} completed")
            except Exception as e:
                logger.warning(f"[Automation] Failed to advance workflow task: {e}")
                # Don't fail the assignment completion if workflow fails
                # The assignment is still marked done

        await db.commit()
        # Refresh the assignment object
        await db.refresh(assignment)

        logger.info(f"[Automation] Assignment completed: task={task_id}, user={user_id}, assignment_id={assignment.id}")

        # Emit Make.com webhook for task.completed event
        try:
            # Get user info for payload
            user_result = await db.execute(select(User).where(User.id == user_id))
            completing_user = user_result.scalar_one_or_none()
            username = completing_user.username if completing_user else "unknown"
            
            payload = build_task_completed_payload(
                task_id=task_id,
                completed_by_user_id=user_id,
                completed_by_username=username,
                completed_at=now,
            )
            await emit_make_webhook(payload)
        except Exception as e:
            logger.warning(f"[Automation] Failed to emit task.completed webhook: {e}")

        # Check if all assignments are done and optionally close task
        closed = await AutomationService.close_task_if_all_done(db, task_id)
        if closed:
            logger.info(f"[Automation] Task {task_id} closed after all assignments completed")

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
            
            # Persist closed event directly to avoid runtime attr dependency
            evt = TaskEvent(
                task_id=task_id,
                user_id=None,
                event_type=TaskEventType.closed,
                event_metadata=json.dumps({"reason": "all_assignments_completed"}),
            )
            db.add(evt)
            await db.flush()
            
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
    async def _safe_log_event(
        db: AsyncSession,
        task_id: int,
        user_id: Optional[int],
        event_type: TaskEventType,
        metadata: Optional[dict[str, Any]] = None,
    ) -> TaskEvent:
        """
        Ensures a TaskEvent is logged even if the underlying _log_event attribute is missing
        due to import ordering or other runtime mutation.
        """
        fn = getattr(AutomationService, '_log_event', None)
        if fn:
            return await fn(db=db, task_id=task_id, user_id=user_id, event_type=event_type, metadata=metadata)

        # Fallback - create the TaskEvent directly
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


async def trigger_event(db: AsyncSession, event_type: str, context: dict, dry_run: bool = False) -> None:
    """Trigger a named automation event for testing or external triggers.

    When dry_run=True this helper will NOT mutate the database and will only log the event.
    When dry_run=False it will create a simple automation task for testing the event trigger.
    
    Also emits Make.com webhook for automation.triggered event.
    """
    title = f"Test event: {event_type}"
    metadata = {"event_type": event_type, "context": context}

    if dry_run:
        # Do not persist anything during a dry-run; just log the event
        logger.info(f"[Automation] Dry-run trigger event '{event_type}' (no DB changes)")
        return

    # Create a simple automation task for testing the event trigger
    task = None
    try:
        task = await AutomationService.create_task(
            db=db,
            task_type=AutomationTaskType.custom,
            title=title,
            created_by_id=context.get('user_id') or 0,
            description=f"Trigger event {event_type}",
            metadata=metadata
        )
        logger.info(f"[Automation] Trigger event '{event_type}' executed")
        
        # Emit Make.com webhook for automation.triggered event
        try:
            payload = build_automation_triggered_payload(
                automation_task_id=task.id,
                rule=f"trigger_{event_type}",
                trigger_event=event_type,
                status="executed",
            )
            await emit_make_webhook(payload)
        except Exception as we:
            logger.warning(f"[Automation] Failed to emit automation.triggered webhook: {we}")
            
    except Exception as e:
        logger.warning(f"[Automation] Failed to trigger event {event_type}: {e}")
        
        # Emit automation.failed webhook
        try:
            payload = build_automation_failed_payload(
                entity_type="automation_event",
                entity_id=0,
                reason="trigger_failed",
                message=str(e),
                recoverable=True,
            )
            await emit_make_webhook(payload)
        except Exception as we:
            logger.warning(f"[Automation] Failed to emit automation.failed webhook: {we}")
        return