"""
Processing Service Layer (Agriculture Phase)

Handles manufacturing/processing operations:
- Converting raw materials into finished goods
- Recipe validation
- Atomic inventory transactions
- Production analytics

Core Principles:
- Atomic transactions: all or nothing
- Explicit rollback on failure
- Audit trail via transactions
- No negative stock allowed
"""
from datetime import datetime
from typing import List, Optional, Dict, Any
import logging
import uuid

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, func
from sqlalchemy.orm import selectinload

from app.db.models import (
    Inventory, RawMaterial, ProcessingRecipe, ProcessingBatch,
    InventoryTransaction, RawMaterialTransaction
)
from app.db.enums import ProductType

logger = logging.getLogger(__name__)


# ============================================================================
# Custom Exceptions
# ============================================================================

class ProcessingError(Exception):
    """Base class for processing errors."""
    http_code: int = 500

class ValidationError(ProcessingError):
    """Invalid input (400)."""
    http_code = 400

class RecipeNotFoundError(ProcessingError):
    """Recipe not found (404)."""
    http_code = 404

class InsufficientRawMaterialError(ProcessingError):
    """Not enough raw material stock (409)."""
    http_code = 409

class ProductNotFoundError(ProcessingError):
    """Product not found (404)."""
    http_code = 404


# ============================================================================
# Recipe Management
# ============================================================================

async def get_recipe(
    session: AsyncSession,
    recipe_id: int
) -> Optional[ProcessingRecipe]:
    """Get a recipe by ID."""
    result = await session.execute(
        select(ProcessingRecipe)
        .options(selectinload(ProcessingRecipe.finished_product))
        .options(selectinload(ProcessingRecipe.raw_material))
        .where(ProcessingRecipe.id == recipe_id)
    )
    return result.scalar_one_or_none()


async def get_recipes_for_product(
    session: AsyncSession,
    finished_product_id: int,
    active_only: bool = True
) -> List[ProcessingRecipe]:
    """Get all recipes for a finished product."""
    query = select(ProcessingRecipe).where(
        ProcessingRecipe.finished_product_id == finished_product_id
    )
    if active_only:
        query = query.where(ProcessingRecipe.is_active == True)
    
    result = await session.execute(
        query.options(selectinload(ProcessingRecipe.raw_material))
    )
    return list(result.scalars().all())


async def create_recipe(
    session: AsyncSession,
    finished_product_id: int,
    raw_material_id: int,
    quantity_required: int,
    unit: str,
    waste_percentage: int = 0,
    notes: Optional[str] = None,
    created_by_id: Optional[int] = None,
) -> ProcessingRecipe:
    """
    Create a new processing recipe.
    
    Validates:
    - Finished product exists and is FINISHED_GOOD type
    - Raw material exists
    - Quantity is positive
    - Waste percentage is 0-100
    """
    # Validate finished product
    inv_result = await session.execute(
        select(Inventory).where(Inventory.id == finished_product_id)
    )
    finished_product = inv_result.scalar_one_or_none()
    if not finished_product:
        raise ProductNotFoundError(f"Finished product {finished_product_id} not found")
    
    # Validate raw material exists
    rm_result = await session.execute(
        select(RawMaterial).where(RawMaterial.id == raw_material_id)
    )
    raw_material = rm_result.scalar_one_or_none()
    if not raw_material:
        raise ProductNotFoundError(f"Raw material {raw_material_id} not found")
    
    # Validate inputs
    if quantity_required <= 0:
        raise ValidationError("quantity_required must be positive")
    if waste_percentage < 0 or waste_percentage > 100:
        raise ValidationError("waste_percentage must be between 0 and 100")
    
    recipe = ProcessingRecipe(
        finished_product_id=finished_product_id,
        raw_material_id=raw_material_id,
        quantity_required=quantity_required,
        unit=unit,
        waste_percentage=waste_percentage,
        notes=notes,
        created_by_id=created_by_id,
    )
    session.add(recipe)
    await session.commit()
    await session.refresh(recipe)
    
    logger.info(f"[Processing] Recipe {recipe.id} created for product {finished_product_id}")
    return recipe


