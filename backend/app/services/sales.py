"""
Sales Service Layer (Phase 6.3 - Transactional)

Core Principles:
- Sales are immutable transactions (no edits, only reversals)
- Inventory uses ledger pattern (InventoryTransaction with deltas)
- Atomic commits: Sale + Ledger in one transaction with explicit rollback
- Side effects (notifications) happen AFTER commit, failures don't break sale
- Defense in depth: role checks at both API and service layer

Error Handling:
- ProductNotFoundError (404)
- InsufficientStockError (409)
- ValidationError (400)
- PermissionDeniedError (403)
"""
from dataclasses import dataclass
from datetime import datetime
from typing import Optional, Tuple, Set
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


# ============================================================================
# Custom Exceptions (maps to HTTP codes)
# ============================================================================

class SalesError(Exception):
    """Base class for sales errors."""
    http_code: int = 500
    
class ValidationError(SalesError):
    """Invalid input (400)."""
    http_code = 400

class ProductNotFoundError(SalesError):
    """Product not found in inventory (404)."""
    http_code = 404

class InsufficientStockError(SalesError):
    """Not enough stock to fulfill sale (409)."""
    http_code = 409

class PermissionDeniedError(SalesError):
    """User not allowed to record sales (403)."""
    http_code = 403


# ============================================================================
# Role Constants (defense in depth - per stabilization spec)
# ============================================================================

# Roles that are NEVER allowed to record sales
BLOCKED_ROLES: Set[str] = {'delivery', 'customer', 'foreman', 'member'}

# Roles allowed to record sales (only these 3)
ALLOWED_ROLES: Set[str] = {'admin', 'system_admin', 'team_admin', 'storekeeper', 'agent'}


# ============================================================================
# Data Transfer Objects
# ============================================================================

@dataclass
class SaleInput:
    """Validated sale input."""
    product_id: int
    product_name: str
    quantity: int
    unit_price: float
    channel: str
    customer_name: Optional[str] = None
    related_order_id: Optional[int] = None
    idempotency_key: Optional[str] = None


@dataclass
class SaleResult:
    """Result of a successful sale."""
    sale_id: int
    product_name: str
    quantity: int
    unit_price: float
    total_amount: float
    channel: str
    stock_before: int
    stock_after: int
    customer_name: Optional[str] = None


# ============================================================================
# Input Normalization & Validation
# ============================================================================

async def resolve_product_by_id(
    session: AsyncSession, 
    product_id: int
) -> Tuple[int, str, Inventory]:
    """
    Resolve product by ID ONLY (canonical flow).
    
    ❌ No name resolution - product_id is required
    
    Returns: (product_id, product_name, inventory_item)
    Raises: ProductNotFoundError, ValidationError
    """
    if not product_id:
        raise ValidationError("Product ID is required")
    
    try:
        product_id = int(product_id)
    except (TypeError, ValueError):
        raise ValidationError("Product ID must be a valid integer")
    
    try:
        res = await session.execute(select(Inventory).where(Inventory.product_id == product_id))
        inv = res.scalar_one_or_none()
        if inv:
            return inv.product_id, inv.product_name or f"Product #{product_id}", inv
        raise ProductNotFoundError(f"Product with ID {product_id} not found in inventory")
    except SalesError:
        raise
    except Exception as e:
        logger.exception("Product lookup failed")
        raise ValidationError("Product lookup failed, please try again")


def normalize_channel(channel_arg: Optional[str]) -> str:
    """Normalize channel string to SaleChannel enum value."""
    if not channel_arg:
        return SaleChannel.direct.value
    
    channel_lower = channel_arg.lower().strip()
    channel_map = {
        'field': SaleChannel.field.value,
        'store': SaleChannel.store.value,
        'delivery': SaleChannel.delivery.value,
        'direct': SaleChannel.direct.value,
        # Legacy mappings
        'agent': SaleChannel.field.value,
    }
    return channel_map.get(channel_lower, SaleChannel.direct.value)


