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


async def _get_user_admin_status(db: AsyncSession, user_id: int) -> tuple:
    """Get user's admin status from DB. Returns (is_system_admin, role)."""
    from sqlalchemy import select
    q = select(User.is_system_admin, User.role).where(User.id == user_id)
    result = await db.execute(q)
    row = result.one_or_none()
    if not row:
        return (False, 'member')
    return (row[0], row[1])


async def _check_can_record_sale(db: AsyncSession, user_id: int, sale_channel: str) -> bool:
    """
    Check if user can record a sale for the given channel.
    - Agents can record AGENT sales (their own)
    - Store keepers can record STORE sales
    - Admins can record any sale
    """
    is_admin, role = await _get_user_admin_status(db, user_id)
    
    if is_admin or role == 'system_admin':
        return True
    
    # Agents can only record agent sales
    if sale_channel == SaleChannel.agent.value:
        return True  # Any authenticated user can record agent sales (their own)
    
    # Store sales require store_keeper or admin
    if sale_channel == SaleChannel.store.value:
        return role in ('system_admin', 'team_admin')
    
    # Direct sales - allow for now
    if sale_channel == SaleChannel.direct.value:
        return True
    
    return False


async def _check_can_view_all_summaries(db: AsyncSession, user_id: int) -> bool:
    """Check if user can view all sales summaries."""
    is_admin, role = await _get_user_admin_status(db, user_id)
    return is_admin or role in ('system_admin', 'team_admin')


@router.post("/")
async def create_sale(
    payload: dict, 
    current_user: dict = Depends(get_current_user), 
    db: AsyncSession = Depends(get_db)
):
    """
    Record a new sale.
    
    Permissions:
    - Agents can record their own AGENT sales
    - Store keepers can record STORE sales  
    - Admins can record any sale
    """
    try:
        product_id = int(payload.get('product_id'))
        quantity = int(payload.get('quantity'))
        unit_price = float(payload.get('unit_price'))
        sale_channel = payload.get('sale_channel', SaleChannel.direct.value)
        related_order_id = payload.get('related_order_id')
        location = payload.get('location')
        idempotency_key = payload.get('idempotency_key')
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid payload")

    # Permission check
    if not await _check_can_record_sale(db, current_user['user_id'], sale_channel):
        raise HTTPException(status_code=403, detail="Not authorized to record this type of sale")

    try:
        sale = await record_sale(
            db, 
            product_id, 
            quantity, 
            unit_price, 
            current_user['user_id'], 
            sale_channel=sale_channel, 
            related_order_id=related_order_id,
            location=location,
            idempotency_key=idempotency_key
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=409, detail=str(e))

    return {
        "sale_id": sale.id, 
        "product_id": sale.product_id, 
        "quantity": sale.quantity,
        "total_amount": sale.total_amount,
        "sale_channel": sale.sale_channel,
    }


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
    - Agents can only view their own sales
    - Admins can view all sales
    """
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
    if not await _check_can_view_all_summaries(db, current_user['user_id']):
        filter_user_id = current_user['user_id']
    
    summary = await get_sales_summary(
        db,
        start_date=start_dt,
        end_date=end_dt,
        user_id=filter_user_id,
        sale_channel=sale_channel,
    )
    
    return summary


@router.get("/metrics/daily")
async def daily_sales_totals(
    date: str | None = Query(None, description="ISO date YYYY-MM-DD. Defaults to today."), 
    db: AsyncSession = Depends(get_db)
):
    """Get daily sales totals."""
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
    return {
        "date": start.date().isoformat(), 
        "total_amount": float(total_amount), 
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
    
    performance = await get_agent_performance(db, start_date=start_dt, end_date=end_dt)
    return {"agents": performance}


@router.get("/inventory")
async def inventory_remaining(db: AsyncSession = Depends(get_db)):
    """Get current inventory levels for all products."""
    q = select(
        Inventory.product_id, 
        Inventory.product_name,
        Inventory.total_stock, 
        Inventory.total_sold,
        Inventory.low_stock_threshold
    )
    res = await db.execute(q)
    rows = res.all()
    return [
        {
            "product_id": r[0], 
            "product_name": r[1],
            "total_stock": r[2], 
            "total_sold": r[3], 
            "remaining": r[2],
            "low_stock_threshold": r[4],
            "is_low_stock": r[2] <= r[4],
        } 
        for r in rows
    ]


@router.get("/grouped/channel")
async def sales_grouped_by_channel(db: AsyncSession = Depends(get_db)):
    """Get sales grouped by channel."""
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
    
    return {
        "sale_id": sale.id,
        "product_id": sale.product_id,
        "quantity": sale.quantity,
        "unit_price": sale.unit_price,
        "total_amount": sale.total_amount,
        "sale_channel": sale.sale_channel,
        "sold_by_user_id": sale.sold_by_user_id,
        "location": sale.location,
        "related_order_id": sale.related_order_id,
        "created_at": sale.created_at.isoformat() if sale.created_at else None,
    }


@router.get("/{sale_id}/commission")
async def sale_commission_classification(sale_id: int, db: AsyncSession = Depends(get_db)):
    """Check if a sale is commission-eligible."""
    try:
        result = await classify_sale(db, sale_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Sale not found")
    return result