async def update_recipe(
    session: AsyncSession,
    recipe_id: int,
    quantity_required: Optional[int] = None,
    unit: Optional[str] = None,
    waste_percentage: Optional[int] = None,
    notes: Optional[str] = None,
    is_active: Optional[bool] = None,
) -> ProcessingRecipe:
    """Update an existing recipe."""
    recipe = await get_recipe(session, recipe_id)
    if not recipe:
        raise RecipeNotFoundError(f"Recipe {recipe_id} not found")
    
    if quantity_required is not None:
        if quantity_required <= 0:
            raise ValidationError("quantity_required must be positive")
        recipe.quantity_required = quantity_required
    if unit is not None:
        recipe.unit = unit
    if waste_percentage is not None:
        if waste_percentage < 0 or waste_percentage > 100:
            raise ValidationError("waste_percentage must be between 0 and 100")
        recipe.waste_percentage = waste_percentage
    if notes is not None:
        recipe.notes = notes
    if is_active is not None:
        recipe.is_active = is_active
    
    await session.commit()
    await session.refresh(recipe)
    return recipe


# ============================================================================
# Processing Operations (Core Transaction)
# ============================================================================

async def calculate_raw_material_requirements(
    session: AsyncSession,
    finished_product_id: int,
    quantity_to_produce: int,
) -> List[Dict[str, Any]]:
    """
    Calculate raw materials needed for a production run.
    
    Returns list of: {raw_material_id, name, required, available, sufficient, unit}
    """
    recipes = await get_recipes_for_product(session, finished_product_id)
    if not recipes:
        raise RecipeNotFoundError(f"No active recipes found for product {finished_product_id}")
    
    requirements = []
    for recipe in recipes:
        # Calculate required amount including waste
        base_required = recipe.quantity_required * quantity_to_produce
        waste_factor = 1 + (recipe.waste_percentage or 0) / 100
        total_required = int(base_required * waste_factor)
        
        # Get current stock
        rm = recipe.raw_material
        available = rm.current_stock if rm else 0
        
        requirements.append({
            "raw_material_id": recipe.raw_material_id,
            "name": rm.name if rm else f"Material #{recipe.raw_material_id}",
            "required": total_required,
            "available": available,
            "sufficient": available >= total_required,
            "unit": recipe.unit,
            "recipe_id": recipe.id,
        })
    
    return requirements