async def validate_sale_input(
    session: AsyncSession,
    product_id: int,
    quantity: int,
    unit_price: float,
    channel: Optional[str] = None,
    customer_name: Optional[str] = None,
    related_order_id: Optional[int] = None,
    idempotency_key: Optional[str] = None,
) -> SaleInput:
    """
    Validate and normalize sale input.
    
    ❌ Uses product_id ONLY - no name resolution
    
    Returns: SaleInput dataclass
    Raises: ValidationError, ProductNotFoundError
    """
    errors = []
    
    if quantity <= 0:
        errors.append("Quantity must be greater than 0")
    if unit_price is None or unit_price < 0:
        errors.append("Price must be >= 0")
    if not product_id:
        errors.append("Product ID is required")
    
    if errors:
        raise ValidationError(", ".join(errors))
    
    # Resolve product by ID only
    resolved_id, product_name, _ = await resolve_product_by_id(session, product_id)
    
    return SaleInput(
        product_id=resolved_id,
        product_name=product_name,
        quantity=quantity,
        unit_price=unit_price,
        channel=normalize_channel(channel),
        customer_name=customer_name,
        related_order_id=related_order_id,
        idempotency_key=idempotency_key,
    )


# ============================================================================
# Stock Check (Pre-transaction)
# ============================================================================

async def check_stock_availability(
    session: AsyncSession,
    product_id: int,
    quantity: int,
) -> Tuple[int, int]:
    """
    Check if sufficient stock is available.
    
    Returns: (current_stock, stock_after_sale)
    Raises: ProductNotFoundError, InsufficientStockError
    """
    result = await session.execute(
        select(Inventory).where(Inventory.product_id == product_id)
    )
    inventory = result.scalar_one_or_none()
    
    if not inventory:
        raise ProductNotFoundError(f"Inventory record for product {product_id} not found")
    
    if inventory.total_stock < quantity:
        raise InsufficientStockError(
            f"Insufficient stock: requested {quantity}, available {inventory.total_stock}"
        )
    
    return inventory.total_stock, inventory.total_stock - quantity


