"""
Sales API Endpoints (Phase 6.3)
Handles sales recording and reporting with role-based permissions.
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from datetime import datetime, timedelta
from typing import Optional

from app.core.security import get_current_user
from app.core.logging import sales_logger
from app.db.database import get_db
from app.services.sales import (
    record_sale, 
    get_sales_summary, 
    get_agent_performance,
    classify_sale,
    get_sale,
)
from app.db.models import Sale, Inventory, User
from app.db.enums import SaleChannel, UserRole

router = APIRouter()


async def _get_user_info(db: AsyncSession, user_id: int) -> tuple:
    """Get user's admin status and username from DB. Returns (is_system_admin, role, username)."""
    from sqlalchemy import select
    q = select(User.is_system_admin, User.role, User.username).where(User.id == user_id)
    result = await db.execute(q)
    row = result.one_or_none()
    if not row:
        return (False, 'member', '')
    return (row[0], row[1], row[2] or '')


def _get_effective_role(is_admin: bool, db_role: str, username: str) -> str:
    """
    Determine effective role from DB role field.
    Now uses actual role values: agent, storekeeper, delivery, foreman, customer.
    Falls back to username prefix for backwards compatibility.
    """
    if is_admin or db_role == 'system_admin':
        return 'admin'
    if db_role == 'team_admin':
        return 'admin'
    
    # Check actual DB role first (new system)
    if db_role in ('storekeeper', 'agent', 'foreman', 'delivery', 'customer'):
        return db_role
    
    # Fallback to username prefix for backwards compatibility
    username_lower = username.lower()
    if username_lower.startswith('storekeeper'):
        return 'storekeeper'
    if username_lower.startswith('agent'):
        return 'agent'
    if username_lower.startswith('foreman'):
        return 'foreman'
    if username_lower.startswith('delivery'):
        return 'delivery'
    if username_lower.startswith('customer'):
        return 'customer'
    
    # Default to member (treated as agent for sales purposes)
    return 'member'


# Legacy compatibility
async def _get_user_admin_status(db: AsyncSession, user_id: int) -> tuple:
    """Legacy: Get user's admin status. Returns (is_system_admin, role)."""
    is_admin, role, _ = await _get_user_info(db, user_id)
    return (is_admin, role)


async def _is_admin_user(db: AsyncSession, user_id: int) -> bool:
    """Return True only for system admins (matches require_admin semantics).

    NOTE: intentionally strict — team_admins are NOT granted revenue visibility.
    """
    try:
        is_admin, role, _ = await _get_user_info(db, user_id)
        return bool(is_admin or role == 'system_admin')
    except Exception:
        return False


async def _check_can_record_sale(db: AsyncSession, user_id: int, sale_channel: str) -> bool:
    """
    Check if user can record a sale.
    
    Permissions (per stabilization spec):
    - Admin: ✅ can record any sale
    - Storekeeper: ✅ can record any sale  
    - Agent: ✅ can record sales
    - Foreman: ❌ BLOCKED
    - Delivery: ❌ BLOCKED
    - Customer: ❌ BLOCKED
    """
    is_admin, db_role, username = await _get_user_info(db, user_id)
    effective_role = _get_effective_role(is_admin, db_role, username)
    
    # Admin and storekeeper can record any sale
    if effective_role in ('admin', 'storekeeper'):
        return True
    
    # Agent can record sales
    if effective_role == 'agent':
        return True
    
    # Block foreman, delivery, customer, and member from recording sales
    # Per stabilization spec: only admin, storekeeper, agent allowed
    return False


async def _check_can_view_all_sales(db: AsyncSession, user_id: int) -> bool:
    """
    Check if user can view ALL sales (not just their own).
    
    Permissions:
    - Admin: can view all
    - Storekeeper: can view all
    - Others: can only view their own
    """
    is_admin, db_role, username = await _get_user_info(db, user_id)
    effective_role = _get_effective_role(is_admin, db_role, username)
    return effective_role in ('admin', 'storekeeper')


async def _check_can_view_inventory(db: AsyncSession, user_id: int) -> bool:
    """
    Check if user can view inventory endpoints.
    
    Permissions:
    - Admin: can view
    - Storekeeper: can view
    - Others: BLOCKED
    """
    is_admin, db_role, username = await _get_user_info(db, user_id)
    effective_role = _get_effective_role(is_admin, db_role, username)
    return effective_role in ('admin', 'storekeeper')


