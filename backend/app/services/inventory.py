"""
Inventory Service Layer (Phase 6.3)
Handles inventory management, restocking, and transaction tracking.
"""
from datetime import datetime
from typing import Optional
import os
import logging

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, func
from sqlalchemy.orm import selectinload

from app.db.models import Inventory, InventoryTransaction
from app.services.task_engine import emit_event

logger = logging.getLogger(__name__)


async def get_inventory_item(
    session: AsyncSession,
    product_id: int,
) -> Optional[Inventory]:
    """Get inventory item by product ID."""
    q = select(Inventory).where(Inventory.product_id == product_id)
    res = await session.execute(q)
    return res.scalar_one_or_none()


async def get_inventory_by_id(
    session: AsyncSession,
    inventory_id: int,
) -> Optional[Inventory]:
    """Get inventory item by ID."""
    q = select(Inventory).where(Inventory.id == inventory_id)
    res = await session.execute(q)
    return res.scalar_one_or_none()


async def list_inventory(
    session: AsyncSession,
    include_low_stock_only: bool = False,
    limit: int = 100,
    offset: int = 0,
) -> list[Inventory]:
    """
    List all inventory items with optional filtering.
    
    Args:
        session: Database session
        include_low_stock_only: If True, only return items below threshold
        limit: Maximum items to return
        offset: Pagination offset
    
    Returns:
        List of Inventory items
    """
    query = select(Inventory)
    
    if include_low_stock_only:
        query = query.where(Inventory.total_stock <= Inventory.low_stock_threshold)
    
    query = query.order_by(Inventory.product_id).limit(limit).offset(offset)
    
    result = await session.execute(query)
    return list(result.scalars().all())


async def create_inventory_item(
    session: AsyncSession,
    product_id: int,
    product_name: Optional[str] = None,
    initial_stock: int = 0,
    low_stock_threshold: int = 10,
    created_by_id: Optional[int] = None,
) -> Inventory:
    """
    Create a new inventory item.
    
    Args:
        session: Database session
        product_id: External product ID
        product_name: Human-readable name
        initial_stock: Starting stock count
        low_stock_threshold: Threshold for low stock alerts
        created_by_id: User creating the item
        
    Returns:
        The created Inventory item
        
    Raises:
        ValueError: If product_id already exists
    """
    # Check if already exists
    existing = await get_inventory_item(session, product_id)
    if existing:
        raise ValueError(f"Inventory item for product {product_id} already exists")
    
    inventory = Inventory(
        product_id=product_id,
        product_name=product_name,
        total_stock=initial_stock,
        total_sold=0,
        low_stock_threshold=low_stock_threshold,
    )
    session.add(inventory)
    await session.flush()  # Get ID
    
    # Record initial stock as transaction if > 0
    if initial_stock > 0:
        transaction = InventoryTransaction(
            inventory_item_id=inventory.id,
            change=initial_stock,
            reason="initial",
            performed_by_id=created_by_id,
            notes="Initial inventory setup",
        )
        session.add(transaction)
    
    await session.commit()
    
    await emit_event('inventory.created', {
        'inventory_id': inventory.id,
        'product_id': product_id,
        'product_name': product_name,
        'initial_stock': initial_stock,
    })
    
    logger.info(f"[Inventory] Created item: product_id={product_id}, stock={initial_stock}")
    
    return inventory


async def restock_inventory(
    session: AsyncSession,
    product_id: int,
    quantity: int,
    performed_by_id: int,
    related_order_id: Optional[int] = None,
    notes: Optional[str] = None,
) -> Inventory:
    """
    Add stock to an inventory item.
    
    Args:
        session: Database session
        product_id: Product to restock
        quantity: Amount to add (must be positive)
        performed_by_id: User performing the restock
        related_order_id: Optional order that triggered this restock
        notes: Optional notes about the restock
        
    Returns:
        Updated Inventory item
        
    Raises:
        ValueError: If quantity <= 0 or product not found
    """
    if quantity <= 0:
        raise ValueError("Restock quantity must be > 0")
    
    inventory = await get_inventory_item(session, product_id)
    if not inventory:
        raise ValueError("Inventory item not found")
    
    # Update stock atomically
    upd = (
        update(Inventory)
        .where(Inventory.id == inventory.id)
        .values(
            total_stock=Inventory.total_stock + quantity,
            version=Inventory.version + 1,
        )
    )
    await session.execute(upd)
    
    # Create transaction record
    transaction = InventoryTransaction(
        inventory_item_id=inventory.id,
        change=quantity,  # Positive for restock
        reason="restock",
        related_order_id=related_order_id,
        performed_by_id=performed_by_id,
        notes=notes or "Manual restock",
    )
    session.add(transaction)
    
    await session.commit()
    await session.refresh(inventory)
    
    await emit_event('inventory.restocked', {
        'inventory_id': inventory.id,
        'product_id': product_id,
        'quantity_added': quantity,
        'new_stock': inventory.total_stock,
        'performed_by': performed_by_id,
    })
    
    logger.info(f"[Inventory] Restocked: product_id={product_id}, +{quantity}, new_stock={inventory.total_stock}")
    
    return inventory