# ============================================================================
# Core Transaction (Atomic with Explicit Rollback)
# ============================================================================

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
    customer_name: Optional[str] = None,
    # Forms Extension fields
    reference: Optional[str] = None,
    customer_phone: Optional[str] = None,
    discount: Optional[float] = None,
    payment_method: Optional[str] = None,
    sale_date: Optional[str] = None,  # ISO string
    linked_order_id: Optional[int] = None,
    affiliate_code: Optional[str] = None,
    affiliate_name: Optional[str] = None,
    affiliate_source: Optional[str] = None,
    # Defense in depth: caller's role (optional, for service-layer validation)
    caller_role: Optional[str] = None,
) -> Sale:
    """
    Validate and record a sale atomically with explicit rollback on failure.

    ATOMIC: Sale + InventoryTransaction in one commit.
    ROLLBACK: Any error triggers explicit rollback before re-raising.
    SIDE EFFECTS: Notifications happen AFTER commit (non-blocking).

    Returns the Sale row with stock_before/stock_after attributes attached.
    Raises: ValidationError, ProductNotFoundError, InsufficientStockError, PermissionDeniedError
    """
    sale = None
    inventory_item = None
    stock_before = 0
    
    try:
        # ===== VALIDATION PHASE (before any DB writes) =====
        
        # Defense in depth: block forbidden roles at service layer
        if caller_role and caller_role.lower() in BLOCKED_ROLES:
            raise PermissionDeniedError(f"Role '{caller_role}' is not allowed to record sales")
        
        if quantity <= 0:
            raise ValidationError("Quantity must be > 0")
        
        if unit_price is None or unit_price < 0:
            raise ValidationError("Price must be >= 0")

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
                raise ValidationError("Related order not found")
            # Accept 'awaiting_confirmation' (delivered awaiting confirmation) or 'completed'
            if order.status not in ("awaiting_confirmation", "completed"):
                raise ValidationError("Order is not in a delivered/completed state")

        # ===== INVENTORY LOOKUP & STOCK CHECK =====
        
        # Get inventory item (we need the ID for the transaction)
        inv_q = select(Inventory).where(Inventory.product_id == product_id)
        inv_res = await session.execute(inv_q)
        inventory_item = inv_res.scalar_one_or_none()
        
        if not inventory_item:
            raise ProductNotFoundError(f"Inventory record for product {product_id} not found")
        
        stock_before = inventory_item.total_stock
        
        # Pre-check stock (will be re-checked atomically in UPDATE)
        if stock_before < quantity:
            raise InsufficientStockError(
                f"Insufficient stock: requested {quantity}, available {stock_before}"
            )

        # ===== ATOMIC WRITE PHASE =====
        
        # Perform atomic inventory update with WHERE clause to prevent negative stock
        # This is the critical section - uses optimistic locking via version column
        upd = (
            update(Inventory)
            .where(Inventory.product_id == product_id)
            .where(Inventory.total_stock >= quantity)  # CRITICAL: prevents negative stock
            .values(
                total_stock=Inventory.total_stock - quantity,
                total_sold=Inventory.total_sold + quantity,
                version=Inventory.version + 1,
            )
        )
        res_upd = await session.execute(upd)
        if res_upd.rowcount == 0:
            # Either concurrent modification or stock dropped below requested quantity
            raise InsufficientStockError("Insufficient stock or concurrent modification - please retry")

        # Normalize channel
        normalized_channel = normalize_channel(sale_channel)

        # Parse sale_date if provided
        parsed_sale_date = None
        if sale_date:
            try:
                from datetime import datetime as dt
                parsed_sale_date = dt.fromisoformat(sale_date.replace('Z', '+00:00'))
            except (ValueError, AttributeError):
                pass  # Keep as None if parsing fails

        # Insert sale record
        total_amount = float(unit_price) * int(quantity)
        sale = Sale(
            product_id=product_id,
            quantity=quantity,
            unit_price=int(unit_price),
            total_amount=int(total_amount),
            sold_by_user_id=sold_by_user_id,
            sale_channel=normalized_channel,
            related_order_id=related_order_id,
            location=location,
            idempotency_key=idempotency_key,
            # Forms Extension fields
            reference=reference,
            customer_name=customer_name,
            customer_phone=customer_phone,
            discount=discount,
            payment_method=payment_method,
            sale_date=parsed_sale_date,
            linked_order_id=linked_order_id,
            # Affiliate fields (all nullable/optional)
            affiliate_code=affiliate_code if affiliate_code else None,
            affiliate_name=affiliate_name if affiliate_name else None,
            affiliate_source=affiliate_source if affiliate_source else None,
        )
        session.add(sale)
        await session.flush()  # Get sale ID

        # Create inventory transaction (ledger entry) - ALWAYS created for auditing
        transaction = InventoryTransaction(
            inventory_item_id=inventory_item.id,
            change=-quantity,  # Negative for sale
            reason="sale",
            related_sale_id=sale.id,
            related_order_id=related_order_id,
            performed_by_id=sold_by_user_id,
            notes=f"Sale recorded via {normalized_channel}" + (f" | Customer: {customer_name}" if customer_name else ""),
        )
        session.add(transaction)

        # ===== COMMIT - Atomic transaction complete =====
        await session.commit()

    except SalesError:
        # Known sales errors - rollback and re-raise with proper HTTP code
        await session.rollback()
        raise
    except Exception as e:
        # Unexpected error - rollback and wrap in ValidationError
        await session.rollback()
        logger.exception(f"[Sales] Unexpected error during sale recording: {e}")
        raise ValidationError(f"Sale recording failed: {str(e)}")

    # Attach stock info to sale object for response
    sale.stock_before = stock_before
    sale.stock_after = stock_before - quantity
    sale.product_name = inventory_item.product_name

    # ========== SIDE EFFECTS (after commit, non-blocking) ==========
    try:
        # Refresh inventory to get updated stock
        await session.refresh(inventory_item)
        
        # Emit sale:created event (canonical event name)
        await emit_event('sale:created', {
            'sale_id': sale.id,
            'product_id': sale.product_id,
            'quantity': sale.quantity,
            'channel': sale.sale_channel,
        })
        
        # Emit inventory:updated event
        await emit_event('inventory:updated', {
            'product_id': sale.product_id,
            'stock_before': stock_before,
            'stock_after': sale.stock_after,
            'change': -quantity,
            'reason': 'sale',
            'sale_id': sale.id,
        })

        # Check for low stock and trigger automation event (pass previous stock to avoid repeated alerts)
        if SALES_AUTOMATION_ENABLED:
            await _check_low_stock_trigger(session, inventory_item, sold_by_user_id, previous_stock=stock_before)
    except Exception as e:
        # Side effects failing should NOT invalidate the sale
        logger.warning(f"[Sales] Side effect failed (sale still valid): {e}")

    logger.info(f"[Sales] Sale {sale.id} recorded: product={product_id}, qty={quantity}, by_user={sold_by_user_id}")

    return sale


# ============================================================================
# High-Level API for Slash Commands
# ============================================================================