async def _check_can_access_sales_api(db: AsyncSession, user_id: int) -> tuple:
    """
    Check sales API access level.
    
    Returns: (can_access, can_view_all, effective_role)
    
    Permissions:
    - Admin/Storekeeper: full access to all sales
    - Agent/Foreman/Member: can record + view own sales only
    - Delivery/Customer: BLOCKED entirely
    """
    is_admin, db_role, username = await _get_user_info(db, user_id)
    effective_role = _get_effective_role(is_admin, db_role, username)
    
    if effective_role in ('delivery', 'customer'):
        return (False, False, effective_role)
    
    if effective_role in ('admin', 'storekeeper'):
        return (True, True, effective_role)
    
    # Agent, foreman, member can access but only view their own
    return (True, False, effective_role)


# Legacy alias for backward compatibility
async def _check_can_view_all_summaries(db: AsyncSession, user_id: int) -> bool:
    """Legacy: Check if user can view all sales summaries."""
    return await _check_can_view_all_sales(db, user_id)


@router.post("/")
async def create_sale(
    payload: dict, 
    current_user: dict = Depends(get_current_user), 
    db: AsyncSession = Depends(get_db)
):
    """
    Record a new sale.
    
    Permissions:
    - Admin/Storekeeper: can record any sale
    - Agent/Foreman/Member: can record sales
    - Delivery/Customer: BLOCKED
    
    Returns consistent JSON on all error paths.
    """
    from app.services.sales import (
        ValidationError as SalesValidationError,
        ProductNotFoundError,
        InsufficientStockError,
        PermissionDeniedError,
        SalesError,
    )

    user_id = current_user['user_id']
    
    # Check basic access first and get effective role
    can_access, _, effective_role = await _check_can_access_sales_api(db, user_id)
    if not can_access:
        sales_logger.warning(
            "Sale access denied - blocked role",
            user_id=user_id,
            effective_role=effective_role,
        )
        raise HTTPException(
            status_code=403, 
            detail={"error": "permission_denied", "message": f"Role '{effective_role}' is not allowed to record sales"}
        )

    # Enforce operational permissions (write) via guard
    from app.db.models import User
    q = select(User).where(User.id == user_id)
    result = await db.execute(q)
    db_user = result.scalar_one_or_none()
    if not db_user:
        raise HTTPException(status_code=404, detail="User not found")

    # Attach operational role info onto db_user for permission resolution
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
    # Require permission, audit on denial
    try:
        require_permission(db_user, "sales", "create")
    except HTTPException:
        await log_audit(db, db_user, action="create", resource="sales", success=False, reason="permission_denied")
        raise

    # Parse and validate payload
    try:
        product_id = int(payload.get('product_id'))
        quantity = int(payload.get('quantity'))
        unit_price = float(payload.get('unit_price'))
        sale_channel = payload.get('sale_channel', SaleChannel.direct.value)
        related_order_id = payload.get('related_order_id')
        location = payload.get('location')
        idempotency_key = payload.get('idempotency_key')
        # Forms Extension fields
        reference = payload.get('reference')
        customer_name = payload.get('customer_name')
        customer_phone = payload.get('customer_phone')
        discount = payload.get('discount')  # Amount or percentage (stored as decimal)
        payment_method = payload.get('payment_method')  # cash, card, transfer, credit
        sale_date = payload.get('sale_date')  # ISO string or None (defaults to now)
        linked_order_id = payload.get('linked_order_id')  # Link to related order
        # Affiliate fields (all optional/nullable)
        affiliate_code = payload.get('affiliate_code') or None
        affiliate_name = payload.get('affiliate_name') or None
        affiliate_source = payload.get('affiliate_source') or None
    except (TypeError, ValueError) as e:
        sales_logger.warning("Invalid sale payload", error=str(e), user_id=user_id)
        raise HTTPException(
            status_code=400, 
            detail={"error": "validation_error", "message": "Invalid payload: product_id, quantity, and unit_price are required"}
        )

    sales_logger.info(
        "Recording sale",
        user_id=user_id,
        product_id=product_id,
        quantity=quantity,
        sale_channel=sale_channel,
    )

    # Permission check (API layer)
    if not await _check_can_record_sale(db, user_id, sale_channel):
        sales_logger.warning(
            "Sale permission denied",
            user_id=user_id,
            sale_channel=sale_channel,
        )
        raise HTTPException(
            status_code=403, 
            detail={"error": "permission_denied", "message": "Not authorized to record this type of sale"}
        )

    try:
        sale = await record_sale(
            db, 
            product_id, 
            quantity, 
            unit_price, 
            user_id, 
            sale_channel=sale_channel, 
            related_order_id=related_order_id,
            location=location,
            idempotency_key=idempotency_key,
            # Forms Extension fields
            reference=reference,
            customer_name=customer_name,
            customer_phone=customer_phone,
            discount=discount,
            payment_method=payment_method,
            sale_date=sale_date,
            linked_order_id=linked_order_id,
            affiliate_code=affiliate_code,
            affiliate_name=affiliate_name,
            affiliate_source=affiliate_source,
            # Pass role for defense-in-depth validation
            caller_role=effective_role,
        )
        sales_logger.info(
            "Sale recorded successfully",
            sale_id=sale.id,
            product_id=product_id,
            quantity=quantity,
            total_amount=float(sale.total_amount),
            user_id=user_id,
        )
        # Audit success
        try:
            await log_audit(db, db_user, action="create", resource="sales", resource_id=sale.id, success=True)
        except Exception:
            pass
    except ProductNotFoundError as e:
        sales_logger.warning("Sale failed - product not found", error=str(e), product_id=product_id)
        raise HTTPException(
            status_code=404, 
            detail={"error": "product_not_found", "message": str(e)}
        )
    except InsufficientStockError as e:
        sales_logger.warning("Sale failed - insufficient stock", error=str(e), product_id=product_id)
        raise HTTPException(
            status_code=409, 
            detail={"error": "insufficient_stock", "message": str(e)}
        )
    except PermissionDeniedError as e:
        sales_logger.warning("Sale failed - permission denied at service layer", error=str(e))
        # Audit denial
        try:
            await log_audit(db, db_user, action="create", resource="sales", success=False, reason=str(e))
        except Exception:
            pass
        raise HTTPException(
            status_code=403, 
            detail={"error": "permission_denied", "message": str(e)}
        )
    except SalesError as e:
        sales_logger.warning("Sale failed - validation or other error", error=str(e))
        raise HTTPException(
            status_code=getattr(e, 'http_code', 400), 
            detail={"error": "sales_error", "message": str(e)}
        )
    except Exception as e:
        sales_logger.error("Sale failed - unexpected error", error=str(e), user_id=user_id)
        # Ensure rollback happened (belt and suspenders)
        try:
            await db.rollback()
        except Exception:
            pass
        raise HTTPException(
            status_code=500, 
            detail={"error": "internal_error", "message": "An unexpected error occurred. Please try again."}
        )

    # Build response with revenue redaction for non-admins
    is_admin = await _is_admin_user(db, current_user['user_id'])
    resp = {
        "sale_id": sale.id,
        "product_id": sale.product_id,
        "quantity": sale.quantity,
        "sale_channel": sale.sale_channel,
        "sold_by_user_id": sale.sold_by_user_id,
        "location": sale.location,
        "related_order_id": sale.related_order_id,
        "created_at": sale.created_at.isoformat() if sale.created_at else None,
    }
    if is_admin:
        resp["unit_price"] = float(sale.unit_price)
        resp["total_amount"] = float(sale.total_amount)
    else:
        resp["unit_price"] = None
        resp["total_amount"] = None

    return resp


