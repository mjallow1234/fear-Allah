"""
Raw Materials API Endpoints (Forms Extension)
Handles raw material inventory management.
Admin-only create/update operations.
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel

from app.core.security import get_current_user
from app.db.database import get_db
from app.db.models import User, RawMaterial, RawMaterialTransaction

router = APIRouter()


# ==================== Admin Overview ====================

@router.get("/overview/stats")
async def get_raw_materials_overview(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Get aggregated raw materials metrics. Admin only.
    Returns total count, low stock count, and usage statistics.
    """
    user_id = current_user.get('user_id')
    
    # Check admin access
    q = select(User.is_system_admin, User.role).where(User.id == user_id)
    result = await db.execute(q)
    row = result.one_or_none()
    if not row or not (row[0] or row[1] in ('system_admin', 'team_admin')):
        raise HTTPException(status_code=403, detail="Admin access required")
    
    # Count totals
    total_query = select(func.count(RawMaterial.id))
    total_result = await db.execute(total_query)
    total_materials = total_result.scalar() or 0
    
    # Count low stock
    low_stock_query = select(func.count(RawMaterial.id)).where(
        RawMaterial.current_stock <= RawMaterial.min_stock_level
    )
    low_stock_result = await db.execute(low_stock_query)
    low_stock_count = low_stock_result.scalar() or 0
    
    # Usage statistics from transactions
    tx_stats_query = select(
        func.sum(func.abs(RawMaterialTransaction.change)).filter(RawMaterialTransaction.change < 0).label('total_used'),
        func.sum(RawMaterialTransaction.change).filter(RawMaterialTransaction.change > 0).label('total_added'),
        func.count(RawMaterialTransaction.id).label('total_transactions')
    )
    tx_stats_result = await db.execute(tx_stats_query)
    tx_stats = tx_stats_result.one()
    
    return {
        "total_materials": total_materials,
        "low_stock_count": low_stock_count,
        "total_used": int(tx_stats.total_used or 0),
        "total_added": int(tx_stats.total_added or 0),
        "total_transactions": tx_stats.total_transactions or 0,
    }


# ==================== Schemas ====================

class RawMaterialCreate(BaseModel):
    name: str
    description: Optional[str] = None
    unit: str  # kg, liters, pieces, etc.
    current_stock: int = 0
    min_stock_level: Optional[int] = 0
    cost_per_unit: Optional[int] = None
    supplier: Optional[str] = None


class RawMaterialUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    unit: Optional[str] = None
    min_stock_level: Optional[int] = None
    cost_per_unit: Optional[int] = None
    supplier: Optional[str] = None


class StockAdjustment(BaseModel):
    change: int  # positive to add, negative to consume
    reason: str  # add, consume, adjust, return
    notes: Optional[str] = None


class RawMaterialResponse(BaseModel):
    id: int
    name: str
    description: Optional[str]
    unit: str
    current_stock: int
    min_stock_level: Optional[int]
    cost_per_unit: Optional[int]
    supplier: Optional[str]
    is_low_stock: bool
    created_at: Optional[datetime]
    updated_at: Optional[datetime]

    class Config:
        from_attributes = True


class RawMaterialTransactionResponse(BaseModel):
    id: int
    raw_material_id: int
    change: int
    reason: str
    notes: Optional[str]
    performed_by_id: Optional[int]
    created_at: Optional[datetime]

    class Config:
        from_attributes = True


# ==================== Helper Functions ====================

async def _check_is_admin(db: AsyncSession, user_id: int) -> bool:
    """Check if user is system admin."""
    q = select(User.is_system_admin, User.role).where(User.id == user_id)
    result = await db.execute(q)
    row = result.one_or_none()
    if not row:
        return False
    return row[0] or row[1] in ('system_admin', 'team_admin')


# ==================== Endpoints ====================

