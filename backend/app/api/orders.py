from fastapi import APIRouter, Depends, HTTPException, status, Request
from app.core.security import get_current_user
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from app.db.database import get_db
from pydantic import BaseModel
from app.services.task_engine import create_order
from app.automation.order_triggers import OrderAutomationTriggers
from app.core.logging import orders_logger
from typing import Optional, List, Any
from datetime import datetime
import json

router = APIRouter()


class CreateOrderRequest(BaseModel):
    order_type: str
    items: list = []
    metadata: dict = {}
    # Extended fields (Forms Extension)
    reference: Optional[str] = None
    priority: Optional[str] = None  # low, normal, high, urgent
    requested_delivery_date: Optional[datetime] = None
    customer_name: Optional[str] = None
    customer_phone: Optional[str] = None
    payment_method: Optional[str] = None  # cash, card, transfer, credit
    internal_comment: Optional[str] = None


@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_order_endpoint(request: CreateOrderRequest, current_user: dict = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    user_id = current_user["user_id"]
    # Fetch DB user and ensure permission to create orders
    from app.db.models import User, UserRole as UserRoleModel, Role
    # Attach operational role onto a lightweight user-like object for permission resolution
    q = select(User).where(User.id == user_id)
    result = await db.execute(q)
    db_user = result.scalar_one_or_none()
    if not db_user:
        raise HTTPException(status_code=404, detail="User not found")

    # Attach operational role info onto db_user for permission resolution (read-only runtime)
    from app.db.models import UserRole as UserRoleModel, Role
    from sqlalchemy.orm import selectinload
    from app.api.system import OPERATIONAL_ROLE_NAMES
    op_result = await db.execute(
        select(UserRoleModel).join(Role).options(selectinload(UserRoleModel.role)).where(
            UserRoleModel.user_id == user_id, Role.name.in_(OPERATIONAL_ROLE_NAMES)
        )
    )
    op_assignment = op_result.scalar_one_or_none()
    db_user.operational_role_id = op_assignment.role_id if op_assignment else None
    db_user.operational_role_name = op_assignment.role.name if (op_assignment and op_assignment.role) else None

    from app.permissions.guards import require_permission
    from app.audit.logger import log_audit
    # Require create permission on orders (audit on deny)
    try:
        require_permission(db_user, "orders", "create")
    except HTTPException as e:
        await log_audit(db, db_user, action="create", resource="orders", success=False, reason="permission_denied")
        raise

    # Temporary runtime verification: log raw HTTP body and parsed payload
    try:
        orders_logger.info(
            "[ORDER-API] raw_body=%s",
            await http_request.body(),
        )
        orders_logger.info(
            "[ORDER-API] parsed_payload=%s",
            request.model_dump(),
        )
    except Exception:
        orders_logger.warning("[ORDER-API] failed to log raw_body/parsed_payload")

    orders_logger.info(
        "Creating order",
        user_id=user_id,
        order_type=request.order_type,
        items_count=len(request.items),
    )

    # Temporary runtime verification log (remove after verification)
    try:
        orders_logger.info(
            "[ORDER-CREATE] payload_keys=%s meta=%s",
            list(request.model_dump().keys()),
            extended_meta,
        )
    except Exception:
        orders_logger.warning("[ORDER-CREATE] failed to log payload_keys/meta")

    try:
        # Build extended metadata dict with new fields
        extended_meta = dict(request.metadata) if request.metadata else {}
        if request.reference:
            extended_meta['reference'] = request.reference
        if request.priority:
            extended_meta['priority'] = request.priority
        if request.requested_delivery_date:
            extended_meta['requested_delivery_date'] = request.requested_delivery_date.isoformat()
        if request.customer_name:
            extended_meta['customer_name'] = request.customer_name
        if request.customer_phone:
            extended_meta['customer_phone'] = request.customer_phone
        if request.payment_method:
            extended_meta['payment_method'] = request.payment_method
        if request.internal_comment:
            extended_meta['internal_comment'] = request.internal_comment
        
        order = await create_order(
            db, 
            request.order_type, 
            items=str(request.items), 
            metadata=extended_meta,
            created_by_id=user_id,
            # Pass extended fields to the order directly
            reference=request.reference,
            priority=request.priority,
            requested_delivery_date=request.requested_delivery_date,
            customer_name=request.customer_name,
            customer_phone=request.customer_phone,
            payment_method=request.payment_method,
            internal_comment=request.internal_comment,
        )
        orders_logger.info(
            "Order created successfully",
            order_id=order.id,
            status=order.status,
            user_id=user_id,
        )
        # Audit successful order creation
        try:
            from app.audit.logger import log_audit
            await log_audit(db, db_user, action="create", resource="orders", resource_id=order.id, success=True)
        except Exception:
            pass
    except ValueError as e:
        orders_logger.warning(
            "Order creation failed - validation error",
            error=e,
            user_id=user_id,
            order_type=request.order_type,
        )
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        orders_logger.error(
            "Order creation failed - unexpected error",
            error=e,
            user_id=user_id,
            order_type=request.order_type,
        )
        raise

    return {"order_id": order.id, "status": order.status}


@router.get("/{order_id}/automation")
async def get_order_automation_status(
    order_id: int,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get automation task status for an order."""
    orders_logger.debug("Fetching automation status", order_id=order_id)
    try:
        status_info = await OrderAutomationTriggers.get_order_automation_status(db, order_id)
        return status_info
    except Exception as e:
        orders_logger.error(
            "Failed to fetch automation status",
            error=e,
            order_id=order_id,
        )
        raise


# ============================================================
# Order Snapshot (Read-Only View)
# ============================================================

@router.get("/{order_id}/snapshot")
async def get_order_snapshot(
    order_id: int,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Get a read-only snapshot of an order for role-based visibility.
    
    Access allowed if ANY is true:
    - User is admin
    - User has operational role matching any task in this order
    - User has assignment (past or present) in this order
    
    NO MUTATIONS - read-only view only.
    """
    from app.db.models import (
        Order, User, AutomationTask, TaskAssignment, UserOperationalRole
    )
    from app.db.enums import AutomationTaskStatus, AssignmentStatus
    
    user_id = current_user["user_id"]
    
    # Load user with operational roles
    user_result = await db.execute(
        select(User)
        .options(selectinload(User.operational_roles))
        .where(User.id == user_id)
    )
    db_user = user_result.scalar_one_or_none()
    if not db_user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Load order
    order_result = await db.execute(
        select(Order).where(Order.id == order_id)
    )
    order = order_result.scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    
    # Load automation tasks for this order with their assignments
    tasks_result = await db.execute(
        select(AutomationTask)
        .options(selectinload(AutomationTask.assignments))
        .where(AutomationTask.related_order_id == order_id)
        .order_by(AutomationTask.id)
    )
    automation_tasks = list(tasks_result.scalars().all())
    
    # ============================================================
    # Permission Check
    # ============================================================
    is_admin = db_user.is_system_admin or (db_user.role and db_user.role.value in ['system_admin', 'team_admin'])
    
    # Get user's operational role names
    user_op_roles = set(r.role for r in db_user.operational_roles) if db_user.operational_roles else set()
    
    # Get all required_roles from tasks
    task_roles = set(t.required_role for t in automation_tasks if t.required_role)
    
    # Check if user has assignment in this order
    has_assignment = any(
        any(a.user_id == user_id for a in t.assignments)
        for t in automation_tasks
    )
    
    # Check if user's operational role matches any task role
    has_matching_role = bool(user_op_roles & task_roles)
    
    # Permission granted if admin, has matching role, or has assignment
    if not (is_admin or has_matching_role or has_assignment):
        raise HTTPException(
            status_code=403,
            detail="Access denied: You don't have permission to view this order"
        )
    
    # ============================================================
    # Build Snapshot Response
    # ============================================================
    
    # Parse meta if it's a JSON string
    meta_dict = {}
    if order.meta:
        try:
            meta_dict = json.loads(order.meta) if isinstance(order.meta, str) else order.meta
        except Exception:
            meta_dict = {}
    
    # Build order data
    order_data = {
        "id": order.id,
        "order_type": order.order_type.value if hasattr(order.order_type, 'value') else order.order_type,
        "status": order.status.value if hasattr(order.status, 'value') else order.status,
        "priority": order.priority or "normal",
        "delivery_location": meta_dict.get("delivery_location"),
        "customer_name": order.customer_name,
        "customer_phone": order.customer_phone,
        "reference": order.reference,
        "payment_method": order.payment_method,
        "internal_comment": order.internal_comment,
        "meta": meta_dict,
        "created_at": order.created_at.isoformat() if order.created_at else None,
        "created_by_id": order.created_by_id,
    }
    
    # Build tasks data with assignments
    tasks_data = []
    completed_roles = []
    pending_roles = []
    locked_roles = []
    
    for task in automation_tasks:
        # Skip root task (it's just a container)
        if task.is_order_root:
            continue
            
        task_status = task.status.value if hasattr(task.status, 'value') else task.status
        role = task.required_role or "unknown"
        
        # Build assignments list
        assignments_data = [
            {
                "user_id": a.user_id,
                "status": a.status.value if hasattr(a.status, 'value') else a.status,
                "assigned_at": a.assigned_at.isoformat() if a.assigned_at else None,
                "completed_at": a.completed_at.isoformat() if a.completed_at else None,
            }
            for a in task.assignments
        ]
        
        tasks_data.append({
            "id": task.id,
            "title": task.title,
            "required_role": role,
            "status": task_status,
            "assignments": assignments_data,
        })
        
        # Categorize role progress
        if task_status == AutomationTaskStatus.completed.value:
            if role not in completed_roles:
                completed_roles.append(role)
        elif task_status in [AutomationTaskStatus.open.value, AutomationTaskStatus.in_progress.value]:
            if role not in pending_roles:
                pending_roles.append(role)
        else:
            if role not in locked_roles:
                locked_roles.append(role)
    
    # Build progress summary
    progress = {
        "completed_roles": completed_roles,
        "pending_roles": pending_roles,
        "locked_roles": locked_roles,
    }
    
    return {
        "order": order_data,
        "tasks": tasks_data,
        "progress": progress,
    }