async def process_batch(
    session: AsyncSession,
    finished_product_id: int,
    quantity_to_produce: int,
    processed_by_id: int,
    batch_reference: Optional[str] = None,
    notes: Optional[str] = None,
    actual_waste_quantity: int = 0,
    waste_notes: Optional[str] = None,
) -> ProcessingBatch:
    """
    Execute a processing batch - convert raw materials to finished goods.
    
    ATOMIC TRANSACTION:
    1. Validate recipes exist
    2. Check all raw materials have sufficient stock
    3. Deduct raw materials (PROCESSING_OUT transactions)
    4. Increase finished goods (PROCESSING_IN transaction)
    5. Create batch record with yield tracking
    
    On ANY failure: rollback everything.
    
    Yield Tracking:
    - expected_quantity: Based on recipe output ratio
    - quantity_produced: Actual output
    - actual_waste_quantity: Measured waste
    - yield_efficiency: (actual/expected) * 100
    
    Returns: ProcessingBatch with all related transactions
    """
    import json
    
    batch = None
    
    try:
        # ===== VALIDATION PHASE =====
        
        if quantity_to_produce <= 0:
            raise ValidationError("quantity_to_produce must be positive")
        
        if actual_waste_quantity < 0:
            raise ValidationError("actual_waste_quantity cannot be negative")
        
        # Get finished product
        inv_result = await session.execute(
            select(Inventory).where(Inventory.id == finished_product_id)
        )
        finished_product = inv_result.scalar_one_or_none()
        if not finished_product:
            raise ProductNotFoundError(f"Finished product {finished_product_id} not found")
        
        # Get and validate recipes
        recipes = await get_recipes_for_product(session, finished_product_id)
        if not recipes:
            raise RecipeNotFoundError(f"No active recipes found for product {finished_product_id}")
        
        # Calculate requirements and check stock
        requirements = await calculate_raw_material_requirements(
            session, finished_product_id, quantity_to_produce
        )
        
        insufficient = [r for r in requirements if not r["sufficient"]]
        if insufficient:
            details = ", ".join(
                f"{r['name']}: need {r['required']} {r['unit']}, have {r['available']}"
                for r in insufficient
            )
            raise InsufficientRawMaterialError(f"Insufficient raw materials: {details}")
        
        # ===== CALCULATE EXPECTED YIELD =====
        # Expected yield = quantity_to_produce (what user requested)
        # In practice this is always 100% for now since we produce what's requested
        expected_quantity = quantity_to_produce
        
        # Calculate yield efficiency
        yield_efficiency = None
        if expected_quantity > 0:
            yield_efficiency = int((quantity_to_produce / expected_quantity) * 100)
        
        # Snapshot raw materials used for reporting
        raw_materials_snapshot = [
            {
                "raw_material_id": req["raw_material_id"],
                "name": req["name"],
                "quantity_used": req["required"],
                "unit": req["unit"],
            }
            for req in requirements
        ]
        
        # ===== ATOMIC WRITE PHASE =====
        
        # Generate batch reference if not provided
        if not batch_reference:
            batch_reference = f"BATCH-{datetime.utcnow().strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"
        
        # Create batch record first
        batch = ProcessingBatch(
            batch_reference=batch_reference,
            finished_product_id=finished_product_id,
            quantity_produced=quantity_to_produce,
            expected_quantity=expected_quantity,
            actual_waste_quantity=actual_waste_quantity,
            waste_notes=waste_notes,
            raw_materials_used=json.dumps(raw_materials_snapshot),
            yield_efficiency=yield_efficiency,
            status="completed",
            notes=notes,
            processed_by_id=processed_by_id,
            completed_at=datetime.utcnow(),
        )
        session.add(batch)
        await session.flush()  # Get batch ID
        
        # Deduct raw materials
        for req in requirements:
            # Update raw material stock
            rm_update = (
                update(RawMaterial)
                .where(RawMaterial.id == req["raw_material_id"])
                .where(RawMaterial.current_stock >= req["required"])  # Prevent negative
                .values(current_stock=RawMaterial.current_stock - req["required"])
            )
            result = await session.execute(rm_update)
            if result.rowcount == 0:
                raise InsufficientRawMaterialError(
                    f"Race condition: {req['name']} stock dropped below required amount"
                )
            
            # Create raw material transaction (PROCESSING_OUT)
            rm_tx = RawMaterialTransaction(
                raw_material_id=req["raw_material_id"],
                change=-req["required"],
                reason="processing_out",
                notes=f"Batch {batch_reference}: producing {quantity_to_produce} units of {finished_product.product_name}",
                performed_by_id=processed_by_id,
                related_batch_id=batch.id,
            )
            session.add(rm_tx)
        
        # Increase finished goods stock
        inv_update = (
            update(Inventory)
            .where(Inventory.id == finished_product_id)
            .values(
                total_stock=Inventory.total_stock + quantity_to_produce,
                version=Inventory.version + 1,
            )
        )
        await session.execute(inv_update)
        
        # Create inventory transaction (PROCESSING_IN)
        inv_tx = InventoryTransaction(
            inventory_item_id=finished_product.id,
            change=quantity_to_produce,
            reason="processing_in",
            related_batch_id=batch.id,
            performed_by_id=processed_by_id,
            notes=f"Batch {batch_reference}: produced from raw materials",
        )
        session.add(inv_tx)
        
        # ===== COMMIT =====
        await session.commit()
        await session.refresh(batch)
        
        logger.info(
            f"[Processing] Batch {batch.id} completed: "
            f"{quantity_to_produce} units of product {finished_product_id}"
        )
        
        return batch
        
    except ProcessingError:
        await session.rollback()
        raise
    except Exception as e:
        await session.rollback()
        logger.exception(f"[Processing] Unexpected error during batch processing: {e}")
        raise ValidationError(f"Processing failed: {str(e)}")


async def get_batch(
    session: AsyncSession,
    batch_id: int
) -> Optional[ProcessingBatch]:
    """Get a processing batch with related transactions."""
    result = await session.execute(
        select(ProcessingBatch)
        .options(
            selectinload(ProcessingBatch.finished_product),
            selectinload(ProcessingBatch.processed_by),
            selectinload(ProcessingBatch.raw_material_transactions)
            .selectinload(RawMaterialTransaction.raw_material),
        )
        .where(ProcessingBatch.id == batch_id)
    )
    return result.scalar_one_or_none()


async def list_batches(
    session: AsyncSession,
    finished_product_id: Optional[int] = None,
    status: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
) -> List[ProcessingBatch]:
    """List processing batches with optional filters."""
    query = select(ProcessingBatch).order_by(ProcessingBatch.created_at.desc())
    
    if finished_product_id:
        query = query.where(ProcessingBatch.finished_product_id == finished_product_id)
    if status:
        query = query.where(ProcessingBatch.status == status)
    
    query = query.limit(limit).offset(offset)
    result = await session.execute(
        query.options(selectinload(ProcessingBatch.finished_product))
    )
    return list(result.scalars().all())


