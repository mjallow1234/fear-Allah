"""
Inventory API Endpoints (Phase 6.3)
Handles inventory management with role-based permissions.
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime, timedelta
from typing import Optional

from app.core.security import get_current_user
from app.core.logging import inventory_logger
from app.db.database import get_db
from app.db.models import User
from app.services.inventory import (
    list_inventory,
    get_inventory_item,
    get_inventory_by_id,
    create_inventory_item,
    restock_inventory,
    adjust_inventory,
    get_inventory_transactions,
    get_inventory_summary,
    update_low_stock_threshold,
)

router = APIRouter()


async def _check_can_manage_inventory(db: AsyncSession, user_id: int) -> bool:
    """Check if user can manage inventory (create, restock, adjust)."""
    q = select(User.is_system_admin, User.role).where(User.id == user_id)
    result = await db.execute(q)
    row = result.one_or_none()
    if not row:
        return False
    is_admin = row[0] or row[1] == 'system_admin'
    return is_admin or row[1] == 'team_admin'


@router.get("/")
async def list_inventory_items(
    low_stock_only: bool = Query(False, description="Only show low stock items"),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    """
    List all inventory items.
    
    Args:
        low_stock_only: If true, only return items below threshold
        limit: Maximum items to return
        offset: Pagination offset
    """
    try:
        items = await list_inventory(
            db,
            include_low_stock_only=low_stock_only,
            limit=limit,
            offset=offset,
        )

        serialized = []
        for item in items:
            try:
                product_id = int(getattr(item, 'product_id', 0) or 0)
            except Exception:
                product_id = 0
            product_name = getattr(item, 'product_name', None) or ""
            try:
                total_stock = int(getattr(item, 'total_stock', 0) or 0)
            except Exception:
                total_stock = 0
            try:
                total_sold = int(getattr(item, 'total_sold', 0) or 0)
            except Exception:
                total_sold = 0
            try:
                low_stock_threshold = int(getattr(item, 'low_stock_threshold', 0) or 0)
            except Exception:
                low_stock_threshold = 0

            updated_at = None
            try:
                if getattr(item, 'updated_at', None):
                    updated_at = item.updated_at.isoformat()
            except Exception:
                updated_at = None

            is_low_stock = total_stock <= low_stock_threshold

            serialized.append({
                "id": getattr(item, 'id', None),
                "product_id": product_id,
                "product_name": product_name,
                "total_stock": total_stock,
                "total_sold": total_sold,
                "low_stock_threshold": low_stock_threshold,
                "is_low_stock": is_low_stock,
                "updated_at": updated_at,
            })

        return {
            "items": serialized,
            "count": len(serialized),
        }
    except Exception as e:
        # Defensive: do not return 500 on missing or malformed rows
        inventory_logger.error("Failed to list inventory", error=e)
        return {"items": [], "count": 0}


@router.get("/summary")
async def inventory_summary(db: AsyncSession = Depends(get_db)):
    """Get overall inventory summary statistics."""
    summary = await get_inventory_summary(db)
    return summary


@router.get("/low-stock")
async def low_stock_items(
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
):
    """Get items that are below their low stock threshold."""
    items = await list_inventory(db, include_low_stock_only=True, limit=limit)
    
    return {
        "items": [
            {
                "id": item.id,
                "product_id": item.product_id,
                "product_name": item.product_name,
                "current_stock": item.total_stock,
                "threshold": item.low_stock_threshold,
                "shortage": item.low_stock_threshold - item.total_stock,
            }
            for item in items
        ],
        "count": len(items),
    }


@router.post("/")
async def create_inventory(
    payload: dict,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Create a new inventory item.
    
    Permissions: Admin only
    """
    user_id = current_user.get('user_id')
    
    try:
        # Enforce operational permissions for creating inventory
        from app.db.models import User
        q = select(User).where(User.id == user_id)
        result = await db.execute(q)
        db_user = result.scalar_one_or_none()
        if not db_user:
            raise HTTPException(status_code=404, detail="User not found")
        # Attach operational role info
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
        require_permission(db_user, "inventory", "create")

        if not await _check_can_manage_inventory(db, user_id):
            inventory_logger.warning("Inventory create denied - not admin", user_id=user_id)
            raise HTTPException(status_code=403, detail="Admin access required")
        
        try:
            raw_product_id = payload.get('product_id')
            # Handle large product_ids (e.g., Date.now() from frontend exceeds int32)
            if raw_product_id:
                raw_product_id = int(raw_product_id)
                # If product_id exceeds int32 max, generate a smaller one
                if raw_product_id > 2147483647:
                    import random
                    raw_product_id = random.randint(100000, 9999999)
                product_id = raw_product_id
            else:
                import random
                product_id = random.randint(100000, 9999999)
            product_name = payload.get('product_name')
            initial_stock = int(payload.get('initial_stock', 0) or 0)
            low_stock_threshold = int(payload.get('low_stock_threshold', 10) or 10)
        except (TypeError, ValueError) as e:
            inventory_logger.warning("Invalid inventory payload", error=e, user_id=user_id)
            raise HTTPException(status_code=400, detail="Invalid payload")
        
        inventory_logger.info(
            "Creating inventory item",
            user_id=user_id,
            product_id=product_id,
            initial_stock=initial_stock,
        )
        
        try:
            item = await create_inventory_item(
                db,
                product_id=product_id,
                product_name=product_name,
                initial_stock=initial_stock,
                low_stock_threshold=low_stock_threshold,
                created_by_id=user_id,
            )
            inventory_logger.info(
                "Inventory item created",
                item_id=item.id,
                product_id=product_id,
                user_id=user_id,
            )
        except ValueError as e:
            inventory_logger.warning("Inventory create failed", error=e, product_id=product_id)
            raise HTTPException(status_code=400, detail=str(e))
        except Exception as e:
            inventory_logger.error("Inventory create failed - unexpected", error=e, product_id=product_id)
            raise
        
        return {
            "id": item.id,
            "product_id": item.product_id,
            "product_name": item.product_name,
            "total_stock": item.total_stock,
            "low_stock_threshold": item.low_stock_threshold,
        }
    except HTTPException:
        raise
    except Exception as e:
        inventory_logger.error("Inventory endpoint exception", error=e)
        raise


