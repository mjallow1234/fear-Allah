"""
Sales Service Layer (Phase 6.3)
Handles sale recording, inventory updates, and automation triggers.
"""
from datetime import datetime
from typing import Optional
import os
import logging

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, func
from sqlalchemy.orm import selectinload

from app.db.models import Inventory, Sale, InventoryTransaction, Order, User
from app.db.enums import SaleChannel
from app.services.task_engine import emit_event

logger = logging.getLogger(__name__)

# Feature flag for sales automation
SALES_AUTOMATION_ENABLED = os.environ.get("SALES_AUTOMATION_ENABLED", "true").lower() == "true"

# Low stock threshold for automation events (can be overridden per product)
DEFAULT_LOW_STOCK_THRESHOLD = int(os.environ.get("LOW_STOCK_THRESHOLD", "10"))


async def record_sale(
    session: AsyncSession,
    product_id: int,
    quantity: int,
    unit_price: float,
    sold_by_user_id: int,
    sale_channel: str = None,
    related_order_id: Optional[int] = None,
    location: Optional[str] = None,
    idempotency_key: Optional[str] = None,
) -> Sale:
    """
    Validate and record a sale atomically.

    - Ensures quantity > 0
    - Performs an atomic UPDATE on inventory: requires available stock >= quantity
    - Inserts sale row
    - Creates inventory transaction record
    - Checks for low stock and emits automation event
    - Emits 'sale.recorded' after commit

    Returns the Sale row.
    Raises ValueError for missing inventory or validation errors.
    Raises RuntimeError for insufficient stock or concurrent conflicts.
    """
    if quantity <= 0:
        raise ValueError("Quantity must be > 0")

    # If idempotency key provided and a prior sale exists, return it (idempotent)
    if idempotency_key:
        q = select(Sale).where(Sale.idempotency_key == idempotency_key, Sale.sold_by_user_id == sold_by_user_id)
        res = await session.execute(q)
        existing = res.scalar_one_or_none()
        if existing:
            return existing

    # If related_order_id provided, validate order exists and is in an acceptable state
    if related_order_id is not None:
        q = select(Order).where(Order.id == related_order_id)
        r = await session.execute(q)
        order = r.scalar_one_or_none()
        if not order:
            raise ValueError("Order not found")
        # Accept 'AWAITING_CONFIRMATION' (delivered awaiting confirmation) or 'COMPLETED'
        if order.status not in ("AWAITING_CONFIRMATION", "COMPLETED"):
            raise RuntimeError("Order is not in a delivered/completed state")

    # Get inventory item first (we need the ID for the transaction)
    inv_q = select(Inventory).where(Inventory.product_id == product_id)
    inv_res = await session.execute(inv_q)
    inventory_item = inv_res.scalar_one_or_none()
    
    if not inventory_item:
        raise ValueError("Inventory record not found")
    
    if inventory_item.total_stock < quantity:
        raise RuntimeError("Insufficient stock")

    # Perform atomic inventory update: decrement stock if sufficient
    upd = (
        update(Inventory)
        .where(Inventory.product_id == product_id)
        .where(Inventory.total_stock >= quantity)
        .values(
            total_stock=Inventory.total_stock - quantity,
            total_sold=Inventory.total_sold + quantity,
            version=Inventory.version + 1,
        )
    )
    res_upd = await session.execute(upd)
    if res_upd.rowcount == 0:
        # Concurrent modification detected
        raise RuntimeError("Insufficient stock or concurrent modification")

    # Insert sale record
    total_amount = float(unit_price) * int(quantity)
    sale = Sale(
        product_id=product_id,
        quantity=quantity,
        unit_price=int(unit_price),
        total_amount=int(total_amount),
        sold_by_user_id=sold_by_user_id,
        sale_channel=sale_channel or SaleChannel.direct.value,
        related_order_id=related_order_id,
        location=location,
        idempotency_key=idempotency_key,
    )
    session.add(sale)
    await session.flush()  # Get sale ID

    # Create inventory transaction record
    transaction = InventoryTransaction(
        inventory_item_id=inventory_item.id,
        change=-quantity,  # Negative for sale
        reason="sale",
        related_sale_id=sale.id,
        related_order_id=related_order_id,
        performed_by_id=sold_by_user_id,
        notes=f"Sale recorded via {sale_channel or 'DIRECT'}",
    )
    session.add(transaction)

    # Commit all changes
    await session.commit()

    # Refresh inventory to get updated stock
    await session.refresh(inventory_item)
    
    # Emit sale recorded event
    await emit_event('sale.recorded', {
        'sale_id': sale.id,
        'product_id': sale.product_id,
        'quantity': sale.quantity,
        'sold_by': sale.sold_by_user_id,
        'channel': sale.sale_channel,
        'location': sale.location,
        'total_amount': sale.total_amount,
    })

    # Check for low stock and trigger automation event
    if SALES_AUTOMATION_ENABLED:
        await _check_low_stock_trigger(session, inventory_item, sold_by_user_id)

    logger.info(f"[Sales] Sale {sale.id} recorded: product={product_id}, qty={quantity}, by_user={sold_by_user_id}")

    return sale


