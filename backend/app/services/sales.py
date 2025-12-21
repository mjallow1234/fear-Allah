from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, insert
from app.db.models import Inventory, Sale
from app.db.enums import SaleChannel
from app.services.task_engine import emit_event


async def record_sale(session: AsyncSession, product_id: int, quantity: int, unit_price: float, sold_by_user_id: int, sale_channel: str = None, related_order_id: int | None = None, idempotency_key: str | None = None):
    """Validate and record a sale atomically.

    - Ensures quantity > 0
    - Performs an atomic UPDATE on inventory: requires available stock >= quantity
    - Inserts sale row
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
        from app.db.models import Order
        q = select(Order).where(Order.id == related_order_id)
        r = await session.execute(q)
        order = r.scalar_one_or_none()
        if not order:
            raise ValueError("Order not found")
        # Accept 'AWAITING_CONFIRMATION' (delivered awaiting confirmation) or 'COMPLETED'
        if order.status not in ("AWAITING_CONFIRMATION", "COMPLETED"):
            raise RuntimeError("Order is not in a delivered/completed state")

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
        # Determine reason
        q = select(Inventory).where(Inventory.product_id == product_id)
        r = await session.execute(q)
        current = r.scalar_one_or_none()
        if not current:
            raise ValueError("Inventory record not found")
        # else insufficient stock
        raise RuntimeError("Insufficient stock")

    # Insert sale record
    total_amount = float(unit_price) * int(quantity)
    sale = Sale(
        product_id=product_id,
        quantity=quantity,
        unit_price=unit_price,
        total_amount=total_amount,
        sold_by_user_id=sold_by_user_id,
        sale_channel=sale_channel or SaleChannel.direct.value,
        related_order_id=related_order_id,
        idempotency_key=idempotency_key,
    )
    session.add(sale)

    # Flush/commit and emit event after commit
    await session.flush()
    await session.commit()

    await emit_event('sale.recorded', {
        'sale_id': sale.id,
        'product_id': sale.product_id,
        'quantity': sale.quantity,
        'sold_by': sale.sold_by_user_id,
        'channel': sale.sale_channel,
    })

    return sale


async def classify_sale(session: AsyncSession, sale_id: int, amount_threshold: float = 10.0):
    """Classify whether a sale is commission eligible and provide exclusion reason if not.

    Policy (preview):
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

    # Default eligible
    eligible = True
    reason = None

    # Channel check
    if sale.sale_channel != Sale.sale_channel.type.python_type.__mro__[1].__name__ if False else None:
        # We can't rely on that reflection; instead compare to enum values
        pass

    # Simple channel rule
    if sale.sale_channel != 'AGENT':
        eligible = False
        reason = 'channel_not_eligible'
        return {"sale_id": sale.id, "commission_eligible": eligible, "exclusion_reason": reason}

    # Amount threshold
    if float(sale.total_amount) < float(amount_threshold):
        eligible = False
        reason = 'amount_below_threshold'
        return {"sale_id": sale.id, "commission_eligible": eligible, "exclusion_reason": reason}

    # Related order check
    if sale.related_order_id is not None:
        from app.db.models import Order
        o_q = select(Order).where(Order.id == sale.related_order_id)
        o_res = await session.execute(o_q)
        order = o_res.scalar_one_or_none()
        if not order or order.status not in ("AWAITING_CONFIRMATION", "COMPLETED"):
            eligible = False
            reason = 'related_order_not_eligible'
            return {"sale_id": sale.id, "commission_eligible": eligible, "exclusion_reason": reason}

    return {"sale_id": sale.id, "commission_eligible": True, "exclusion_reason": None}