# Legacy function for name-based lookup (slash commands only)
async def resolve_product_by_name_or_id(
    session: AsyncSession,
    product_ref: str
) -> Tuple[int, str, Inventory]:
    """
    Legacy: Resolve product by ID or name (for slash commands only).
    API endpoints should use resolve_product_by_id().
    """
    if not product_ref or not str(product_ref).strip():
        raise ValidationError("Product is required")
    
    raw = str(product_ref).strip()
    
    # Try as ID first
    try:
        product_id = int(raw)
        return await resolve_product_by_id(session, product_id)
    except (ValueError, TypeError):
        pass
    except ProductNotFoundError:
        pass  # Fall through to name search
    
    # Fallback to name search
    norm = raw.lower()
    res = await session.execute(select(Inventory).where(func.lower(Inventory.product_name) == norm))
    inv = res.scalar_one_or_none()
    if inv:
        return inv.product_id, inv.product_name, inv
    
    raise ProductNotFoundError(f"Product '{raw}' not found")


async def create_sale_from_command(
    session: AsyncSession,
    user_id: int,
    product_ref: str,
    quantity: int,
    unit_price: float,
    channel: Optional[str] = None,
    customer_name: Optional[str] = None,
    dry_run: bool = False,
) -> SaleResult:
    """
    High-level function for slash command (allows name-based lookup).
    
    Note: API endpoints should use record_sale() with product_id directly.
    
    Handles:
    1. Input normalization
    2. Product resolution (by ID or name)
    3. Stock check
    4. Sale recording (if not dry_run)
    
    Returns: SaleResult dataclass
    Raises: ValidationError, ProductNotFoundError, InsufficientStockError
    """
    # Resolve product (allows name for slash commands)
    product_id, product_name, _ = await resolve_product_by_name_or_id(session, product_ref)
    
    # Validate input using the resolved product_id
    sale_input = await validate_sale_input(
        session, product_id, quantity, unit_price, channel, customer_name
    )
    
    # Check stock availability
    stock_before, stock_after = await check_stock_availability(
        session, sale_input.product_id, quantity
    )
    
    total_amount = unit_price * quantity
    
    if dry_run:
        # Return preview without recording
        return SaleResult(
            sale_id=0,  # No ID for dry run
            product_name=sale_input.product_name,
            quantity=quantity,
            unit_price=unit_price,
            total_amount=total_amount,
            channel=sale_input.channel,
            stock_before=stock_before,
            stock_after=stock_after,
            customer_name=customer_name,
        )
    
    # Record the sale
    sale = await record_sale(
        session,
        product_id=sale_input.product_id,
        quantity=quantity,
        unit_price=unit_price,
        sold_by_user_id=user_id,
        sale_channel=channel,
        customer_name=customer_name,
    )
    
    return SaleResult(
        sale_id=sale.id,
        product_name=sale_input.product_name,
        quantity=sale.quantity,
        unit_price=float(sale.unit_price),
        total_amount=float(sale.total_amount),
        channel=sale.sale_channel,
        stock_before=sale.stock_before,
        stock_after=sale.stock_after,
        customer_name=customer_name,
    )


async def _check_low_stock_trigger(
    session: AsyncSession,
    inventory_item: Inventory,
    triggered_by_user_id: int,
    previous_stock: int | None = None,
) -> None:
    """
    Check if inventory is below threshold and emit low stock automation event.
    If `previous_stock` is provided, trigger **only** when crossing from >threshold -> <= threshold.
    """
    threshold = inventory_item.low_stock_threshold or DEFAULT_LOW_STOCK_THRESHOLD

    # If previous_stock provided, only trigger when crossing from safe -> low
    if previous_stock is not None:
        if previous_stock <= threshold:
            # already low before — do not retrigger
            return
        if inventory_item.total_stock > threshold:
            # still above threshold — nothing to do
            return
    else:
        # No previous_stock provided: keep legacy behavior (trigger whenever at/below threshold)
        if inventory_item.total_stock > threshold:
            return

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
    # Use 'field' channel for agent sales (agents work in the field)
    query = select(
        Sale.sold_by_user_id,
        func.count(Sale.id).label('total_sales'),
        func.coalesce(func.sum(Sale.quantity), 0).label('total_quantity'),
        func.coalesce(func.sum(Sale.total_amount), 0).label('total_amount'),
    ).where(Sale.sale_channel == SaleChannel.field.value).group_by(Sale.sold_by_user_id)
    
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