async def _check_low_stock_trigger(
    session: AsyncSession,
    inventory_item: Inventory,
    triggered_by_user_id: int,
) -> None:
    """
    Check if inventory is below threshold and emit low stock automation event.
    This is a hook for future notification/automation integration.
    """
    threshold = inventory_item.low_stock_threshold or DEFAULT_LOW_STOCK_THRESHOLD
    
    if inventory_item.total_stock <= threshold:
        # Emit low stock event
        await emit_event('inventory.low_stock', {
            'inventory_id': inventory_item.id,
            'product_id': inventory_item.product_id,
            'product_name': inventory_item.product_name,
            'current_stock': inventory_item.total_stock,
            'threshold': threshold,
            'triggered_by': triggered_by_user_id,
        })
        
        logger.warning(
            f"[Inventory] LOW STOCK ALERT: product_id={inventory_item.product_id}, "
            f"stock={inventory_item.total_stock}, threshold={threshold}"
        )

        # Trigger automation task for low stock (if enabled)
        try:
            from app.automation.sales_triggers import SalesAutomationTriggers
            await SalesAutomationTriggers.on_low_stock(session, inventory_item, triggered_by_user_id)
        except ImportError:
            pass  # Automation module not yet available
        except Exception as e:
            logger.warning(f"[Automation] Failed to trigger low stock automation: {e}")


async def get_sale(session: AsyncSession, sale_id: int) -> Optional[Sale]:
    """Get a sale by ID."""
    q = select(Sale).where(Sale.id == sale_id)
    res = await session.execute(q)
    return res.scalar_one_or_none()


async def get_sales_summary(
    session: AsyncSession,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    user_id: Optional[int] = None,
    sale_channel: Optional[str] = None,
) -> dict:
    """
    Get aggregated sales summary with optional filters.
    
    Returns:
        dict with total_sales, total_quantity, total_amount, by_channel breakdown
    """
    query = select(
        func.count(Sale.id).label('total_sales'),
        func.coalesce(func.sum(Sale.quantity), 0).label('total_quantity'),
        func.coalesce(func.sum(Sale.total_amount), 0).label('total_amount'),
    )
    
    if start_date:
        query = query.where(Sale.created_at >= start_date)
    if end_date:
        query = query.where(Sale.created_at < end_date)
    if user_id:
        query = query.where(Sale.sold_by_user_id == user_id)
    if sale_channel:
        query = query.where(Sale.sale_channel == sale_channel)
    
    result = await session.execute(query)
    row = result.one()
    
    # Get by-channel breakdown
    channel_query = select(
        Sale.sale_channel,
        func.count(Sale.id).label('count'),
        func.coalesce(func.sum(Sale.total_amount), 0).label('amount'),
    ).group_by(Sale.sale_channel)
    
    if start_date:
        channel_query = channel_query.where(Sale.created_at >= start_date)
    if end_date:
        channel_query = channel_query.where(Sale.created_at < end_date)
    if user_id:
        channel_query = channel_query.where(Sale.sold_by_user_id == user_id)
    
    channel_result = await session.execute(channel_query)
    by_channel = [
        {"channel": r[0], "count": r[1], "amount": float(r[2])}
        for r in channel_result.all()
    ]
    
    return {
        "total_sales": row[0],
        "total_quantity": int(row[1]),
        "total_amount": float(row[2]),
        "by_channel": by_channel,
    }


async def get_agent_performance(
    session: AsyncSession,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
) -> list[dict]:
    """
    Get sales performance grouped by agent (sold_by_user_id).
    Only includes AGENT channel sales.
    
    Returns:
        List of agent performance records with user info.
    """
    query = select(
        Sale.sold_by_user_id,
        func.count(Sale.id).label('total_sales'),
        func.coalesce(func.sum(Sale.quantity), 0).label('total_quantity'),
        func.coalesce(func.sum(Sale.total_amount), 0).label('total_amount'),
    ).where(Sale.sale_channel == SaleChannel.agent.value).group_by(Sale.sold_by_user_id)
    
    if start_date:
        query = query.where(Sale.created_at >= start_date)
    if end_date:
        query = query.where(Sale.created_at < end_date)
    
    query = query.order_by(func.sum(Sale.total_amount).desc())
    
    result = await session.execute(query)
    rows = result.all()
    
    # Fetch user details
    performance = []
    for user_id, total_sales, total_quantity, total_amount in rows:
        user_q = select(User.username, User.display_name).where(User.id == user_id)
        user_res = await session.execute(user_q)
        user_row = user_res.one_or_none()
        
        performance.append({
            "user_id": user_id,
            "username": user_row[0] if user_row else None,
            "display_name": user_row[1] if user_row else None,
            "total_sales": total_sales,
            "total_quantity": int(total_quantity),
            "total_amount": float(total_amount),
        })
    
    return performance


async def classify_sale(session: AsyncSession, sale_id: int, amount_threshold: float = 10.0):
    """
    Classify whether a sale is commission eligible and provide exclusion reason if not.

    Policy:
      - Only sales with sale_channel == AGENT are eligible.
      - Sales below amount_threshold are excluded.
      - If sale.related_order_id exists, order must be in AWAITING_CONFIRMATION or COMPLETED.

    Returns: dict {"sale_id": ..., "commission_eligible": bool, "exclusion_reason": str | None}
    """
    q = select(Sale).where(Sale.id == sale_id)
    res = await session.execute(q)
    sale = res.scalar_one_or_none()
    if not sale:
        raise ValueError("Sale not found")

    # Simple channel rule
    if sale.sale_channel != SaleChannel.agent.value:
        return {"sale_id": sale.id, "commission_eligible": False, "exclusion_reason": 'channel_not_eligible'}

    # Amount threshold
    if float(sale.total_amount) < float(amount_threshold):
        return {"sale_id": sale.id, "commission_eligible": False, "exclusion_reason": 'amount_below_threshold'}

    # Related order check
    if sale.related_order_id is not None:
        o_q = select(Order).where(Order.id == sale.related_order_id)
        o_res = await session.execute(o_q)
        order = o_res.scalar_one_or_none()
        if not order or order.status not in ("AWAITING_CONFIRMATION", "COMPLETED"):
            return {"sale_id": sale.id, "commission_eligible": False, "exclusion_reason": 'related_order_not_eligible'}

    return {"sale_id": sale.id, "commission_eligible": True, "exclusion_reason": None}
