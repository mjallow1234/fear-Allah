from fastapi import APIRouter, Depends, HTTPException, status, Request
import asyncio
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
from app.db.models import Order, Sale, Inventory
from app.db.enums import OrderStatus
import json

router = APIRouter()


# ============================================================
# List Orders
# ============================================================

@router.get("/")
@router.get("/")
async def list_orders(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Return all orders.
    Admin/storekeeper → all orders.
    Everyone else → only orders they created.
    """
    from app.db.models import User, Sale, UserOperationalRole
    from sqlalchemy import exists

    user_id = current_user["user_id"]

    # Resolve user + operational role
    q = select(User).where(User.id == user_id)
    result = await db.execute(q)
    db_user = result.scalar_one_or_none()
    if not db_user:
        raise HTTPException(status_code=404, detail="User not found")

    op_result = await db.execute(
        select(UserOperationalRole).where(UserOperationalRole.user_id == user_id)
    )
    user_roles = {r.role for r in op_result.scalars().all()}
    is_admin = db_user.is_system_admin or db_user.role == "system_admin"
    print("OPERATIONAL ROLES:", user_roles)

    # Build query — admin/storekeeper see all, others see own orders
    stmt = select(Order).options(selectinload(Order.created_by)).order_by(Order.created_at.desc())
    if not is_admin and "storekeeper" not in user_roles:
        stmt = stmt.where(Order.created_by_id == user_id)

    rows = await db.execute(stmt)
    orders = rows.scalars().all()

    # For efficiency, fetch all sales related_order_id in one query
    order_ids = [o.id for o in orders]
    if order_ids:
        sales_rows = await db.execute(
            select(Sale.related_order_id)
            .where(Sale.related_order_id.in_(order_ids), Sale.is_reversed == False)
        )
        sales_order_ids = set(sales_rows.scalars().all())
    else:
        sales_order_ids = set()

    return [
        {
            "id": o.id,
            "order_type": o.order_type.value if hasattr(o.order_type, "value") else o.order_type,
            "status": o.status.value if hasattr(o.status, "value") else o.status,
            "items": o.items,
            "meta": o.meta,
            "created_at": o.created_at.isoformat() if o.created_at else None,
            "updated_at": o.updated_at.isoformat() if o.updated_at else None,
            "created_by_id": o.created_by_id,
            "created_by": {
                "id": o.created_by.id,
                "username": o.created_by.username,
                "display_name": o.created_by.display_name,
            } if o.created_by else None,
            "customer_name": o.customer_name,
            "customer_phone": o.customer_phone,
            "reference": o.reference,
            "priority": o.priority,
            "has_sale": o.id in sales_order_ids,
        }
        for o in orders
    ]

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
    from app.db.models import User, UserOperationalRole
    # Attach operational role onto a lightweight user-like object for permission resolution
    q = select(User).where(User.id == user_id)
    result = await db.execute(q)
    db_user = result.scalar_one_or_none()
    if not db_user:
        raise HTTPException(status_code=404, detail="User not found")

    # Attach operational role info onto db_user for permission resolution (read-only runtime)
    op_result = await db.execute(
        select(UserOperationalRole).where(UserOperationalRole.user_id == user_id)
    )
    op_roles = [r.role for r in op_result.scalars().all()]
    print("OPERATIONAL ROLES:", op_roles)
    # Shadow SA relationship with plain string list (bypasses instrumentation)
    object.__setattr__(db_user, 'operational_roles', op_roles)
    db_user.operational_role_id = None
    db_user.operational_role_name = op_roles[0] if op_roles else None

    from app.audit.logger import log_audit
    # Multi-role permission check: any matching role grants access
    allowed_roles_orders_create = {"admin", "agent", "sales_agent", "storekeeper"}
    is_admin_create = db_user.is_system_admin or db_user.role == "system_admin"
    if not (is_admin_create or any(role in allowed_roles_orders_create for role in op_roles)):
        await log_audit(db, db_user, action="create", resource="orders", success=False, reason="permission_denied")
        raise HTTPException(status_code=403, detail="Not allowed to create orders")

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

    # Fire-and-forget: notify connected clients
    from app.core.realtime import ops_manager
    asyncio.create_task(ops_manager.broadcast({"type": "ORDER_CREATED", "order_id": order.id}))

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
    Get a read-only snapshot of an order.
    
    Any authenticated user can view order snapshots.
    This is intentionally permissive - snapshots are read-only
    and should never block legitimate users.
    """
    from app.db.models import Order, AutomationTask
    from app.db.enums import AutomationTaskStatus
    
    # Load order with creator
    order_result = await db.execute(
        select(Order).options(selectinload(Order.created_by)).where(Order.id == order_id)
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
        "created_by": {
            "id": order.created_by.id,
            "username": order.created_by.username,
            "display_name": order.created_by.display_name,
        } if order.created_by else None,
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


# ============================================================
# Order Fulfillment (Pre-fill Sale Payload)
# ============================================================

@router.get("/{order_id}/fulfill")
async def get_fulfill_payload(
    order_id: int,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Return a pre-filled sale payload for fulfilling an order.
    Does NOT create the sale — the frontend submits via POST /api/sales/.
    Admin/Storekeeper only.
    """
    user_id = current_user["user_id"]

    # Check admin/storekeeper/sales_agent role via user_operational_roles
    from app.db.models import User, UserOperationalRole
    q = select(User).where(User.id == user_id)
    result = await db.execute(q)
    db_user = result.scalar_one_or_none()
    if not db_user:
        raise HTTPException(status_code=404, detail="User not found")

    op_result = await db.execute(
        select(UserOperationalRole).where(UserOperationalRole.user_id == user_id)
    )
    user_roles = {r.role for r in op_result.scalars().all()}
    is_admin = db_user.is_system_admin or db_user.role == "system_admin"

    print("[FULFILL] user_id:", user_id, "is_system_admin:", db_user.is_system_admin, "user_roles:", user_roles)

    allowed_roles = {"admin", "storekeeper", "sales_agent"}
    if not (is_admin or user_roles.intersection(allowed_roles)):
        raise HTTPException(status_code=403, detail="Insufficient permissions")

    # Load order
    order_result = await db.execute(select(Order).where(Order.id == order_id))
    order = order_result.scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    # Validate status
    order_status = order.status.value if hasattr(order.status, "value") else order.status
    if order_status not in ("awaiting_confirmation", "completed"):
        raise HTTPException(
            status_code=400,
            detail=f"Order must be in 'awaiting_confirmation' or 'completed' state (current: {order_status})",
        )

    # Check duplicate fulfillment
    dup_result = await db.execute(
        select(Sale.id).where(Sale.related_order_id == order_id).limit(1)
    )
    existing_sale = dup_result.scalar_one_or_none()
    if existing_sale:
        raise HTTPException(
            status_code=409,
            detail=f"Order #{order_id} has already been fulfilled (Sale #{existing_sale})",
        )

    # Source of truth: task.task_metadata.order_items
    items = []
    try:
        from app.db.models import AutomationTask as _AutomationTask
        task_res = await db.execute(
            select(_AutomationTask).where(
                _AutomationTask.related_order_id == order.id,
                _AutomationTask.is_order_root == True,
            ).limit(1)
        )
        task = task_res.scalar_one_or_none()

        if task and task.task_metadata:
            task_meta = task.task_metadata
            if isinstance(task_meta, str):
                try:
                    task_meta = json.loads(task_meta)
                except Exception:
                    task_meta = {}
            if isinstance(task_meta, dict):
                raw_items = task_meta.get("order_items")
                if isinstance(raw_items, str):
                    try:
                        raw_items = json.loads(raw_items)
                    except Exception:
                        raw_items = []
                if isinstance(raw_items, list):
                    items = raw_items
    except Exception as e:
        print("FULFILL ITEMS ERROR:", e)
        items = []

    print("ITEMS FROM TASK:", items)

    # Map order_type → sale_channel
    order_type = order.order_type.value if hasattr(order.order_type, "value") else order.order_type
    channel_map = {
        "agent_restock": "field",
        "agent_retail": "field",
        "store_keeper_restock": "store",
        "customer_wholesale": "direct",
    }
    sale_channel = channel_map.get(order_type, "direct")

    # Enrich items with product info from inventory
    enriched_items = []
    for item in items:
        product_id = item.get("product_id")
        qty = item.get("quantity") or item.get("qty") or 0
        if not product_id:
            continue

        try:
            inv_result = await db.execute(
                select(Inventory).where(Inventory.product_id == int(product_id))
            )
            inv = inv_result.scalar_one_or_none()
        except Exception:
            inv = None

        enriched_items.append({
            "product_id": int(product_id),
            "product_name": (item.get("product_name") or (inv.product_name if inv else None) or f"Product #{product_id}"),
            "quantity": int(qty),
            "available_stock": inv.total_stock if inv else None,
            "unit_price": 0,  # Inventory has no unit_price; set via modal
        })

    return {
        "order_id": order.id,
        "order_type": order_type,
        "order_status": order_status,
        "sale_channel": sale_channel,
        "customer_name": order.customer_name,
        "customer_phone": order.customer_phone,
        "reference": order.reference,
        "payment_method": order.payment_method,
        "items": enriched_items,
    }


# ============================================================
# Record Sales from Order (Backend-driven conversion)
# ============================================================

@router.post("/{order_id}/record-sales")
async def record_sales_from_order(
    order_id: int,
    body: dict,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Convert an order into one or more sales atomically.
    Idempotent — calling twice with the same order returns existing sales.
    """
    from app.db.models import User, UserOperationalRole
    from app.services.sales import record_sale

    user_id = current_user["user_id"]

    # ── Resolve user + operational role ──
    q = select(User).where(User.id == user_id)
    result = await db.execute(q)
    db_user = result.scalar_one_or_none()
    if not db_user:
        raise HTTPException(status_code=404, detail="User not found")

    op_result = await db.execute(
        select(UserOperationalRole).where(UserOperationalRole.user_id == user_id)
    )
    user_roles_rs = {r.role for r in op_result.scalars().all()}
    is_admin_rs = db_user.is_system_admin or db_user.role == "system_admin"

    print("[RECORD-SALES] user_id:", user_id, "is_system_admin:", db_user.is_system_admin, "user_roles:", user_roles_rs)

    allowed_roles_rs = {"admin", "storekeeper", "sales_agent"}
    if not (is_admin_rs or user_roles_rs.intersection(allowed_roles_rs)):
        raise HTTPException(status_code=403, detail="Insufficient permissions")

    # ── Load order ──
    order_result = await db.execute(select(Order).where(Order.id == order_id))
    order = order_result.scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    order_status = order.status.value if hasattr(order.status, "value") else order.status
    if order_status not in ("awaiting_confirmation", "completed"):
        raise HTTPException(
            status_code=400,
            detail=f"Order must be in 'awaiting_confirmation' or 'completed' state (current: {order_status})",
        )

    # ── Validate payload ──
    items = body.get("items")
    if not items or not isinstance(items, list):
        raise HTTPException(status_code=422, detail="'items' array is required")

    # ── Map order_type → sale_channel ──
    order_type = order.order_type.value if hasattr(order.order_type, "value") else order.order_type
    channel_map = {
        "agent_restock": "field",
        "agent_retail": "field",
        "store_keeper_restock": "store",
        "customer_wholesale": "direct",
    }
    sale_channel = channel_map.get(order_type, "direct")

    # ── Record one sale per item ──
    sale_ids = []
    for item in items:
        try:
            product_id = int(item["product_id"])
            quantity = int(item["quantity"])
            unit_price = float(item["unit_price"])
        except (KeyError, TypeError, ValueError) as exc:
            raise HTTPException(
                status_code=422,
                detail=f"Each item must have product_id, quantity, unit_price: {exc}",
            )

        sale = await record_sale(
            session=db,
            product_id=product_id,
            quantity=quantity,
            unit_price=unit_price,
            sold_by_user_id=user_id,
            sale_channel=sale_channel,
            related_order_id=order.id,
            customer_name=order.customer_name,
            customer_phone=order.customer_phone,
            payment_method=order.payment_method,
            reference=order.reference,
            idempotency_key=f"order-{order.id}-{product_id}",
        )
        sale_ids.append(sale.id)

    # Fire-and-forget: notify connected clients that order was converted
    from app.core.realtime import ops_manager
    asyncio.create_task(ops_manager.broadcast({"type": "ORDER_UPDATED", "order_id": order_id}))

    return {"success": True, "sales_created": sale_ids}
