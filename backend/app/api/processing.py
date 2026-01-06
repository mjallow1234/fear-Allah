"""
Processing API Endpoints (Agriculture Phase)

Handles:
- Recipe management (CRUD)
- Processing batches (manufacturing runs)
- Production analytics (admin-only)

All processing operations are admin-only.
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel

from app.core.security import get_current_user
from app.db.database import get_db
from app.db.models import User
from app.services.processing import (
    # Recipe management
    get_recipe,
    get_recipes_for_product,
    create_recipe,
    update_recipe,
    # Processing operations
    calculate_raw_material_requirements,
    process_batch,
    get_batch,
    list_batches,
    # Analytics
    get_raw_material_usage_stats,
    get_finished_goods_yield_stats,
    get_processing_overview,
    # Production reporting
    get_production_report,
    get_waste_report,
    # Exceptions
    ProcessingError,
    ValidationError as ProcessingValidationError,
    RecipeNotFoundError,
    InsufficientRawMaterialError,
    ProductNotFoundError,
)
from sqlalchemy import select

router = APIRouter()


# ============================================================================
# Helper Functions
# ============================================================================

async def _check_admin(db: AsyncSession, user_id: int) -> bool:
    """Check if user is admin (system_admin or team_admin)."""
    q = select(User.is_system_admin, User.role).where(User.id == user_id)
    result = await db.execute(q)
    row = result.one_or_none()
    if not row:
        return False
    return row[0] or row[1] in ('system_admin', 'team_admin')


# ============================================================================
# Pydantic Models
# ============================================================================

class RecipeCreate(BaseModel):
    finished_product_id: int
    raw_material_id: int
    quantity_required: int
    unit: str
    waste_percentage: int = 0
    notes: Optional[str] = None


class RecipeUpdate(BaseModel):
    quantity_required: Optional[int] = None
    unit: Optional[str] = None
    waste_percentage: Optional[int] = None
    notes: Optional[str] = None
    is_active: Optional[bool] = None


class ProcessBatchRequest(BaseModel):
    finished_product_id: int
    quantity_to_produce: int
    batch_reference: Optional[str] = None
    notes: Optional[str] = None
    actual_waste_quantity: int = 0  # Measured waste in units
    waste_notes: Optional[str] = None  # Notes about waste cause


# ============================================================================
# Recipe Endpoints
# ============================================================================

@router.get("/recipes")
async def list_recipes(
    active_only: bool = Query(True),
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List all recipes. Admin only."""
    user_id = current_user.get('user_id')
    if not await _check_admin(db, user_id):
        raise HTTPException(status_code=403, detail={"error": "permission_denied", "message": "Admin access required"})
    
    from app.db.models import ProcessingRecipe
    from sqlalchemy.orm import selectinload
    
    q = select(ProcessingRecipe).options(
        selectinload(ProcessingRecipe.finished_product),
        selectinload(ProcessingRecipe.raw_material)
    )
    if active_only:
        q = q.where(ProcessingRecipe.is_active == True)
    
    result = await db.execute(q)
    recipes = result.scalars().all()
    
    return [
        {
            "id": r.id,
            "finished_product_id": r.finished_product_id,
            "finished_product_name": r.finished_product.product_name if r.finished_product else None,
            "raw_material_id": r.raw_material_id,
            "raw_material_name": r.raw_material.name if r.raw_material else None,
            "quantity_required": r.quantity_required,
            "unit": r.unit,
            "waste_percentage": r.waste_percentage,
            "is_active": r.is_active,
        }
        for r in recipes
    ]