@router.get("/summary")
async def sales_summary(
    start_date: Optional[str] = Query(None, description="Start date YYYY-MM-DD"),
    end_date: Optional[str] = Query(None, description="End date YYYY-MM-DD"),
    user_id: Optional[int] = Query(None, description="Filter by user"),
    sale_channel: Optional[str] = Query(None, description="Filter by channel"),
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get sales summary with optional filters.
    
    Permissions:
    - Admin/Storekeeper: can view all sales
    - Agent/Foreman/Member: can only view their own sales
    - Delivery/Customer: BLOCKED
    """
    # Check access
    can_access, can_view_all, effective_role = await _check_can_access_sales_api(db, current_user['user_id'])
    if not can_access:
        raise HTTPException(status_code=403, detail=f"Role '{effective_role}' is not allowed to access sales data")
    
    # Parse dates
    start_dt = None
    end_dt = None
    if start_date:
        try:
            start_dt = datetime.fromisoformat(start_date)
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid start_date format")
    if end_date:
        try:
            end_dt = datetime.fromisoformat(end_date) + timedelta(days=1)  # Include full day
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid end_date format")
    
    # Permission check - non-admins can only see their own data
    filter_user_id = user_id
    if not can_view_all:
        filter_user_id = current_user['user_id']
    
    summary = await get_sales_summary(
        db,
        start_date=start_dt,
        end_date=end_dt,
        user_id=filter_user_id,
        sale_channel=sale_channel,
    )

    # Alias for frontend convenience
    summary['total_revenue'] = summary.get('total_amount')

    # Redact revenue for non-admins
    is_admin = await _is_admin_user(db, current_user['user_id'])
    if not is_admin:
        summary['total_amount'] = None
        summary['total_revenue'] = None
        for ch in summary.get('by_channel', []):
            ch['amount'] = None
            ch['revenue'] = None
    else:
        for ch in summary.get('by_channel', []):
            ch['revenue'] = ch.get('amount')

    return summary


@router.get("/metrics/daily")
async def daily_sales_totals(
    date: str | None = Query(None, description="ISO date YYYY-MM-DD. Defaults to today."),
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get daily sales totals.
    
    Permissions:
    - Admin/Storekeeper: can view totals
    - Others: BLOCKED (this is aggregate data)
    """
    if not await _check_can_view_all_sales(db, current_user['user_id']):
        raise HTTPException(status_code=403, detail="Not authorized to view aggregate sales metrics")
    
    if date:
        try:
            d = datetime.fromisoformat(date)
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid date format, use YYYY-MM-DD")
    else:
        d = datetime.utcnow()
    start = datetime(d.year, d.month, d.day)
    end = start + timedelta(days=1)

    q = select(
        func.coalesce(func.sum(Sale.total_amount), 0), 
        func.coalesce(func.sum(Sale.quantity), 0)
    ).where(Sale.created_at >= start, Sale.created_at < end)
    res = await db.execute(q)
    total_amount, total_quantity = res.one()
    is_admin = await _is_admin_user(db, current_user['user_id'])
    total_amt_out = float(total_amount) if is_admin else None
    return {
        "date": start.date().isoformat(),
        "total_amount": total_amt_out,
        "total_quantity": int(total_quantity)
    }


@router.get("/performance/agents")
async def agent_performance(
    start_date: Optional[str] = Query(None, description="Start date YYYY-MM-DD"),
    end_date: Optional[str] = Query(None, description="End date YYYY-MM-DD"),
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get sales performance by agent.
    Only includes AGENT channel sales.
    
    Permissions:
    - Admin only (or team_admin)
    """
    if not await _check_can_view_all_summaries(db, current_user['user_id']):
        raise HTTPException(status_code=403, detail="Admin access required")
    
    # Parse dates
    start_dt = None
    end_dt = None
    if start_date:
        try:
            start_dt = datetime.fromisoformat(start_date)
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid start_date format")
    if end_date:
        try:
            end_dt = datetime.fromisoformat(end_date) + timedelta(days=1)
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid end_date format")
    
    try:
        performance = await get_agent_performance(db, start_date=start_dt, end_date=end_dt)
        # Defensive: ensure numeric totals and return empty list when none
        safe_performance = []
        for p in performance:
            safe_performance.append({
                "user_id": p.get('user_id'),
                "username": p.get('username'),
                "display_name": p.get('display_name'),
                "total_sales": int(p.get('total_sales') or 0),
                "total_quantity": int(p.get('total_quantity') or 0),
                "total_amount": float(p.get('total_amount') or 0.0),
            })

        # Redact revenue values for non-admins
        is_admin = await _is_admin_user(db, current_user['user_id'])
        if not is_admin:
            for p in safe_performance:
                p['total_amount'] = None

        return {"agents": safe_performance}
    except Exception as e:
        sales_logger.error("Failed to fetch agent performance", error=e)
        return {"agents": []}


@router.get("/inventory")
async def inventory_remaining(current_user: dict = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """
    Get current inventory levels for all products.
    
    Permissions:
    - Admin/Storekeeper: can view
    - Others: BLOCKED
    """
    if not await _check_can_view_inventory(db, current_user['user_id']):
        raise HTTPException(status_code=403, detail="Not authorized to view inventory")

    q = select(
        Inventory.product_id, 
        Inventory.product_name,
        Inventory.total_stock, 
        Inventory.total_sold,
        Inventory.low_stock_threshold
    )
    res = await db.execute(q)
    try:
        rows = res.all()
        items = []
        for r in rows:
            try:
                product_id = int(r[0] or 0)
            except Exception:
                product_id = 0
            product_name = r[1] or ""
            try:
                total_stock = int(r[2] or 0)
            except Exception:
                total_stock = 0
            try:
                total_sold = int(r[3] or 0)
            except Exception:
                total_sold = 0
            try:
                low_stock_threshold = int(r[4] or 0)
            except Exception:
                low_stock_threshold = 0

            items.append({
                "product_id": product_id,
                "product_name": product_name,
                "total_stock": total_stock,
                "total_sold": total_sold,
                "remaining": total_stock,
                "low_stock_threshold": low_stock_threshold,
                "is_low_stock": total_stock <= low_stock_threshold,
            })
        return items
    except Exception as e:
        sales_logger.error("Failed to fetch inventory summary", error=e)
        return []


@router.get("/inventory/transactions")
async def inventory_transactions(product_id: Optional[int] = None, limit: int = 50, current_user: dict = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """Get recent inventory transactions. Admin + storekeeper only."""
    if not await _check_can_view_inventory(db, current_user['user_id']):
        raise HTTPException(status_code=403, detail="Not authorized to view inventory transactions")

    from app.db.models import InventoryTransaction
    q = select(InventoryTransaction).order_by(InventoryTransaction.created_at.desc()).limit(limit)
    if product_id:
        q = select(InventoryTransaction).where(InventoryTransaction.inventory_item_id == product_id).order_by(InventoryTransaction.created_at.desc()).limit(limit)
    res = await db.execute(q)
    rows = res.scalars().all()

    return [
        {
            "id": r.id,
            "inventory_item_id": r.inventory_item_id,
            "change": r.change,
            "reason": r.reason,
            "related_sale_id": r.related_sale_id,
            "performed_by_id": r.performed_by_id,
            "notes": r.notes,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in rows
    ]


@router.get("/grouped/channel")
async def sales_grouped_by_channel(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get sales grouped by channel.
    
    Permissions:
    - Admin/Storekeeper: can view
    - Others: BLOCKED (aggregate data)
    """
    if not await _check_can_view_all_sales(db, current_user['user_id']):
        raise HTTPException(status_code=403, detail="Not authorized to view aggregate sales data")
    
    q = select(
        Sale.sale_channel, 
        func.coalesce(func.sum(Sale.total_amount), 0), 
        func.coalesce(func.sum(Sale.quantity), 0)
    ).group_by(Sale.sale_channel)
    res = await db.execute(q)
    return [
        {"channel": r[0], "total_amount": float(r[1]), "total_quantity": int(r[2])} 
        for r in res.all()
    ]


@router.get("/grouped/user")
async def sales_grouped_by_user(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get sales grouped by user.
    
    Permissions:
    - Admin only
    """
    if not await _check_can_view_all_summaries(db, current_user['user_id']):
        raise HTTPException(status_code=403, detail="Admin access required")
    
    q = select(
        Sale.sold_by_user_id, 
        func.coalesce(func.sum(Sale.total_amount), 0), 
        func.coalesce(func.sum(Sale.quantity), 0)
    )
    q = q.group_by(Sale.sold_by_user_id)
    res = await db.execute(q)
    rows = res.all()

    results = []
    for user_id, total_amount, total_quantity in rows:
        username = None
        if user_id is not None:
            u_q = select(User.username).where(User.id == user_id)
            u_res = await db.execute(u_q)
            u_row = u_res.scalar_one_or_none()
            username = u_row
        results.append({
            "user_id": user_id, 
            "username": username, 
            "total_amount": float(total_amount), 
            "total_quantity": int(total_quantity)
        })
    return results


@router.get("/{sale_id}")
async def get_sale_by_id(
    sale_id: int,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get a specific sale by ID."""
    sale = await get_sale(db, sale_id)
    if not sale:
        raise HTTPException(status_code=404, detail="Sale not found")
    
    # Permission check - users can only see their own sales unless admin
    if not await _check_can_view_all_summaries(db, current_user['user_id']):
        if sale.sold_by_user_id != current_user['user_id']:
            raise HTTPException(status_code=403, detail="Not authorized to view this sale")
    
    is_admin = await _is_admin_user(db, current_user['user_id'])
    resp = {
        "sale_id": sale.id,
        "product_id": sale.product_id,
        "quantity": sale.quantity,
        "sale_channel": sale.sale_channel,
        "sold_by_user_id": sale.sold_by_user_id,
        "location": sale.location,
        "related_order_id": sale.related_order_id,
        "created_at": sale.created_at.isoformat() if sale.created_at else None,
    }
    if is_admin:
        resp["unit_price"] = sale.unit_price
        resp["total_amount"] = sale.total_amount
    else:
        resp["unit_price"] = None
        resp["total_amount"] = None
    return resp


@router.get("/{sale_id}/commission")
async def sale_commission_classification(sale_id: int, db: AsyncSession = Depends(get_db)):
    """Check if a sale is commission-eligible."""
    try:
        result = await classify_sale(db, sale_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Sale not found")
    return result