@router.get("/")
async def list_raw_materials(
    low_stock_only: bool = Query(False, description="Only show low stock items"),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    """List all raw materials."""
    query = select(RawMaterial).order_by(RawMaterial.name)
    
    if low_stock_only:
        query = query.where(RawMaterial.current_stock <= RawMaterial.min_stock_level)
    
    query = query.limit(limit).offset(offset)
    result = await db.execute(query)
    items = result.scalars().all()
    
    return {
        "items": [
            {
                "id": item.id,
                "name": item.name,
                "description": item.description,
                "unit": item.unit,
                "current_stock": item.current_stock,
                "min_stock_level": item.min_stock_level,
                "cost_per_unit": item.cost_per_unit,
                "supplier": item.supplier,
                "is_low_stock": item.is_low_stock,
                "created_at": item.created_at.isoformat() if item.created_at else None,
                "updated_at": item.updated_at.isoformat() if item.updated_at else None,
            }
            for item in items
        ],
        "count": len(items),
    }


@router.get("/{material_id}")
async def get_raw_material(
    material_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Get a specific raw material by ID with usage statistics."""
    query = select(RawMaterial).where(RawMaterial.id == material_id)
    result = await db.execute(query)
    item = result.scalar_one_or_none()
    
    if not item:
        raise HTTPException(status_code=404, detail="Raw material not found")
    
    # Get usage statistics from transactions
    tx_query = select(
        func.sum(func.abs(RawMaterialTransaction.change)).filter(RawMaterialTransaction.change < 0).label('total_used'),
        func.sum(RawMaterialTransaction.change).filter(RawMaterialTransaction.change > 0).label('total_added'),
        func.count(RawMaterialTransaction.id).label('transaction_count')
    ).where(RawMaterialTransaction.raw_material_id == material_id)
    tx_result = await db.execute(tx_query)
    tx_stats = tx_result.one()
    
    return {
        "id": item.id,
        "name": item.name,
        "description": item.description,
        "unit": item.unit,
        "current_stock": item.current_stock,
        "min_stock_level": item.min_stock_level,
        "cost_per_unit": item.cost_per_unit,
        "supplier": item.supplier,
        "is_low_stock": item.is_low_stock,
        "total_used": int(tx_stats.total_used or 0),
        "total_added": int(tx_stats.total_added or 0),
        "transaction_count": tx_stats.transaction_count or 0,
        "created_at": item.created_at.isoformat() if item.created_at else None,
        "updated_at": item.updated_at.isoformat() if item.updated_at else None,
    }


@router.post("/")
async def create_raw_material(
    payload: RawMaterialCreate,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a new raw material. Admin only."""
    user_id = current_user.get('user_id')
    # Enforce operational permission for raw_materials create
    q = select(User).where(User.id == user_id)
    result = await db.execute(q)
    db_user = result.scalar_one_or_none()
    if not db_user:
        raise HTTPException(status_code=404, detail="User not found")
    from app.permissions.guards import require_permission
    from app.audit.logger import log_audit
    try:
        require_permission(db_user, "raw_materials", "create")
    except HTTPException:
        try:
            await log_audit(db, db_user, action="create", resource="raw_materials", success=False, reason="permission_denied")
        except Exception:
            pass
        raise

    if not await _check_is_admin(db, user_id):
        try:
            await log_audit(db, db_user, action="create", resource="raw_materials", success=False, reason="admin_required")
        except Exception:
            pass
        raise HTTPException(status_code=403, detail="Admin access required")
    
    # Create raw material
    item = RawMaterial(
        name=payload.name,
        description=payload.description,
        unit=payload.unit,
        current_stock=payload.current_stock,
        min_stock_level=payload.min_stock_level,
        cost_per_unit=payload.cost_per_unit,
        supplier=payload.supplier,
        created_by_id=user_id,
    )
    db.add(item)
    await db.commit()
    await db.refresh(item)
    
    # Record initial stock transaction if stock > 0
    if payload.current_stock > 0:
        tx = RawMaterialTransaction(
            raw_material_id=item.id,
            change=payload.current_stock,
            reason="add",
            notes="Initial stock",
            performed_by_id=user_id,
        )
        db.add(tx)
        await db.commit()
    
    # Audit success
    try:
        await log_audit(db, db_user, action="create", resource="raw_materials", resource_id=item.id, success=True)
    except Exception:
        pass
    
    return {
        "id": item.id,
        "name": item.name,
        "description": item.description,
        "unit": item.unit,
        "current_stock": item.current_stock,
        "min_stock_level": item.min_stock_level,
        "cost_per_unit": item.cost_per_unit,
        "supplier": item.supplier,
        "is_low_stock": item.is_low_stock,
    }


@router.put("/{material_id}")
async def update_raw_material(
    material_id: int,
    payload: RawMaterialUpdate,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update a raw material. Admin only."""
    user_id = current_user.get('user_id')
    # Enforce operational permission for raw_materials update
    q = select(User).where(User.id == user_id)
    result = await db.execute(q)
    db_user = result.scalar_one_or_none()
    if not db_user:
        raise HTTPException(status_code=404, detail="User not found")
    from app.permissions.guards import require_permission
    from app.audit.logger import log_audit
    try:
        require_permission(db_user, "raw_materials", "update")
    except HTTPException:
        try:
            await log_audit(db, db_user, action="update", resource="raw_materials", success=False, reason="permission_denied")
        except Exception:
            pass
        raise

    if not await _check_is_admin(db, user_id):
        try:
            await log_audit(db, db_user, action="update", resource="raw_materials", success=False, reason="admin_required")
        except Exception:
            pass
        raise HTTPException(status_code=403, detail="Admin access required")
    
    query = select(RawMaterial).where(RawMaterial.id == material_id)
    result = await db.execute(query)
    item = result.scalar_one_or_none()
    
    if not item:
        raise HTTPException(status_code=404, detail="Raw material not found")
    
    # Update fields
    if payload.name is not None:
        item.name = payload.name
    if payload.description is not None:
        item.description = payload.description
    if payload.unit is not None:
        item.unit = payload.unit
    if payload.min_stock_level is not None:
        item.min_stock_level = payload.min_stock_level
    if payload.cost_per_unit is not None:
        item.cost_per_unit = payload.cost_per_unit
    if payload.supplier is not None:
        item.supplier = payload.supplier
    
    await db.commit()
    await db.refresh(item)
    
    return {
        "id": item.id,
        "name": item.name,
        "description": item.description,
        "unit": item.unit,
        "current_stock": item.current_stock,
        "min_stock_level": item.min_stock_level,
        "cost_per_unit": item.cost_per_unit,
        "supplier": item.supplier,
        "is_low_stock": item.is_low_stock,
    }


@router.post("/{material_id}/adjust")
async def adjust_stock(
    material_id: int,
    payload: StockAdjustment,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Adjust raw material stock (add, consume, adjust). Admin only."""
    user_id = current_user.get('user_id')
    # Enforce operational permission for raw_materials update
    q = select(User).where(User.id == user_id)
    result = await db.execute(q)
    db_user = result.scalar_one_or_none()
    if not db_user:
        raise HTTPException(status_code=404, detail="User not found")
    from app.permissions.guards import require_permission
    from app.audit.logger import log_audit
    try:
        require_permission(db_user, "raw_materials", "update")
    except HTTPException:
        try:
            await log_audit(db, db_user, action="update", resource="raw_materials", success=False, reason="permission_denied")
        except Exception:
            pass
        raise

    if not await _check_is_admin(db, user_id):
        try:
            await log_audit(db, db_user, action="update", resource="raw_materials", success=False, reason="admin_required")
        except Exception:
            pass
        raise HTTPException(status_code=403, detail="Admin access required")
    
    query = select(RawMaterial).where(RawMaterial.id == material_id)
    result = await db.execute(query)
    item = result.scalar_one_or_none()
    
    if not item:
        raise HTTPException(status_code=404, detail="Raw material not found")
    
    # Validate reason
    valid_reasons = ["add", "consume", "adjust", "return"]
    if payload.reason not in valid_reasons:
        raise HTTPException(status_code=400, detail=f"Invalid reason. Must be one of: {valid_reasons}")
    
    # Prevent negative stock
    new_stock = item.current_stock + payload.change
    if new_stock < 0:
        raise HTTPException(status_code=400, detail="Insufficient stock for this operation")
    
    # Update stock
    item.current_stock = new_stock
    
    # Record transaction
    tx = RawMaterialTransaction(
        raw_material_id=item.id,
        change=payload.change,
        reason=payload.reason,
        notes=payload.notes,
        performed_by_id=user_id,
    )
    db.add(tx)
    await db.commit()
    await db.refresh(item)
    # Audit success
    try:
        await log_audit(db, db_user, action="update", resource="raw_materials", resource_id=item.id, success=True)
    except Exception:
        pass
    
    return {
        "id": item.id,
        "name": item.name,
        "current_stock": item.current_stock,
        "change_applied": payload.change,
        "is_low_stock": item.is_low_stock,
    }


@router.get("/{material_id}/transactions")
async def get_material_transactions(
    material_id: int,
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
):
    """Get transaction history for a raw material."""
    # Verify material exists
    query = select(RawMaterial).where(RawMaterial.id == material_id)
    result = await db.execute(query)
    item = result.scalar_one_or_none()
    
    if not item:
        raise HTTPException(status_code=404, detail="Raw material not found")
    
    # Get transactions
    tx_query = (
        select(RawMaterialTransaction)
        .where(RawMaterialTransaction.raw_material_id == material_id)
        .order_by(RawMaterialTransaction.created_at.desc())
        .limit(limit)
    )
    tx_result = await db.execute(tx_query)
    transactions = tx_result.scalars().all()
    
    return {
        "material_id": material_id,
        "material_name": item.name,
        "transactions": [
            {
                "id": tx.id,
                "change": tx.change,
                "reason": tx.reason,
                "notes": tx.notes,
                "performed_by_id": tx.performed_by_id,
                "created_at": tx.created_at.isoformat() if tx.created_at else None,
            }
            for tx in transactions
        ],
        "count": len(transactions),
    }


@router.delete("/{material_id}")
async def delete_raw_material(
    material_id: int,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete a raw material. Admin only."""
    user_id = current_user.get('user_id')
    
    if not await _check_is_admin(db, user_id):
        raise HTTPException(status_code=403, detail="Admin access required")
    
    query = select(RawMaterial).where(RawMaterial.id == material_id)
    result = await db.execute(query)
    item = result.scalar_one_or_none()
    
    if not item:
        raise HTTPException(status_code=404, detail="Raw material not found")
    
    await db.delete(item)
    await db.commit()
    
    return {"message": "Raw material deleted", "id": material_id}