# ============================================================================
# Analytics (Admin Only)
# ============================================================================

async def get_raw_material_usage_stats(
    session: AsyncSession,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
) -> List[Dict[str, Any]]:
    """
    Get raw material usage statistics for production.
    
    Returns aggregated usage per raw material for processing operations.
    """
    query = select(
        RawMaterialTransaction.raw_material_id,
        RawMaterial.name,
        func.sum(func.abs(RawMaterialTransaction.change)).label("total_used"),
        func.count(RawMaterialTransaction.id).label("batch_count"),
    ).join(
        RawMaterial, RawMaterialTransaction.raw_material_id == RawMaterial.id
    ).where(
        RawMaterialTransaction.reason == "processing_out"
    ).group_by(
        RawMaterialTransaction.raw_material_id,
        RawMaterial.name
    )
    
    if start_date:
        query = query.where(RawMaterialTransaction.created_at >= start_date)
    if end_date:
        query = query.where(RawMaterialTransaction.created_at <= end_date)
    
    result = await session.execute(query)
    rows = result.all()
    
    return [
        {
            "raw_material_id": row.raw_material_id,
            "name": row.name,
            "total_used": int(row.total_used or 0),
            "batch_count": row.batch_count or 0,
        }
        for row in rows
    ]


async def get_finished_goods_yield_stats(
    session: AsyncSession,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
) -> List[Dict[str, Any]]:
    """
    Get finished goods production statistics.
    
    Returns aggregated yield per finished product.
    """
    query = select(
        ProcessingBatch.finished_product_id,
        Inventory.product_name,
        func.sum(ProcessingBatch.quantity_produced).label("total_produced"),
        func.count(ProcessingBatch.id).label("batch_count"),
    ).join(
        Inventory, ProcessingBatch.finished_product_id == Inventory.id
    ).where(
        ProcessingBatch.status == "completed"
    ).group_by(
        ProcessingBatch.finished_product_id,
        Inventory.product_name
    )
    
    if start_date:
        query = query.where(ProcessingBatch.created_at >= start_date)
    if end_date:
        query = query.where(ProcessingBatch.created_at <= end_date)
    
    result = await session.execute(query)
    rows = result.all()
    
    return [
        {
            "finished_product_id": row.finished_product_id,
            "product_name": row.product_name or f"Product #{row.finished_product_id}",
            "total_produced": int(row.total_produced or 0),
            "batch_count": row.batch_count or 0,
        }
        for row in rows
    ]


async def get_processing_overview(
    session: AsyncSession,
) -> Dict[str, Any]:
    """
    Get overall processing statistics for admin dashboard.
    """
    # Total batches
    batch_count_result = await session.execute(
        select(func.count(ProcessingBatch.id))
    )
    total_batches = batch_count_result.scalar() or 0
    
    # Total finished goods produced
    total_produced_result = await session.execute(
        select(func.sum(ProcessingBatch.quantity_produced))
        .where(ProcessingBatch.status == "completed")
    )
    total_produced = int(total_produced_result.scalar() or 0)
    
    # Total raw materials consumed (via processing)
    total_consumed_result = await session.execute(
        select(func.sum(func.abs(RawMaterialTransaction.change)))
        .where(RawMaterialTransaction.reason == "processing_out")
    )
    total_consumed = int(total_consumed_result.scalar() or 0)
    
    # Active recipes count
    recipes_count_result = await session.execute(
        select(func.count(ProcessingRecipe.id))
        .where(ProcessingRecipe.is_active == True)
    )
    active_recipes = recipes_count_result.scalar() or 0
    
    # Products with recipes (finished goods)
    products_with_recipes_result = await session.execute(
        select(func.count(func.distinct(ProcessingRecipe.finished_product_id)))
        .where(ProcessingRecipe.is_active == True)
    )
    products_with_recipes = products_with_recipes_result.scalar() or 0
    
    return {
        "total_batches": total_batches,
        "total_produced": total_produced,
        "total_raw_materials_consumed": total_consumed,
        "active_recipes": active_recipes,
        "products_with_recipes": products_with_recipes,
    }


# ============================================================================
# Production Reporting (Yield & Waste Analysis)
# ============================================================================