@router.get("/recipes/{recipe_id}")
async def get_recipe_endpoint(
    recipe_id: int,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get a specific recipe by ID."""
    user_id = current_user.get('user_id')
    if not await _check_admin(db, user_id):
        raise HTTPException(status_code=403, detail={"error": "permission_denied", "message": "Admin access required"})
    
    recipe = await get_recipe(db, recipe_id)
    if not recipe:
        raise HTTPException(status_code=404, detail={"error": "not_found", "message": f"Recipe {recipe_id} not found"})
    
    return {
        "id": recipe.id,
        "finished_product_id": recipe.finished_product_id,
        "finished_product_name": recipe.finished_product.product_name if recipe.finished_product else None,
        "raw_material_id": recipe.raw_material_id,
        "raw_material_name": recipe.raw_material.name if recipe.raw_material else None,
        "quantity_required": recipe.quantity_required,
        "unit": recipe.unit,
        "waste_percentage": recipe.waste_percentage,
        "notes": recipe.notes,
        "is_active": recipe.is_active,
        "created_at": recipe.created_at.isoformat() if recipe.created_at else None,
    }


@router.get("/recipes/product/{product_id}")
async def get_product_recipes(
    product_id: int,
    active_only: bool = Query(True),
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get all recipes for a finished product."""
    user_id = current_user.get('user_id')
    if not await _check_admin(db, user_id):
        raise HTTPException(status_code=403, detail={"error": "permission_denied", "message": "Admin access required"})
    
    recipes = await get_recipes_for_product(db, product_id, active_only)
    
    return {
        "product_id": product_id,
        "recipes": [
            {
                "id": r.id,
                "raw_material_id": r.raw_material_id,
                "raw_material_name": r.raw_material.name if r.raw_material else None,
                "quantity_required": r.quantity_required,
                "unit": r.unit,
                "waste_percentage": r.waste_percentage,
                "is_active": r.is_active,
            }
            for r in recipes
        ],
        "count": len(recipes),
    }


@router.post("/recipes")
async def create_recipe_endpoint(
    payload: RecipeCreate,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a new processing recipe. Admin only."""
    user_id = current_user.get('user_id')
    if not await _check_admin(db, user_id):
        raise HTTPException(status_code=403, detail={"error": "permission_denied", "message": "Admin access required"})
    
    try:
        recipe = await create_recipe(
            db,
            finished_product_id=payload.finished_product_id,
            raw_material_id=payload.raw_material_id,
            quantity_required=payload.quantity_required,
            unit=payload.unit,
            waste_percentage=payload.waste_percentage,
            notes=payload.notes,
            created_by_id=user_id,
        )
        return {
            "id": recipe.id,
            "finished_product_id": recipe.finished_product_id,
            "raw_material_id": recipe.raw_material_id,
            "quantity_required": recipe.quantity_required,
            "unit": recipe.unit,
            "waste_percentage": recipe.waste_percentage,
            "is_active": recipe.is_active,
            "created_at": recipe.created_at.isoformat() if recipe.created_at else None,
        }
    except ProductNotFoundError as e:
        raise HTTPException(status_code=404, detail={"error": "not_found", "message": str(e)})
    except ProcessingValidationError as e:
        raise HTTPException(status_code=400, detail={"error": "validation_error", "message": str(e)})
    except ProcessingError as e:
        raise HTTPException(status_code=getattr(e, 'http_code', 500), detail={"error": "processing_error", "message": str(e)})


@router.patch("/recipes/{recipe_id}")
async def update_recipe_endpoint(
    recipe_id: int,
    payload: RecipeUpdate,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update an existing recipe. Admin only."""
    user_id = current_user.get('user_id')
    if not await _check_admin(db, user_id):
        raise HTTPException(status_code=403, detail={"error": "permission_denied", "message": "Admin access required"})
    
    try:
        recipe = await update_recipe(
            db,
            recipe_id=recipe_id,
            quantity_required=payload.quantity_required,
            unit=payload.unit,
            waste_percentage=payload.waste_percentage,
            notes=payload.notes,
            is_active=payload.is_active,
        )
        return {
            "id": recipe.id,
            "finished_product_id": recipe.finished_product_id,
            "raw_material_id": recipe.raw_material_id,
            "quantity_required": recipe.quantity_required,
            "unit": recipe.unit,
            "waste_percentage": recipe.waste_percentage,
            "is_active": recipe.is_active,
            "updated_at": recipe.updated_at.isoformat() if recipe.updated_at else None,
        }
    except RecipeNotFoundError as e:
        raise HTTPException(status_code=404, detail={"error": "not_found", "message": str(e)})
    except ProcessingValidationError as e:
        raise HTTPException(status_code=400, detail={"error": "validation_error", "message": str(e)})


# ============================================================================
# Processing Batch Endpoints
# ============================================================================

@router.post("/batches/calculate")
async def calculate_requirements(
    payload: ProcessBatchRequest,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Calculate raw material requirements for a production run.
    Does NOT execute - just returns what would be needed.
    """
    user_id = current_user.get('user_id')
    if not await _check_admin(db, user_id):
        raise HTTPException(status_code=403, detail={"error": "permission_denied", "message": "Admin access required"})
    
    try:
        requirements = await calculate_raw_material_requirements(
            db, payload.finished_product_id, payload.quantity_to_produce
        )
        all_sufficient = all(r["sufficient"] for r in requirements)
        
        return {
            "finished_product_id": payload.finished_product_id,
            "quantity_to_produce": payload.quantity_to_produce,
            "requirements": requirements,
            "all_sufficient": all_sufficient,
            "can_process": all_sufficient,
        }
    except RecipeNotFoundError as e:
        raise HTTPException(status_code=404, detail={"error": "no_recipe", "message": str(e)})
    except ProductNotFoundError as e:
        raise HTTPException(status_code=404, detail={"error": "not_found", "message": str(e)})


@router.post("/batches")
async def execute_batch(
    payload: ProcessBatchRequest,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Execute a processing batch - convert raw materials to finished goods.
    
    This is an atomic operation:
    - All raw materials are deducted
    - Finished goods are added to inventory
    - All transactions are recorded
    - Yield/waste metrics captured
    
    On failure, everything is rolled back.
    """
    user_id = current_user.get('user_id')
    if not await _check_admin(db, user_id):
        raise HTTPException(status_code=403, detail={"error": "permission_denied", "message": "Admin access required"})
    
    try:
        batch = await process_batch(
            db,
            finished_product_id=payload.finished_product_id,
            quantity_to_produce=payload.quantity_to_produce,
            processed_by_id=user_id,
            batch_reference=payload.batch_reference,
            notes=payload.notes,
            actual_waste_quantity=payload.actual_waste_quantity,
            waste_notes=payload.waste_notes,
        )
        
        return {
            "batch_id": batch.id,
            "batch_reference": batch.batch_reference,
            "finished_product_id": batch.finished_product_id,
            "quantity_produced": batch.quantity_produced,
            "expected_quantity": batch.expected_quantity,
            "actual_waste_quantity": batch.actual_waste_quantity,
            "yield_efficiency": batch.yield_efficiency,
            "status": batch.status,
            "created_at": batch.created_at.isoformat() if batch.created_at else None,
            "completed_at": batch.completed_at.isoformat() if batch.completed_at else None,
        }
    except RecipeNotFoundError as e:
        raise HTTPException(status_code=404, detail={"error": "no_recipe", "message": str(e)})
    except InsufficientRawMaterialError as e:
        raise HTTPException(status_code=409, detail={"error": "insufficient_materials", "message": str(e)})
    except ProductNotFoundError as e:
        raise HTTPException(status_code=404, detail={"error": "not_found", "message": str(e)})
    except ProcessingValidationError as e:
        raise HTTPException(status_code=400, detail={"error": "validation_error", "message": str(e)})
    except ProcessingError as e:
        raise HTTPException(status_code=getattr(e, 'http_code', 500), detail={"error": "processing_error", "message": str(e)})


@router.get("/batches/{batch_id}")
async def get_batch_endpoint(
    batch_id: int,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get details of a specific processing batch."""
    user_id = current_user.get('user_id')
    if not await _check_admin(db, user_id):
        raise HTTPException(status_code=403, detail={"error": "permission_denied", "message": "Admin access required"})
    
    batch = await get_batch(db, batch_id)
    if not batch:
        raise HTTPException(status_code=404, detail={"error": "not_found", "message": f"Batch {batch_id} not found"})
    
    import json
    raw_materials_snapshot = None
    if batch.raw_materials_used:
        try:
            raw_materials_snapshot = json.loads(batch.raw_materials_used)
        except:
            pass
    
    return {
        "id": batch.id,
        "batch_reference": batch.batch_reference,
        "finished_product_id": batch.finished_product_id,
        "finished_product_name": batch.finished_product.product_name if batch.finished_product else None,
        "quantity_produced": batch.quantity_produced,
        "expected_quantity": batch.expected_quantity,
        "actual_waste_quantity": batch.actual_waste_quantity,
        "waste_notes": batch.waste_notes,
        "yield_efficiency": batch.yield_efficiency,
        "raw_materials_used": raw_materials_snapshot,
        "status": batch.status,
        "notes": batch.notes,
        "processed_by_id": batch.processed_by_id,
        "processed_by_name": batch.processed_by.display_name if batch.processed_by else None,
        "raw_materials_consumed": [
            {
                "raw_material_id": tx.raw_material_id,
                "raw_material_name": tx.raw_material.name if tx.raw_material else None,
                "quantity": abs(tx.change),
            }
            for tx in batch.raw_material_transactions
        ],
        "created_at": batch.created_at.isoformat() if batch.created_at else None,
        "completed_at": batch.completed_at.isoformat() if batch.completed_at else None,
    }


@router.get("/batches")
async def list_batches_endpoint(
    finished_product_id: Optional[int] = Query(None),
    status: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List processing batches with optional filters."""
    user_id = current_user.get('user_id')
    if not await _check_admin(db, user_id):
        raise HTTPException(status_code=403, detail={"error": "permission_denied", "message": "Admin access required"})
    
    batches = await list_batches(db, finished_product_id, status, limit, offset)
    
    return {
        "batches": [
            {
                "id": b.id,
                "batch_reference": b.batch_reference,
                "finished_product_id": b.finished_product_id,
                "finished_product_name": b.finished_product.product_name if b.finished_product else None,
                "quantity_produced": b.quantity_produced,
                "status": b.status,
                "created_at": b.created_at.isoformat() if b.created_at else None,
            }
            for b in batches
        ],
        "count": len(batches),
    }


# ============================================================================
# Analytics Endpoints (Admin Only)
# ============================================================================

@router.get("/analytics/overview")
async def get_overview(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get overall processing statistics for admin dashboard."""
    user_id = current_user.get('user_id')
    if not await _check_admin(db, user_id):
        raise HTTPException(status_code=403, detail={"error": "permission_denied", "message": "Admin access required"})
    
    return await get_processing_overview(db)


@router.get("/analytics/raw-material-usage")
async def get_raw_material_usage(
    start_date: Optional[str] = Query(None, description="ISO date YYYY-MM-DD"),
    end_date: Optional[str] = Query(None, description="ISO date YYYY-MM-DD"),
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get raw material usage statistics for processing operations."""
    user_id = current_user.get('user_id')
    if not await _check_admin(db, user_id):
        raise HTTPException(status_code=403, detail={"error": "permission_denied", "message": "Admin access required"})
    
    start_dt = None
    end_dt = None
    if start_date:
        try:
            start_dt = datetime.fromisoformat(start_date)
        except ValueError:
            raise HTTPException(status_code=400, detail={"error": "validation_error", "message": "Invalid start_date format"})
    if end_date:
        try:
            end_dt = datetime.fromisoformat(end_date)
        except ValueError:
            raise HTTPException(status_code=400, detail={"error": "validation_error", "message": "Invalid end_date format"})
    
    stats = await get_raw_material_usage_stats(db, start_dt, end_dt)
    return {
        "start_date": start_date,
        "end_date": end_date,
        "usage": stats,
    }


@router.get("/analytics/finished-goods-yield")
async def get_finished_goods_yield(
    start_date: Optional[str] = Query(None, description="ISO date YYYY-MM-DD"),
    end_date: Optional[str] = Query(None, description="ISO date YYYY-MM-DD"),
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get finished goods production statistics."""
    user_id = current_user.get('user_id')
    if not await _check_admin(db, user_id):
        raise HTTPException(status_code=403, detail={"error": "permission_denied", "message": "Admin access required"})
    
    start_dt = None
    end_dt = None
    if start_date:
        try:
            start_dt = datetime.fromisoformat(start_date)
        except ValueError:
            raise HTTPException(status_code=400, detail={"error": "validation_error", "message": "Invalid start_date format"})
    if end_date:
        try:
            end_dt = datetime.fromisoformat(end_date)
        except ValueError:
            raise HTTPException(status_code=400, detail={"error": "validation_error", "message": "Invalid end_date format"})
    
    stats = await get_finished_goods_yield_stats(db, start_dt, end_dt)
    return {
        "start_date": start_date,
        "end_date": end_date,
        "yield": stats,
    }


# ============================================================================
# Production Reporting Endpoints (Yield & Waste)
# ============================================================================

@router.get("/reports/production")
async def production_report(
    start_date: Optional[str] = Query(None, description="ISO date YYYY-MM-DD"),
    end_date: Optional[str] = Query(None, description="ISO date YYYY-MM-DD"),
    finished_product_id: Optional[int] = Query(None, description="Filter by product"),
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Comprehensive production report with yield and waste analysis.
    
    Returns:
    - Summary totals (batches, produced, waste)
    - Breakdown by finished product
    - Yield efficiency metrics
    """
    user_id = current_user.get('user_id')
    if not await _check_admin(db, user_id):
        raise HTTPException(status_code=403, detail={"error": "permission_denied", "message": "Admin access required"})
    
    start_dt = None
    end_dt = None
    if start_date:
        try:
            start_dt = datetime.fromisoformat(start_date)
        except ValueError:
            raise HTTPException(status_code=400, detail={"error": "validation_error", "message": "Invalid start_date format"})
    if end_date:
        try:
            end_dt = datetime.fromisoformat(end_date)
        except ValueError:
            raise HTTPException(status_code=400, detail={"error": "validation_error", "message": "Invalid end_date format"})
    
    return await get_production_report(db, start_dt, end_dt, finished_product_id)


@router.get("/reports/waste")
async def waste_report(
    start_date: Optional[str] = Query(None, description="ISO date YYYY-MM-DD"),
    end_date: Optional[str] = Query(None, description="ISO date YYYY-MM-DD"),
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Waste analysis report.
    
    Returns:
    - Total waste across all batches
    - Individual batch waste entries with notes
    """
    user_id = current_user.get('user_id')
    if not await _check_admin(db, user_id):
        raise HTTPException(status_code=403, detail={"error": "permission_denied", "message": "Admin access required"})
    
    start_dt = None
    end_dt = None
    if start_date:
        try:
            start_dt = datetime.fromisoformat(start_date)
        except ValueError:
            raise HTTPException(status_code=400, detail={"error": "validation_error", "message": "Invalid start_date format"})
    if end_date:
        try:
            end_dt = datetime.fromisoformat(end_date)
        except ValueError:
            raise HTTPException(status_code=400, detail={"error": "validation_error", "message": "Invalid end_date format"})
    
    return await get_waste_report(db, start_dt, end_dt)