async def generate_daily_sales_summary(
    session: AsyncSession,
    date: Optional[datetime] = None,
) -> str:
    """Generate a markdown-formatted daily sales summary for the given date (UTC).
    Returns a markdown string with totals, top product, top agent, and low-stock list.
    """
    # Determine date range (UTC midnight -> next midnight)
    if date is None:
        date = datetime.utcnow()
    start = datetime(date.year, date.month, date.day)
    end = start + timedelta(days=1)

    # Aggregated totals (reuse existing helper)
    summary = await get_sales_summary(session, start_date=start, end_date=end)

    # Top product by revenue
    top_product = None
    try:
        prod_q = select(Sale.product_id, func.coalesce(func.sum(Sale.total_amount), 0).label('amount')).where(
            Sale.created_at >= start, Sale.created_at < end
        ).group_by(Sale.product_id).order_by(func.sum(Sale.total_amount).desc()).limit(1)
        prod_res = await session.execute(prod_q)
        prod_row = prod_res.one_or_none()
        if prod_row:
            prod_id = prod_row[0]
            amount = float(prod_row[1] or 0)
            # Try to resolve product name from Inventory
            pname = None
            try:
                inv_q = select(Inventory).where(Inventory.product_id == prod_id)
                inv_res = await session.execute(inv_q)
                inv = inv_res.scalar_one_or_none()
                if inv:
                    pname = inv.product_name or f"Product {prod_id}"
            except Exception:
                pname = f"Product {prod_id}"
            top_product = {"product_id": prod_id, "product_name": pname, "amount": amount}
    except Exception:
        top_product = None

    # Top agent
    top_agent = None
    try:
        agents = await get_agent_performance(session, start_date=start, end_date=end)
        if agents and len(agents) > 0:
            top = agents[0]
            top_agent = {"user_id": top.get('user_id'), "username": top.get('username'), "display_name": top.get('display_name'), "total_amount": top.get('total_amount'), "total_quantity": top.get('total_quantity')}
    except Exception:
        top_agent = None

    # Low stock items (simple list)
    low_items = []
    try:
        li_q = select(Inventory).where(Inventory.total_stock <= Inventory.low_stock_threshold).order_by((Inventory.low_stock_threshold - Inventory.total_stock).desc()).limit(10)
        li_res = await session.execute(li_q)
        for inv in li_res.scalars().all():
            shortage = inv.low_stock_threshold - inv.total_stock
            low_items.append({"product_id": inv.product_id, "product_name": inv.product_name, "stock": inv.total_stock, "threshold": inv.low_stock_threshold, "shortage": shortage})
    except Exception:
        low_items = []

    # Build markdown
    lines = []
    lines.append(f"# Daily Sales Summary — {start.date().isoformat()}")
    lines.append("")
    lines.append("**Totals**")
    lines.append(f"- Sales: {summary.get('total_sales', 0)}")
    lines.append(f"- Units sold: {summary.get('total_quantity', 0)}")
    total_amt = summary.get('total_amount')
    if total_amt is not None:
        lines.append(f"- Revenue: ${float(total_amt):.2f}")
    else:
        lines.append(f"- Revenue: N/A")
    lines.append("")

    lines.append("**Top product**")
    if top_product:
        lines.append(f"- {top_product.get('product_name') or 'Unknown'} (ID: {top_product.get('product_id')}) — ${top_product.get('amount'):.2f}")
    else:
        lines.append("- None")
    lines.append("")

    lines.append("**Top agent**")
    if top_agent:
        display = top_agent.get('display_name') or top_agent.get('username') or f"User {top_agent.get('user_id')}"
        lines.append(f"- {display} — ${float(top_agent.get('total_amount') or 0):.2f} ({top_agent.get('total_quantity')} units)")
    else:
        lines.append("- None")
    lines.append("")

    lines.append("**Low stock items**")
    if low_items:
        for it in low_items:
            lines.append(f"- {it.get('product_name') or 'Product '+str(it.get('product_id'))}: {it.get('stock')} in stock (threshold {it.get('threshold')}, shortage {it.get('shortage')})")
    else:
        lines.append("- None")

    return "\n".join(lines)


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

    # Simple channel rule - field channel is for agents
    if sale.sale_channel != SaleChannel.field.value:
        return {"sale_id": sale.id, "commission_eligible": False, "exclusion_reason": 'channel_not_eligible'}

    # Amount threshold
    if float(sale.total_amount) < float(amount_threshold):
        return {"sale_id": sale.id, "commission_eligible": False, "exclusion_reason": 'amount_below_threshold'}

    # Related order check
    if sale.related_order_id is not None:
        o_q = select(Order).where(Order.id == sale.related_order_id)
        o_res = await session.execute(o_q)
        order = o_res.scalar_one_or_none()
        if not order or order.status not in ("awaiting_confirmation", "completed"):
            return {"sale_id": sale.id, "commission_eligible": False, "exclusion_reason": 'related_order_not_eligible'}

    return {"sale_id": sale.id, "commission_eligible": True, "exclusion_reason": None}