async def get_production_report(
    session: AsyncSession,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    finished_product_id: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Comprehensive production report with yield and waste analysis.
    
    Returns:
    - Summary: total batches, total produced, total waste
    - By product: breakdown per finished good
    - Yield efficiency: average efficiency across batches
    - Waste analysis: total waste by product
    """
    import json
    
    # Base query for batches
    query = select(ProcessingBatch).where(ProcessingBatch.status == "completed")
    
    if start_date:
        query = query.where(ProcessingBatch.created_at >= start_date)
    if end_date:
        query = query.where(ProcessingBatch.created_at <= end_date)
    if finished_product_id:
        query = query.where(ProcessingBatch.finished_product_id == finished_product_id)
    
    result = await session.execute(
        query.options(selectinload(ProcessingBatch.finished_product))
    )
    batches = list(result.scalars().all())
    
    # Calculate aggregates
    total_batches = len(batches)
    total_produced = sum(b.quantity_produced for b in batches)
    total_expected = sum(b.expected_quantity or b.quantity_produced for b in batches)
    total_waste = sum(b.actual_waste_quantity or 0 for b in batches)
    
    # Calculate overall yield efficiency
    avg_yield_efficiency = None
    batches_with_yield = [b for b in batches if b.yield_efficiency is not None]
    if batches_with_yield:
        avg_yield_efficiency = int(sum(b.yield_efficiency for b in batches_with_yield) / len(batches_with_yield))
    
    # Breakdown by product
    product_breakdown = {}
    for batch in batches:
        pid = batch.finished_product_id
        if pid not in product_breakdown:
            product_breakdown[pid] = {
                "finished_product_id": pid,
                "product_name": batch.finished_product.product_name if batch.finished_product else f"Product #{pid}",
                "batch_count": 0,
                "total_produced": 0,
                "total_expected": 0,
                "total_waste": 0,
                "yield_efficiencies": [],
            }
        
        product_breakdown[pid]["batch_count"] += 1
        product_breakdown[pid]["total_produced"] += batch.quantity_produced
        product_breakdown[pid]["total_expected"] += batch.expected_quantity or batch.quantity_produced
        product_breakdown[pid]["total_waste"] += batch.actual_waste_quantity or 0
        if batch.yield_efficiency is not None:
            product_breakdown[pid]["yield_efficiencies"].append(batch.yield_efficiency)
    
    # Calculate average yield efficiency per product
    for pid, data in product_breakdown.items():
        efficiencies = data.pop("yield_efficiencies")
        data["avg_yield_efficiency"] = int(sum(efficiencies) / len(efficiencies)) if efficiencies else None
    
    return {
        "summary": {
            "total_batches": total_batches,
            "total_produced": total_produced,
            "total_expected": total_expected,
            "total_waste": total_waste,
            "avg_yield_efficiency": avg_yield_efficiency,
        },
        "by_product": list(product_breakdown.values()),
        "period": {
            "start_date": start_date.isoformat() if start_date else None,
            "end_date": end_date.isoformat() if end_date else None,
        },
    }


async def get_waste_report(
    session: AsyncSession,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
) -> Dict[str, Any]:
    """
    Waste analysis report.
    
    Returns waste totals and breakdown by batch with notes.
    """
    query = (
        select(ProcessingBatch)
        .where(ProcessingBatch.status == "completed")
        .where(ProcessingBatch.actual_waste_quantity > 0)
        .order_by(ProcessingBatch.created_at.desc())
    )
    
    if start_date:
        query = query.where(ProcessingBatch.created_at >= start_date)
    if end_date:
        query = query.where(ProcessingBatch.created_at <= end_date)
    
    result = await session.execute(
        query.options(selectinload(ProcessingBatch.finished_product))
    )
    batches_with_waste = list(result.scalars().all())
    
    total_waste = sum(b.actual_waste_quantity or 0 for b in batches_with_waste)
    
    waste_entries = [
        {
            "batch_id": b.id,
            "batch_reference": b.batch_reference,
            "finished_product_id": b.finished_product_id,
            "product_name": b.finished_product.product_name if b.finished_product else None,
            "quantity_produced": b.quantity_produced,
            "waste_quantity": b.actual_waste_quantity,
            "waste_notes": b.waste_notes,
            "created_at": b.created_at.isoformat() if b.created_at else None,
        }
        for b in batches_with_waste
    ]
    
    return {
        "total_waste": total_waste,
        "batches_with_waste": len(batches_with_waste),
        "waste_entries": waste_entries,
    }
