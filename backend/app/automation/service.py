"""
Automation Engine Service Layer (Phase 6.1)
Core business logic for task-based workflow automation.
Phase 6.4 - Integrated notification hooks.
Phase 6.5 - Make.com webhook integration.
"""
import json
from datetime import datetime, timezone
from typing import Optional, Any

from sqlalchemy import select, func, update, exists
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
from app.services.notification_emitter import (
    notify_and_emit_task_completed_to_participants,
    notify_and_emit_order_completed_to_participants,
)


class ClaimError(Exception):
    """Base exception for claim-related failures."""


class ClaimConflictError(ClaimError):
    """Raised when a task is already claimed by someone else."""


class ClaimPermissionError(ClaimError):
    """Raised when a user is not permitted to claim a task."""


class ClaimNotFoundError(ClaimError):
    """Raised when a task to claim does not exist."""


class ClaimInvalidStateError(ClaimError):
    """Raised when a claim is attempted on a task that is not in an open state."""


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

        # Resolve user and check minimal authorization
        user_result = await db.execute(select(User).where(User.id == user_id))
        user = user_result.scalar_one_or_none()
        if not user:
            raise ClaimPermissionError("User not found")

        # NOTE: Task claiming is global-role based. It intentionally does NOT depend on chat channels.
        # Authorization rules (only):
        # - Task must be OPEN or PENDING to be claimable (unless admin override)
        # - If task.required_role is set, user must have the global role or be a system admin

        # FRESH DB role resolution — do NOT use cached user.operational_roles or user.has_operational_role()
        # This ensures admin role changes take effect immediately without logout/token refresh
        from app.db.models import UserOperationalRole
        role_result = await db.execute(
            select(UserOperationalRole.role).where(UserOperationalRole.user_id == user.id)
        )
        user_roles = {row[0] for row in role_result}

        # Diagnostic logging for debugging role issues
        logger.info(
            "[CLAIM_ROLE_CHECK] user_id=%s roles=%s required_role=%s task_id=%s",
            user.id,
            sorted(user_roles),
            task.required_role,
            task.id,
        )

        # Role-based authorization (403) — resolved fresh from DB per request
        if task.required_role:
            if task.required_role not in user_roles and not user.is_system_admin:
                from app.audit.logger import log_audit
                await log_audit(
                    db,
                    user,
                    action="claim",
                    resource="automation_task",
                    resource_id=task.id,
                    success=False,
                    reason="missing_required_role",
                )
                raise ClaimPermissionError("User does not have required operational role to claim this task")

        # Handle current task status cases
        # Role-based claiming: reject if task is already claimed (regardless of who claimed it)
        # Only allow admin override to take over existing claims
        if task.status == AutomationTaskStatus.claimed:
            # If admin and override=True, allow override (handled below)
            if user.is_system_admin and override:
                # allow to continue to override path
                pass
            else:
                await log_audit(db, user, action="claim", resource="automation_task", resource_id=task.id, success=False, reason="already_claimed")
                raise ClaimConflictError("Task already claimed")

        # For any state that is not OPEN or PENDING (e.g., done) that is not an admin override, reject with 400
        if task.status not in (AutomationTaskStatus.open, AutomationTaskStatus.pending):
            if not (user.is_system_admin and override):
                raise ClaimInvalidStateError("Task is not open for claim")

        # Normal claim path — perform an atomic UPDATE so concurrent claim attempts race on the DB

        # Role-based claiming: if task is already claimed (by anyone), conflict unless admin override
        if task.claimed_by_user_id:
            if not (user.is_system_admin and override):
                await log_audit(db, user, action="claim", resource="automation_task", resource_id=task.id, success=False, reason="already_claimed")
                raise ClaimConflictError("Task already claimed")

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
                await notify_task_reassigned(
                    db=db,
                    task_id=task.id,
                    task_title=task.title,
                    from_user_id=prev,
                    to_user_id=user_id,
                    order_id=task.related_order_id,  # Pass order_id for participant-based notifications
                )
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
                AutomationTask.status.in_([AutomationTaskStatus.open, AutomationTaskStatus.pending]),
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

        # Create a TaskAssignment for the claimer so this claim is visible in their 'my assignments'
        try:
            # Avoid creating duplicate assignment if one exists
            existing_q = await db.execute(
                select(TaskAssignment).where(
                    TaskAssignment.task_id == task.id,
                    TaskAssignment.user_id == user_id,
                    TaskAssignment.role_hint == task.required_role,
                )
            )
            existing_assignment = existing_q.scalar_one_or_none()
            if not existing_assignment and task.required_role:
                new_assign = TaskAssignment(
                    task_id=task.id,
                    user_id=user_id,
                    role_hint=task.required_role,
                    status=AssignmentStatus.in_progress,
                )
                db.add(new_assign)

                # Log assignment event for the new assignment
                evt = TaskEvent(
                    task_id=task.id,
                    user_id=user_id,
                    event_type=TaskEventType.assigned,
                    event_metadata=json.dumps({"assigned_user_id": user_id, "role_hint": task.required_role}),
                )
                db.add(evt)
                await db.flush()
                logger.info(f"[Automation] Created assignment for claimer {user_id} on task {task.id} (role={task.required_role})")
        except Exception as e:
            logger.warning(f"[Automation] Failed to create assignment for claimer: {e}")

        # Notify other role members and admins about the claim
        try:
            from app.services.notifications import notify_task_claimed
            await notify_task_claimed(
                db=db,
                task_id=task.id,
                task_title=task.title,
                claimer_id=user_id,
                required_role=task.required_role,
                order_id=task.related_order_id,  # Pass order_id for participant-based notifications
            )
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
        is_order_root: bool = False,
        status: AutomationTaskStatus = AutomationTaskStatus.pending,
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
            status: Optional initial status for the task (default: pending)
            
        Returns:
            The created AutomationTask
        """
        task = AutomationTask(
            task_type=task_type,
            # Allow explicit initial status to be set by callers
            status=status,
            title=title,
            description=description,
            created_by_id=created_by_id,
            related_order_id=related_order_id,
            task_metadata=json.dumps(metadata) if metadata else None,
            required_role=required_role,
            is_order_root=is_order_root,
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

        # If task has required_role, mark it OPEN (claim-based workflow) and emit TASK_OPENED event.
        if task.required_role:
            # Ensure the task is OPEN and unclaimed so it can be claimed by users with the required global role.
            if task.status != AutomationTaskStatus.open:
                task.status = AutomationTaskStatus.open
                task.claimed_by_user_id = None
                db.add(task)
                await db.commit()
                await db.refresh(task)

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
        current_user: Optional[User] = None,
    ) -> list[AutomationTask]:
        pass

    @staticmethod
    async def _all_required_assignments_done(db: AsyncSession, automation_task_id: int) -> bool:
        """Return True if there are no remaining non-DONE/non-SKIPPED assignments for the automation task."""
        from app.db.models import TaskAssignment
        from app.db.enums import AssignmentStatus

        q = select(TaskAssignment.id).where(
            TaskAssignment.task_id == automation_task_id,
            TaskAssignment.status.notin_((AssignmentStatus.done, AssignmentStatus.skipped)),
        ).limit(1)
        res = await db.execute(q)
        return res.scalar_one_or_none() is None

    @staticmethod
    async def list_tasks(
        db: AsyncSession,
        status: Optional[AutomationTaskStatus] = None,
        task_type: Optional[AutomationTaskType] = None,
        created_by_id: Optional[int] = None,
        limit: int = 50,
        offset: int = 0,
        current_user: Optional[User] = None,
    ) -> list[AutomationTask]:
        """List tasks with optional filters.

        For non-admin users, include tasks they created OR tasks where they have a TaskAssignment.
        Use DISTINCT to avoid duplicates and preserve pagination.
        """
        """
        List tasks with optional filters.

        For non-admin users, include tasks they created OR tasks where they have a TaskAssignment.
        Use DISTINCT to avoid duplicates and preserve pagination.
        """
        from sqlalchemy import or_, exists, func
        from app.db.models import TaskAssignment

        # Determine user debug info (best-effort, do not change logic)
        user_id_debug = getattr(current_user, 'id', None)
        user_role_debug = getattr(current_user, 'role', None)
        user_is_admin_debug = getattr(current_user, 'is_system_admin', None)

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

            # Allow non-admin users to still see COMPLETED automation tasks for their operational role
            # (e.g., delivery users should see completed delivery tasks). This is a read-only, presentation
            # change that ensures users can observe completed tasks relevant to their role without
            # modifying workflows or assignments.
            role_val = getattr(current_user, 'role', None) if current_user is not None else None
            if role_val:
                from sqlalchemy import and_
                # Include tasks created by the user, tasks assigned to the user, OR completed tasks for their role
                query = query.where(
                    or_(
                        AutomationTask.created_by_id == created_by_id,
                        exists(assignment_exists),
                        and_(AutomationTask.required_role == role_val, AutomationTask.status == AutomationTaskStatus.completed),
                    )
                )
            else:
                query = query.where(
                    or_(
                        AutomationTask.created_by_id == created_by_id,
                        exists(assignment_exists),
                    )
                )

        # Compute total matches BEFORE pagination (do not modify returned results)
        # Build a simple count query with the same WHERE clauses
        count_q = select(func.count()).select_from(AutomationTask)
        # Apply same filters used above for count
        if status:
            count_q = count_q.where(AutomationTask.status == status)
        if task_type:
            count_q = count_q.where(AutomationTask.task_type == task_type)
        if created_by_id:
            assignment_exists = (
                select(TaskAssignment.id)
                .where(TaskAssignment.task_id == AutomationTask.id)
                .where(TaskAssignment.user_id == created_by_id)
            )
            role_val = getattr(current_user, 'role', None) if current_user is not None else None
            if role_val:
                from sqlalchemy import and_
                count_q = count_q.where(
                    or_(
                        AutomationTask.created_by_id == created_by_id,
                        exists(assignment_exists),
                        and_(AutomationTask.required_role == role_val, AutomationTask.status == AutomationTaskStatus.completed),
                    )
                )
            else:
                count_q = count_q.where(
                    or_(
                        AutomationTask.created_by_id == created_by_id,
                        exists(assignment_exists),
                    )
                )

        total_result = await db.execute(count_q)
        total_before_pagination = int(total_result.scalar_one())

        # Log debug information
        logger.info(f"[TASK-LIST-DEBUG] user_id={user_id_debug} role={user_role_debug} is_system_admin={user_is_admin_debug} limit={limit} offset={offset} total_before_pagination={total_before_pagination}")

        # Apply ordering and pagination
        query = query.order_by(AutomationTask.created_at.desc()).limit(limit).offset(offset)
        
        result = await db.execute(query)
        return list(result.scalars().all())

    @staticmethod
    async def available_tasks_for_role(
        db: AsyncSession,
        role: str,
        limit: int = 50,
        offset: int = 0,
    ) -> list[AutomationTask]:
        """Return tasks that are required for a role and currently unclaimed."""
        # Exclude tasks that already have any assignments — claiming must be the first assignment
        from sqlalchemy import select as _select
        # Only consider operational role assignments (e.g., foreman, delivery) when determining
        # whether a task is still 'available' to be claimed. Allow requester and other non-operational
        # assignments to exist without blocking claim availability.
        assignment_exists = (
            _select(TaskAssignment.id)
            .where(TaskAssignment.task_id == AutomationTask.id)
            .where(TaskAssignment.role_hint.in_(['foreman', 'delivery']))
        )

        query = (
            select(AutomationTask)
            .options(selectinload(AutomationTask.assignments))
            .where(AutomationTask.required_role == role)
            .where(AutomationTask.claimed_by_user_id == None)
            .where(~exists(assignment_exists))
            .order_by(AutomationTask.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
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
        
        # Before committing, if this task is being completed, ensure all assignments are marked DONE atomically
        if new_status == AutomationTaskStatus.completed:
            try:
                from app.db.models import TaskAssignment
                from app.db.enums import AssignmentStatus
                from datetime import datetime

                now = datetime.utcnow()
                await db.execute(
                    update(TaskAssignment)
                    .where(TaskAssignment.task_id == task_id)
                    .where(TaskAssignment.status != AssignmentStatus.done)
                    .values(status=AssignmentStatus.done, completed_at=now)
                )
                logger.info(f"[Automation] Auto-completed assignments for task {task_id} as part of task completion")
            except Exception as e:
                logger.warning(f"[Automation] Failed to auto-complete assignments for task {task_id}: {e}")

        await db.commit()
        await db.refresh(task)

        # If this was a DELIVERY task completion, ensure task closure and possibly close parent automation
        if new_status == AutomationTaskStatus.completed:
            try:
                if getattr(task, 'required_role', None) == 'delivery':
                    # Ensure delivery task closes if all assignments are done
                    try:
                        await AutomationService.close_task_if_all_done(db, task_id)
                    except Exception as e:
                        logger.warning(f"[Automation] close_task_if_all_done failed for delivery task {task_id}: {e}")

                    # Check if there are any remaining operational (foreman/delivery) tasks for the same order
                    if getattr(task, 'related_order_id', None):
                        from app.db.models import AutomationTask as AT
                        from app.db.enums import AutomationTaskStatus as ATS
                        res = await db.execute(
                            select(AT.id)
                            .where(
                                AT.related_order_id == task.related_order_id,
                                AT.required_role.in_(['foreman', 'delivery']),
                                ~AT.status.in_([ATS.completed, ATS.cancelled])
                            )
                            .limit(1)
                        )
                        remaining = res.scalar_one_or_none()
                        if not remaining:
                            # No more operational tasks remain — close the main order automation task if it's still open
                            try:
                                from app.automation.order_triggers import OrderAutomationTriggers
                                parent = await OrderAutomationTriggers._get_order_automation_task(db, task.related_order_id)
                                if parent and parent.id != task.id and parent.status not in (ATS.completed, ATS.cancelled):
                                    await AutomationService.update_task_status(db, parent.id, ATS.completed, user_id=None)
                            except Exception as e:
                                logger.warning(f"[Automation] Failed to close parent automation task for order {task.related_order_id}: {e}")
            except Exception as e:
                logger.warning(f"[Automation] Delivery completion post-processing failed: {e}")

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
        logger.info(
            "[DEBUG] complete_assignment ENTERED | assignment_id=%s | user_id=%s | task_id=%s",
            assignment_id,
            user_id,
            task_id,
        )
        # Define now early so it's available in all branches
        now = datetime.now(timezone.utc)

        # Determine admin status early so it's available in all branches
        is_admin = False
        actor = None
        user_roles = set()
        if user_id is not None:
            actor_result = await db.execute(select(User).where(User.id == user_id))
            actor = actor_result.scalar_one_or_none()
            is_admin = bool(actor and getattr(actor, 'is_system_admin', False))
            
            # FRESH DB role resolution — do NOT use cached user.operational_roles or user.has_operational_role()
            # This ensures admin role changes take effect immediately without logout/token refresh
            from app.db.models import UserOperationalRole
            role_result = await db.execute(
                select(UserOperationalRole.role).where(UserOperationalRole.user_id == user_id)
            )
            user_roles = {row[0] for row in role_result}
            
            # Diagnostic logging for debugging role issues
            logger.info(
                "[COMPLETE_ROLE_CHECK] user_id=%s roles=%s task_id=%s is_admin=%s",
                user_id,
                sorted(user_roles),
                task_id,
                is_admin,
            )

        # Find the assignment (prefer explicit assignment_id when provided)
        if assignment_id is not None:
            result = await db.execute(
                select(TaskAssignment).where(TaskAssignment.id == assignment_id)
            )
        else:
            # If the actor is a system admin, they are allowed to complete any assignment
            # for the task; select the first non-done assignment for the task.
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
            logger.info(
                "[DEBUG] complete_assignment RETURNING EARLY | assignment_id=%s | reason=assignment_not_found",
                assignment_id,
            )
            logger.warning(f"[Automation] Assignment not found: task={task_id}, user={user_id}, assignment_id={assignment_id}")
            raise ValueError("Assignment not found")
        
        if assignment.status == AssignmentStatus.done:
            logger.info(
                "[DEBUG] complete_assignment RETURNING EARLY | assignment_id=%s | reason=already_done",
                assignment.id,
            )
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
            
            # Mark the acknowledged role's assignment as DONE, but only if ALL workflow tasks for that role are done
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
                    try:
                        # Determine remaining workflow steps for the acknowledged role
                        from app.db.models import Task as OrderTask, Order
                        from app.services.task_engine import WORKFLOWS
                        # Load order to determine workflow
                        if getattr(automation_task, 'related_order_id', None):
                            order_res = await db.execute(select(Order).where(Order.id == automation_task.related_order_id))
                            order = order_res.scalar_one_or_none()
                            if order:
                                wf_def = WORKFLOWS.get(order.order_type, [])
                                role_steps = [s['step_key'] for s in wf_def if s.get('assigned_to') == acknowledges_role and s.get('required', True)]
                                if role_steps:
                                    from app.db.enums import TaskStatus as OrderTaskStatus
                                    remaining_q = select(OrderTask.id).where(
                                        OrderTask.order_id == order.id,
                                        OrderTask.step_key.in_(role_steps),
                                        OrderTask.status != OrderTaskStatus.done.value,
                                    ).limit(1)
                                    rem_res = await db.execute(remaining_q)
                                    has_remaining = rem_res.scalar_one_or_none() is not None
                                    remaining = has_remaining
                                else:
                                    remaining = None
                            else:
                                remaining = None
                        else:
                            remaining = None
                    except Exception:
                        remaining = None

                    if remaining is None:
                        # Fallback: if we cannot determine, do not block - mark done
                        await db.execute(
                            update(TaskAssignment)
                            .where(TaskAssignment.id == ack_assignment.id)
                            .values(status=AssignmentStatus.done, completed_at=now)
                        )
                        logger.info(f"[Automation] Cross-role acknowledgment: marking {acknowledges_role}'s assignment as DONE (fallback)")
                    elif remaining is False:
                        # No remaining steps for this role - mark assignment DONE
                        await db.execute(
                            update(TaskAssignment)
                            .where(TaskAssignment.id == ack_assignment.id)
                            .values(status=AssignmentStatus.done, completed_at=now)
                        )
                        logger.info(f"[Automation] Cross-role acknowledgment: {role_hint} acknowledged receipt, marking {acknowledges_role}'s assignment as DONE")
                    else:
                        logger.info(f"[Automation] Cross-role acknowledgment: {role_hint} acknowledged receipt, but {acknowledges_role} has remaining workflow steps; not marking assignment DONE")
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
        
        # Determine whether to mark the current assignment as DONE based on workflow role completion
        marked_done = False

        if is_admin:
            # System admins may force-complete an assignment
            upd = (
                update(TaskAssignment)
                .where(TaskAssignment.id == assignment.id)
                .where(TaskAssignment.status != AssignmentStatus.done)
                .values(status=AssignmentStatus.done, completed_at=now, notes=notes)
            )
            res = await db.execute(upd)
            marked_done = res.rowcount > 0
        else:
            # Regular users: mark DONE only if final step or all workflow tasks for their role are done
            can_mark_done = should_mark_done

            # If we have role_hint and an automation task linked to an order, compute remaining tasks for role
            role_hint = assignment.role_hint
            remaining = None
            if not can_mark_done and role_hint and automation_task and getattr(automation_task, 'related_order_id', None):
                try:
                    from app.db.models import Task as OrderTask, Order
                    from app.services.task_engine import WORKFLOWS

                    order_res = await db.execute(select(Order).where(Order.id == automation_task.related_order_id))
                    order = order_res.scalar_one_or_none()
                    if order:
                        wf_def = WORKFLOWS.get(order.order_type, [])
                        role_steps = [s['step_key'] for s in wf_def if s.get('assigned_to') == role_hint and s.get('required', True)]
                        if role_steps:
                            from app.db.enums import TaskStatus as OrderTaskStatus
                            remaining_q = select(OrderTask.id).where(
                                OrderTask.order_id == order.id,
                                OrderTask.step_key.in_(role_steps),
                                OrderTask.status != OrderTaskStatus.done.value,
                            ).limit(1)
                            rem_res = await db.execute(remaining_q)
                            has_remaining = rem_res.scalar_one_or_none() is not None
                            remaining = has_remaining
                except Exception as e:
                    logger.warning(f"[Automation] Failed to compute remaining workflow steps for role {role_hint}: {e}")

            # can_mark_done OR no remaining role tasks -> mark assignment done
            if can_mark_done or (remaining is False):
                # Mark assignment as done
                upd = (
                    update(TaskAssignment)
                    .where(TaskAssignment.id == assignment.id)
                    .where(TaskAssignment.user_id == user_id)
                    .where(TaskAssignment.status != AssignmentStatus.done)
                    .values(status=AssignmentStatus.done, completed_at=now, notes=notes)
                )
                res = await db.execute(upd)
                marked_done = res.rowcount > 0
            else:
                # Do not mark assignment done; update notes only to record activity
                upd = (
                    update(TaskAssignment)
                    .where(TaskAssignment.id == assignment.id)
                    .where(TaskAssignment.user_id == user_id)
                    .values(notes=notes)
                )
                await db.execute(upd)

        logger.info(f"[Automation] DEBUG update performed for assignment={assignment.id}, marked_done={marked_done}")

        if marked_done:
            logger.info(
                "[DEBUG] assignment marked DONE | assignment_id=%s | task_id=%s | task_required_role=%s",
                assignment.id,
                assignment.task_id,
                getattr(automation_task, 'required_role', None) if automation_task else None,
            )
            # Update in-memory assignment object to reflect completed status for downstream consumers
            try:
                from app.db.enums import AssignmentStatus as AS
                assignment.status = AS.done
                assignment.completed_at = now
                assignment.notes = notes
                db.add(assignment)
            except Exception:
                pass


        # Log the completion event
        evt = TaskEvent(
            task_id=task_id,
            user_id=user_id,
            event_type=TaskEventType.step_completed,
            event_metadata=json.dumps({"assignment_id": assignment.id, "notes": notes}),
        )
        db.add(evt)
        await db.flush()

        # === NOTIFY: Assignment completed → notify participants ===
        if marked_done and automation_task and automation_task.related_order_id:
            try:
                # Get actor username for notification content
                actor_username = actor.username if actor else "Someone"
                task_title = getattr(automation_task, 'title', None) or f"Task #{task_id}"
                await notify_and_emit_task_completed_to_participants(
                    db=db,
                    task_id=automation_task.id,
                    order_id=automation_task.related_order_id,
                    task_title=task_title,
                    completed_by=actor_username,
                )
                logger.info(f"[Automation] Emitted task_completed notification to participants for task={task_id}")
            except Exception as e:
                logger.warning(f"[Automation] Failed to emit task_completed notification: {e}")
        
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

            # If this was the foreman handover step, chain delivery task creation regardless of engine success
            try:
                if getattr(workflow_task_to_complete, 'step_key', None) == 'foreman_handover':
                    await AutomationService._maybe_chain_foreman_to_delivery(db, automation_task)
            except Exception as e:
                logger.warning(f"[Automation] Failed to chain foreman handover->delivery: {e}")

        await db.commit()
        # Refresh the assignment object
        await db.refresh(assignment)

        logger.info(f"[Automation] Assignment completed: task={task_id}, user={user_id}, assignment_id={assignment.id}")

        # CRITICAL: Evaluate order-root completion BEFORE any return.
        # This block runs unconditionally — fetch the order-root and complete if all assignments are done.
        # NO role checks, NO order-type checks, NO early returns between all_done and mutation.
        related_order_id = getattr(automation_task, 'related_order_id', None) if automation_task else None
        if related_order_id:
            from app.db.models import AutomationTask as ATModel, Order as OrderModel
            from app.db.enums import AutomationTaskStatus as ATS, OrderStatus as OS

            # Fetch the order-root task for this order
            root_q = select(ATModel).where(ATModel.related_order_id == related_order_id, ATModel.is_order_root == True).limit(1)
            root_res = await db.execute(root_q)
            root_task = root_res.scalar_one_or_none()
            logger.error(
                "[ROOT-TRACE] root BEFORE evaluation | root_id=%s | status=%s",
                getattr(root_task, 'id', None) if root_task else None,
                getattr(root_task, 'status', None) if root_task else None,
            )

            if root_task:
                # Check if all required assignments on the root task are done
                all_done_root = await AutomationService._all_required_assignments_done(db, root_task.id)
                logger.error(
                    "[ROOT-TRACE] all_required_assignments_done=%s | root_id=%s",
                    all_done_root,
                    root_task.id,
                )

                # If all_done is True, ALWAYS complete — no extra conditions
                if all_done_root:
                    # Guard: For agent_retail, only complete after deliver_items step is done
                    order_res = await db.execute(select(OrderModel).where(OrderModel.id == related_order_id))
                    order_obj = order_res.scalar_one_or_none()
                    if order_obj:
                        from app.db.enums import OrderType as OT
                        from app.db.models import Task as WorkflowTask
                        from app.db.enums import TaskStatus as WTS
                        ot_val = order_obj.order_type.value if hasattr(order_obj.order_type, 'value') else order_obj.order_type
                        if ot_val == OT.agent_retail.value:
                            # Check if deliver_items step is still pending
                            pending_final_q = select(WorkflowTask).where(
                                WorkflowTask.order_id == order_obj.id,
                                WorkflowTask.step_key == "deliver_items",
                                WorkflowTask.status != WTS.done.value,
                            ).limit(1)
                            pending_final_res = await db.execute(pending_final_q)
                            pending_final_delivery = pending_final_res.scalar_one_or_none()
                            if pending_final_delivery:
                                logger.info(f"[Automation] agent_retail order {order_obj.id}: deliver_items not yet done, skipping root completion")
                                # Do NOT complete root yet — return assignment
                                return assignment

                    now_root = datetime.now(timezone.utc)
                    # Use ORM mutation instead of Core UPDATE to avoid CompileError
                    root_task.status = ATS.completed
                    root_task.completed_at = now_root
                    logger.error(
                        "[ROOT-TRACE] root MARKED COMPLETED | root_id=%s",
                        root_task.id,
                    )
                    # order_obj already fetched above; complete it
                    if order_obj:
                        order_obj.status = OS.completed

                    # Cascade completion to role-scoped automation tasks
                    # Find all non-root tasks for this order that are still open/claimed/in_progress
                    from app.db.models import TaskAssignment as TAModel
                    role_tasks_q = select(ATModel).where(
                        ATModel.related_order_id == related_order_id,
                        ATModel.is_order_root == False,
                        ATModel.status.in_([ATS.open, ATS.claimed, ATS.in_progress])
                    )
                    role_tasks_res = await db.execute(role_tasks_q)
                    role_tasks = role_tasks_res.scalars().all()
                    for rtask in role_tasks:
                        rtask.status = ATS.completed
                        rtask.completed_at = now_root
                        # Mark all assignments on this task as DONE
                        assign_q = select(TAModel).where(
                            TAModel.task_id == rtask.id,
                            TAModel.status.notin_([AssignmentStatus.done, AssignmentStatus.skipped])
                        )
                        assign_res = await db.execute(assign_q)
                        assigns = assign_res.scalars().all()
                        for a in assigns:
                            a.status = AssignmentStatus.done
                            a.completed_at = now_root
                        logger.info(f"[Automation] Cascade-completed role-scoped task {rtask.id} and {len(assigns)} assignments")

                    await db.commit()
                    logger.error(
                        "[ROOT-TRACE] TRANSACTION COMMITTED | root_id=%s",
                        root_task.id,
                    )
                    logger.info(f"[Automation] Marked order-root {root_task.id} COMPLETED and Order {related_order_id} COMPLETED as all root assignments are done")

                    # === NOTIFY: Task (root) completed → notify participants ===
                    try:
                        root_title = getattr(root_task, 'title', None) or f"Order Task #{root_task.id}"
                        actor_username = actor.username if actor else "System"
                        await notify_and_emit_task_completed_to_participants(
                            db=db,
                            task_id=root_task.id,
                            order_id=related_order_id,
                            task_title=root_title,
                            completed_by=actor_username,
                        )
                        logger.info(f"[Automation] Emitted root task_completed notification for task={root_task.id}")
                    except Exception as e:
                        logger.warning(f"[Automation] Failed to emit root task_completed notification: {e}")

                    # === NOTIFY: Order completed → notify ALL participants ===
                    if order_obj:
                        try:
                            order_reference = str(order_obj.id)
                            await notify_and_emit_order_completed_to_participants(
                                db=db,
                                order_id=order_obj.id,
                                order_reference=order_reference,
                            )
                            logger.info(f"[Automation] Emitted order_completed notification for order={order_obj.id}")
                        except Exception as e:
                            logger.warning(f"[Automation] Failed to emit order_completed notification: {e}")

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

        logger.error(
            "[ROOT-TRACE] EXIT complete_assignment | assignment_id=%s",
            assignment.id,
        )
        return assignment

    @staticmethod
    async def complete_assignment_by_assignment_id(
        db: AsyncSession,
        assignment_id: int,
        user_id: int,
        notes: Optional[str] = None,
    ):
        """
        Complete an assignment by its assignment id.

        Ensures the caller is the assigned user or a system admin. Delegates to
        the main assignment completion logic to avoid duplication and preserve
        workflow advancement behavior.
        """
        from app.db.models import TaskAssignment, User

        # Load assignment
        res = await db.execute(select(TaskAssignment).where(TaskAssignment.id == assignment_id))
        assignment = res.scalar_one_or_none()
        if not assignment:
            raise ValueError("Assignment not found")

        # Permission check: assigned user or system admin
        user_res = await db.execute(select(User).where(User.id == user_id))
        user = user_res.scalar_one_or_none()
        if assignment.user_id != user_id and not (user and user.is_system_admin):
            raise PermissionError("Not permitted to complete this assignment")

        # Delegate to existing task-scoped complete_assignment to keep behavior consistent
        return await AutomationService.complete_assignment(db=db, task_id=assignment.task_id, user_id=user_id, notes=notes)

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
            # Ensure any remaining assignments are marked DONE atomically (best-effort),
            # but do NOT change automation task status here. Automation completion is
            # driven by workflow completion (order/task engine) or admin actions.
            try:
                from app.db.models import TaskAssignment
                from datetime import datetime

                now = datetime.utcnow()
                await db.execute(
                    update(TaskAssignment)
                    .where(TaskAssignment.task_id == task_id)
                    .where(TaskAssignment.status != AssignmentStatus.done)
                    .values(status=AssignmentStatus.done, completed_at=now)
                )
                logger.info(f"[Automation] Auto-completed assignments for task {task_id} as part of auto-close (assignments-only)")
            except Exception as e:
                logger.warning(f"[Automation] Failed to auto-complete assignments during auto-close for task {task_id}: {e}")
            return True
        
        return False

    @staticmethod
    async def _maybe_chain_foreman_to_delivery(
        db: AsyncSession,
        task: AutomationTask,
    ) -> None:
        """
        After a foreman task completes for a qualifying order type, create a single
        delivery automation task if one does not already exist for the order.

        Safety:
        - Uses a DB-level existence check to avoid duplicates.
        - Only runs for specific OrderType values: agent_restock, store_keeper_restock, customer_wholesale.
        - Uses the existing AutomationService.create_task to create the delivery task (so existing hooks run).
        """
        # Quick guardrails
        if not task:
            return
        if getattr(task, 'required_role', None) != 'foreman':
            return
        if not getattr(task, 'related_order_id', None):
            return

        # Local imports to avoid circular dependencies at module import time
        from app.db.models import Order, AutomationTask as AT
        from app.db.enums import OrderType, AutomationTaskStatus

        # Resolve the order
        res = await db.execute(select(Order).where(Order.id == task.related_order_id))
        order = res.scalar_one_or_none()
        if not order:
            return

        order_type = order.order_type.value if isinstance(order.order_type, OrderType) else order.order_type
        allowed = {
            OrderType.agent_restock.value,
            OrderType.store_keeper_restock.value,
            OrderType.customer_wholesale.value,
        }
        if order_type not in allowed:
            return

        # Ensure a DB-level partial unique index exists to prevent duplicates/race conditions
        try:
            from sqlalchemy import text
            await db.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS uq_active_automation_task_per_role ON automation_tasks (related_order_id, required_role) WHERE status IN ('open','claimed','pending');"))
            await db.commit()
        except Exception as e:
            logger.warning(f"[OrderAutomation] Failed to ensure unique index for automation_tasks: {e}")

        # DB-level existence check: ensure at most one active delivery task per order
        try:
            exists_q = select(AT.id).where(
                AT.related_order_id == order.id,
                AT.required_role == 'delivery',
                AT.status.in_([AutomationTaskStatus.open, AutomationTaskStatus.claimed, AutomationTaskStatus.pending])
            ).limit(1)
            ex = await db.execute(exists_q)
            if ex.scalar_one_or_none():
                logger.info(f"[OrderAutomation] Skipping creation: active delivery task already exists for order {order.id}")
                return
        except Exception as e:
            logger.warning(f"[OrderAutomation] Existence check failed, proceeding with creation: {e}")

        # Create delivery task (do not auto-assign; created_by_id=0 to represent system)
        try:
            new_task = await AutomationService.create_task(
                db=db,
                task_type=task.task_type,
                title=f"Deliver Order #{order.id}",
                created_by_id=0,
                related_order_id=order.id,
                required_role='delivery',
                is_order_root=False,
            )
            logger.info(f"[Automation] Chained delivery task created for order {order.id}")

            # Mark the foreman automation task as completed since handover occurred
            try:
                from app.db.enums import AutomationTaskStatus as ATS
                if task.status not in (ATS.completed, ATS.cancelled):
                    task.status = ATS.completed
                    db.add(task)
                    await db.commit()
                    await db.refresh(task)
                    logger.info(f"[Automation] Foreman task {task.id} marked completed after handover")
            except Exception as e:
                logger.warning(f"[Automation] Failed to mark foreman task completed after handover: {e}")
        except Exception:
            logger.exception(f"[Automation] Failed to create chained delivery task for order {order.id}")
            raise
            raise

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

    @staticmethod
    async def reassign_task(
        db: AsyncSession,
        task_id: int,
        new_user_id: int,
        acting_user_id: int,
    ) -> Optional[AutomationTask]:
        """Reassign the claimed user on a task (admin-only operation)."""
        from app.audit.logger import log_audit
        # Load task
        task = await AutomationService.get_task(db, task_id, include_assignments=False)
        if not task:
            return None

        # Update claim
        prev = task.claimed_by_user_id
        task.claimed_by_user_id = new_user_id
        task.claimed_at = datetime.utcnow()
        db.add(task)

        # Log TaskEvent
        evt = TaskEvent(
            task_id=task.id,
            user_id=acting_user_id,
            event_type=TaskEventType.task_reassigned,
            event_metadata=json.dumps({"from_user_id": prev, "to_user_id": new_user_id}),
        )
        db.add(evt)

        # Audit
        try:
            from app.services.audit import log_audit_from_user, AuditActions
            actor_res = await db.execute(select(User).where(User.id == acting_user_id))
            actor = actor_res.scalar_one_or_none()
            await log_audit_from_user(db, actor, action=AuditActions.TASK_ASSIGN, target_type='task', target_id=task.id, description='admin reassign claim', meta={"from": prev, "to": new_user_id})
        except Exception:
            logger.warning(f"[Automation] Failed to write audit log for reassign task {task_id}")

        try:
            # Notify users
            from app.services.notifications import notify_task_reassigned
            await notify_task_reassigned(db=db, task_id=task.id, task_title=task.title, from_user_id=prev, to_user_id=new_user_id)
        except Exception as e:
            logger.warning(f"[Automation] Failed to notify on task.reassigned: {e}")

        await db.commit()
        await db.refresh(task)
        return task

    @staticmethod
    async def reassign_assignment(
        db: AsyncSession,
        assignment_id: int,
        new_user_id: Optional[int] = None,
        new_role_hint: Optional[str] = None,
        acting_user_id: Optional[int] = None,
    ) -> Optional[TaskAssignment]:
        """Reassign an assignment to a different user or role (admin-only)."""
        from app.audit.logger import log_audit
        res = await db.execute(select(TaskAssignment).where(TaskAssignment.id == assignment_id))
        assignment = res.scalar_one_or_none()
        if not assignment:
            return None

        prev_user = assignment.user_id
        prev_role = assignment.role_hint
        changed = False
        if new_user_id is not None and new_user_id != assignment.user_id:
            assignment.user_id = new_user_id
            changed = True
        if new_role_hint is not None and new_role_hint != assignment.role_hint:
            assignment.role_hint = new_role_hint
            changed = True

        if not changed:
            return assignment

        db.add(assignment)

        # Log TaskEvent
        evt = TaskEvent(
            task_id=assignment.task_id,
            user_id=acting_user_id,
            event_type=TaskEventType.reassigned,
            event_metadata=json.dumps({"from_user": prev_user, "to_user": assignment.user_id, "from_role": prev_role, "to_role": assignment.role_hint}),
        )
        db.add(evt)

        # Audit
        try:
            from app.services.audit import log_audit_from_user, AuditActions
            actor_res = await db.execute(select(User).where(User.id == acting_user_id))
            actor = actor_res.scalar_one_or_none()
            await log_audit_from_user(db, actor, action=AuditActions.TASK_ASSIGN, target_type='task_assignment', target_id=assignment.id, description='admin reassigned assignment', meta={"from_user": prev_user, "to_user": assignment.user_id, "from_role": prev_role, "to_role": assignment.role_hint})
        except Exception:
            logger.warning(f"[Automation] Failed to write audit log for reassign assignment {assignment_id}")

        await db.commit()
        await db.refresh(assignment)
        return assignment

    @staticmethod
    async def soft_delete_task(
        db: AsyncSession,
        task_id: int,
        acting_user_id: Optional[int] = None,
    ) -> Optional[AutomationTask]:
        """Soft-delete a task (implemented as cancel) and log audit.
        Note: We use status=cancelled as soft-delete since schema changes are not allowed."""
        from app.audit.logger import log_audit
        task = await AutomationService.get_task(db, task_id, include_assignments=False)
        if not task:
            return None

        task.status = AutomationTaskStatus.cancelled
        db.add(task)

        evt = TaskEvent(
            task_id=task.id,
            user_id=acting_user_id,
            event_type=TaskEventType.cancelled,
            event_metadata=json.dumps({"reason": "admin_soft_delete"}),
        )
        db.add(evt)

        try:
            from app.services.audit import log_audit_from_user, AuditActions
            actor_res = await db.execute(select(User).where(User.id == acting_user_id))
            actor = actor_res.scalar_one_or_none()
            await log_audit_from_user(db, actor, action=AuditActions.TASK_DELETE, target_type='task', target_id=task.id, description='admin soft delete')
        except Exception:
            logger.warning(f"[Automation] Failed to write audit log for soft delete task {task_id}")

        await db.commit()
        await db.refresh(task)
        return task    
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