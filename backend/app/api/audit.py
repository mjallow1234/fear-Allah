from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional, List
from datetime import datetime

from app.core.security import get_current_user
from app.db.database import get_db
from app.db.models import AuditLog, User
from app.core.logging import api_logger

router = APIRouter()


@router.get("/logs")
async def get_audit_logs(
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=200),
    user_id: Optional[int] = Query(None),
    action: Optional[str] = Query(None),
    resource: Optional[str] = Query(None),
    from_date: Optional[str] = Query(None, description="ISO format start date/time"),
    to_date: Optional[str] = Query(None, description="ISO format end date/time"),
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Read-only audit logs (admin-only).

    Pagination + optional filters: user_id, action, resource (target_type), from_date, to_date.
    """
    # Fetch DB user and attach operational role if present
    q = select(User).where(User.id == current_user['user_id'])
    result = await db.execute(q)
    db_user = result.scalar_one_or_none()
    if not db_user:
        raise HTTPException(status_code=404, detail="User not found")

    # Operational admin check: normalized system admins are allowed
    effective_role = getattr(db_user, 'operational_role_name', None)
    if not (getattr(db_user, 'is_system_admin', False) or (effective_role and str(effective_role).lower() == 'admin')):
        api_logger.warning("Audit access denied - non-admin", user_id=current_user['user_id'])
        raise HTTPException(status_code=403, detail="Admin access required")

    # Build query
    base_q = select(AuditLog)
    # Optional join to user to enable role lookup (left outer)
    base_q = base_q.select_from(AuditLog)

    where_clauses = []
    if user_id is not None:
        where_clauses.append(AuditLog.user_id == user_id)
    if action is not None:
        where_clauses.append(AuditLog.action == action)
    if resource is not None:
        # Audit model might expose resource as 'resource' or 'target_type'
        if hasattr(AuditLog, 'resource'):
            where_clauses.append(AuditLog.resource == resource)
        else:
            where_clauses.append(AuditLog.target_type == resource)
    if from_date is not None:
        try:
            fd = datetime.fromisoformat(from_date)
            where_clauses.append(AuditLog.created_at >= fd)
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid from_date format")
    if to_date is not None:
        try:
            td = datetime.fromisoformat(to_date)
            where_clauses.append(AuditLog.created_at <= td)
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid to_date format")

    if where_clauses:
        base_q = base_q.where(*where_clauses)

    # Total count
    count_q = select(func.count()).select_from(AuditLog)
    if where_clauses:
        count_q = count_q.where(*where_clauses)
    total_result = await db.execute(count_q)
    total = total_result.scalar() or 0

    # Ordering and pagination
    offset = (page - 1) * page_size
    base_q = base_q.order_by(desc(AuditLog.created_at)).limit(page_size).offset(offset)

    rows = await db.execute(base_q)
    items = rows.scalars().all()

    # Map to response shape
    def _row_to_json(r: AuditLog):
        return {
            "id": getattr(r, 'id', None),
            "timestamp": r.created_at.isoformat() if getattr(r, 'created_at', None) else None,
            "user_id": getattr(r, 'user_id', None),
            "username": getattr(r, 'username', None),
            "role": getattr(r, 'role', None) or None,
            "action": getattr(r, 'action', None),
            "resource": getattr(r, 'resource', None) or getattr(r, 'target_type', None),
            "success": getattr(r, 'success', None),
            "ip_address": getattr(r, 'ip_address', None),
        }

    return {
        "items": [_row_to_json(i) for i in items],
        "page": page,
        "page_size": page_size,
        "total": total,
    }