@router.get("/product/{product_id}")
async def get_inventory_by_product(
    product_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Get inventory for a specific product."""
    item = await get_inventory_item(db, product_id)
    if not item:
        raise HTTPException(status_code=404, detail="Inventory item not found")
    
    return {
        "id": item.id,
        "product_id": item.product_id,
        "product_name": item.product_name,
        "total_stock": item.total_stock,
        "total_sold": item.total_sold,
        "low_stock_threshold": item.low_stock_threshold,
        "is_low_stock": item.total_stock <= item.low_stock_threshold,
        "updated_at": item.updated_at.isoformat() if item.updated_at else None,
    }


@router.post("/product/{product_id}/restock")
async def restock_product(
    product_id: int,
    payload: dict,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Add stock to an inventory item.
    
    Permissions: Admin only
    """
    user_id = current_user['user_id']
    # Enforce operational permission for inventory update (restock)
    from app.db.models import User
    q = select(User).where(User.id == user_id)
    result = await db.execute(q)
    db_user = result.scalar_one_or_none()
    if not db_user:
        raise HTTPException(status_code=404, detail="User not found")
    from app.permissions.guards import require_permission
    require_permission(db_user, "inventory", "update")

    if not await _check_can_manage_inventory(db, user_id):
        inventory_logger.warning("Restock denied - not admin", user_id=user_id, product_id=product_id)
        raise HTTPException(status_code=403, detail="Admin access required")
    
    try:
        quantity = int(payload.get('quantity'))
        related_order_id = payload.get('related_order_id')
        notes = payload.get('notes')
    except (TypeError, ValueError) as e:
        inventory_logger.warning("Invalid restock payload", error=e, user_id=user_id)
        raise HTTPException(status_code=400, detail="Invalid quantity")
    
    inventory_logger.info(
        "Restocking inventory",
        user_id=user_id,
        product_id=product_id,
        quantity=quantity,
    )
    
    try:
        item = await restock_inventory(
            db,
            product_id=product_id,
            quantity=quantity,
            performed_by_id=user_id,
            related_order_id=related_order_id,
            notes=notes,
        )
        inventory_logger.info(
            "Inventory restocked",
            product_id=product_id,
            quantity_added=quantity,
            new_stock=item.total_stock,
            user_id=user_id,
        )
    except ValueError as e:
        inventory_logger.warning("Restock failed", error=e, product_id=product_id)
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        inventory_logger.error("Restock failed - unexpected", error=e, product_id=product_id)
        raise
    
    return {
        "product_id": item.product_id,
        "quantity_added": quantity,
        "new_stock": item.total_stock,
        "is_low_stock": item.total_stock <= item.low_stock_threshold,
    }


@router.post("/product/{product_id}/adjust")
async def adjust_product_inventory(
    product_id: int,
    payload: dict,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Adjust inventory (up or down) for corrections, returns, damage, etc.
    
    Permissions: Admin only
    """
    user_id = current_user['user_id']
    # Enforce operational permission for inventory update (adjust)
    from app.db.models import User
    q = select(User).where(User.id == user_id)
    result = await db.execute(q)
    db_user = result.scalar_one_or_none()
    if not db_user:
        raise HTTPException(status_code=404, detail="User not found")
    from app.permissions.guards import require_permission
    require_permission(db_user, "inventory", "update")

    if not await _check_can_manage_inventory(db, user_id):
        inventory_logger.warning("Adjustment denied - not admin", user_id=user_id, product_id=product_id)
        raise HTTPException(status_code=403, detail="Admin access required")
    
    try:
        adjustment = int(payload.get('adjustment'))
        reason = payload.get('reason', 'adjustment')
        notes = payload.get('notes')
    except (TypeError, ValueError) as e:
        inventory_logger.warning("Invalid adjustment payload", error=e, user_id=user_id)
        raise HTTPException(status_code=400, detail="Invalid adjustment value")
    
    inventory_logger.info(
        "Adjusting inventory",
        user_id=user_id,
        product_id=product_id,
        adjustment=adjustment,
        reason=reason,
    )
    
    # Validate reason
    valid_reasons = ['adjustment', 'return', 'correction', 'damage', 'expired', 'other']
    if reason not in valid_reasons:
        raise HTTPException(status_code=400, detail=f"Invalid reason. Must be one of: {valid_reasons}")
    
    try:
        item = await adjust_inventory(
            db,
            product_id=product_id,
            adjustment=adjustment,
            performed_by_id=current_user['user_id'],
            reason=reason,
            notes=notes,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    
    return {
        "product_id": item.product_id,
        "adjustment": adjustment,
        "reason": reason,
        "new_stock": item.total_stock,
        "is_low_stock": item.total_stock <= item.low_stock_threshold,
    }


@router.put("/product/{product_id}/threshold")
async def update_product_threshold(
    product_id: int,
    payload: dict,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Update the low stock threshold for a product.
    
    Permissions: Admin only
    """
    if not await _check_can_manage_inventory(db, current_user['user_id']):
        raise HTTPException(status_code=403, detail="Admin access required")
    
    try:
        threshold = int(payload.get('threshold'))
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail="Invalid threshold value")
    
    try:
        item = await update_low_stock_threshold(db, product_id, threshold)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    
    return {
        "product_id": item.product_id,
        "low_stock_threshold": item.low_stock_threshold,
        "is_low_stock": item.total_stock <= item.low_stock_threshold,
    }


@router.get("/transactions")
async def list_transactions(
    product_id: Optional[int] = Query(None, description="Filter by product"),
    reason: Optional[str] = Query(None, description="Filter by reason (sale, restock, adjustment)"),
    start_date: Optional[str] = Query(None, description="Start date YYYY-MM-DD"),
    end_date: Optional[str] = Query(None, description="End date YYYY-MM-DD"),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Get inventory transaction history.
    
    Permissions: Admin only
    """
    if not await _check_can_manage_inventory(db, current_user['user_id']):
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
    
    transactions = await get_inventory_transactions(
        db,
        product_id=product_id,
        reason=reason,
        start_date=start_dt,
        end_date=end_dt,
        limit=limit,
        offset=offset,
    )
    
    return {
        "transactions": [
            {
                "id": t.id,
                "inventory_item_id": t.inventory_item_id,
                "change": t.change,
                "reason": t.reason,
                "related_sale_id": t.related_sale_id,
                "related_order_id": t.related_order_id,
                "performed_by_id": t.performed_by_id,
                "notes": t.notes,
                "created_at": t.created_at.isoformat() if t.created_at else None,
            }
            for t in transactions
        ],
        "count": len(transactions),
    }

