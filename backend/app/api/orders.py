from fastapi import APIRouter, Depends, HTTPException, status
from app.core.security import get_current_user
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.db.database import get_db
from pydantic import BaseModel
from app.services.task_engine import create_order
from app.automation.order_triggers import OrderAutomationTriggers
from app.core.logging import orders_logger
from typing import Optional
from datetime import datetime

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

    orders_logger.info(
        "Creating order",
        user_id=user_id,
        order_type=request.order_type,
        items_count=len(request.items),
    )

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