async def adjust_inventory(
    session: AsyncSession,
    product_id: int,
    adjustment: int,
    performed_by_id: int,
    reason: str = "adjustment",
    notes: Optional[str] = None,
) -> Inventory:
    """
    Adjust inventory (up or down) for corrections, returns, etc.
    
    Args:
        session: Database session
        product_id: Product to adjust
        adjustment: Amount to add (positive) or remove (negative)
        performed_by_id: User performing the adjustment
        reason: Reason for adjustment (adjustment, return, correction, damage)
        notes: Optional notes
        
    Returns:
        Updated Inventory item
        
    Raises:
        ValueError: If adjustment would result in negative stock
    """
    if adjustment == 0:
        raise ValueError("Adjustment cannot be zero")
    
    inventory = await get_inventory_item(session, product_id)
    if not inventory:
        raise ValueError("Inventory item not found")
    
    new_stock = inventory.total_stock + adjustment
    if new_stock < 0:
        raise ValueError(f"Adjustment would result in negative stock ({new_stock})")
    
    # Update stock atomically
    upd = (
        update(Inventory)
        .where(Inventory.id == inventory.id)
        .where(Inventory.total_stock + adjustment >= 0)  # Safety check
        .values(
            total_stock=Inventory.total_stock + adjustment,
            version=Inventory.version + 1,
        )
    )
    result = await session.execute(upd)
    
    if result.rowcount == 0:
        raise ValueError("Adjustment would result in negative stock")
    
    # Create transaction record
    transaction = InventoryTransaction(
        inventory_item_id=inventory.id,
        change=adjustment,
        reason=reason,
        performed_by_id=performed_by_id,
        notes=notes,
    )
    session.add(transaction)
    
    await session.commit()
    await session.refresh(inventory)
    
    await emit_event('inventory.adjusted', {
        'inventory_id': inventory.id,
        'product_id': product_id,
        'adjustment': adjustment,
        'reason': reason,
        'new_stock': inventory.total_stock,
        'performed_by': performed_by_id,
    })
    
    logger.info(f"[Inventory] Adjusted: product_id={product_id}, {adjustment:+d}, reason={reason}")
    
    return inventory


async def get_inventory_transactions(
    session: AsyncSession,
    product_id: Optional[int] = None,
    inventory_id: Optional[int] = None,
    reason: Optional[str] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    limit: int = 100,
    offset: int = 0,
) -> list[InventoryTransaction]:
    """
    Get inventory transactions with optional filters.
    
    Args:
        session: Database session
        product_id: Filter by product
        inventory_id: Filter by inventory item
        reason: Filter by reason (sale, restock, adjustment)
        start_date: Filter by start date
        end_date: Filter by end date
        limit: Maximum items to return
        offset: Pagination offset
        
    Returns:
        List of InventoryTransaction records
    """
    query = select(InventoryTransaction)
    
    if inventory_id:
        query = query.where(InventoryTransaction.inventory_item_id == inventory_id)
    elif product_id:
        # Join to get by product_id
        inv_q = select(Inventory.id).where(Inventory.product_id == product_id)
        query = query.where(InventoryTransaction.inventory_item_id.in_(inv_q))
    
    if reason:
        query = query.where(InventoryTransaction.reason == reason)
    if start_date:
        query = query.where(InventoryTransaction.created_at >= start_date)
    if end_date:
        query = query.where(InventoryTransaction.created_at < end_date)
    
    query = query.order_by(InventoryTransaction.created_at.desc()).limit(limit).offset(offset)
    
    result = await session.execute(query)
    return list(result.scalars().all())


async def get_inventory_summary(session: AsyncSession) -> dict:
    """
    Get overall inventory summary statistics.
    
    Returns:
        dict with total_items, total_stock, total_sold, low_stock_count
    """
    # Basic stats
    stats_q = select(
        func.count(Inventory.id).label('total_items'),
        func.coalesce(func.sum(Inventory.total_stock), 0).label('total_stock'),
        func.coalesce(func.sum(Inventory.total_sold), 0).label('total_sold'),
    )
    stats_res = await session.execute(stats_q)
    stats = stats_res.one()
    
    # Low stock count
    low_q = select(func.count(Inventory.id)).where(
        Inventory.total_stock <= Inventory.low_stock_threshold
    )
    low_res = await session.execute(low_q)
    low_stock_count = low_res.scalar()
    
    return {
        "total_items": stats[0],
        "total_stock": int(stats[1]),
        "total_sold": int(stats[2]),
        "low_stock_count": low_stock_count,
    }


async def update_low_stock_threshold(
    session: AsyncSession,
    product_id: int,
    new_threshold: int,
) -> Inventory:
    """
    Update the low stock threshold for a product.
    
    Args:
        session: Database session
        product_id: Product to update
        new_threshold: New threshold value
        
    Returns:
        Updated Inventory item
    """
    if new_threshold < 0:
        raise ValueError("Threshold must be >= 0")
    
    inventory = await get_inventory_item(session, product_id)
    if not inventory:
        raise ValueError("Inventory item not found")
    
    inventory.low_stock_threshold = new_threshold
    await session.commit()
    await session.refresh(inventory)
    
    logger.info(f"[Inventory] Updated threshold: product_id={product_id}, threshold={new_threshold}")
    
    return inventory

