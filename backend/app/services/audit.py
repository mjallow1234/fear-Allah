"""
Phase 8.2 - Admin Audit Service

Centralized service for logging audit events across the system.
Provides async logging to avoid blocking main request flow.
"""
import json
from datetime import datetime
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc, and_
from app.db.models import AuditLog, User
from app.core.logging import api_logger, request_id_var


async def log_audit(
    db: AsyncSession,
    action: str,
    target_type: str,
    target_id: Optional[int] = None,
    description: Optional[str] = None,
    meta: Optional[dict] = None,
    user_id: Optional[int] = None,
    username: Optional[str] = None,
    ip_address: Optional[str] = None,
) -> AuditLog:
    """
    Log an audit event to the database.
    
    Args:
        db: Database session
        action: Action performed (e.g., 'sale.create', 'inventory.restock')
        target_type: Type of entity affected (e.g., 'sale', 'inventory', 'order')
        target_id: ID of the affected entity (optional)
        description: Human-readable description of the action
        meta: Additional JSON-serializable data
        user_id: ID of the user who performed the action (null for system)
        username: Username of the actor (denormalized for display)
        ip_address: IP address of the request
    
    Returns:
        The created AuditLog entry
    """
    # Get request_id from context if available
    req_id = request_id_var.get()
    
    # Serialize metadata to JSON string
    meta_str = json.dumps(meta) if meta else None
    
    audit_entry = AuditLog(
        user_id=user_id,
        username=username,
        action=action,
        target_type=target_type,
        target_id=target_id,
        description=description,
        meta=meta_str,
        ip_address=ip_address,
        request_id=req_id,
    )
    
    db.add(audit_entry)
    await db.commit()
    await db.refresh(audit_entry)
    
    api_logger.info(
        "audit_logged",
        action=action,
        target_type=target_type,
        target_id=target_id,
        user_id=user_id,
    )
    
    return audit_entry


async def log_audit_from_user(
    db: AsyncSession,
    user: User,
    action: str,
    target_type: str,
    target_id: Optional[int] = None,
    description: Optional[str] = None,
    meta: Optional[dict] = None,
    ip_address: Optional[str] = None,
) -> AuditLog:
    """
    Convenience wrapper that extracts actor info from a User object.
    """
    return await log_audit(
        db=db,
        action=action,
        target_type=target_type,
        target_id=target_id,
        description=description,
        meta=meta,
        user_id=user.id,
        username=user.username,
        ip_address=ip_address,
    )


async def get_audit_logs(
    db: AsyncSession,
    user_id: Optional[int] = None,
    action: Optional[str] = None,
    target_type: Optional[str] = None,
    target_id: Optional[int] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    limit: int = 100,
    offset: int = 0,
) -> tuple[list[AuditLog], int]:
    """
    Query audit logs with optional filters.
    
    Returns:
        Tuple of (list of audit logs, total count)
    """
    # Build filter conditions
    conditions = []
    
    if user_id is not None:
        conditions.append(AuditLog.user_id == user_id)
    
    if action:
        # Support partial matching (e.g., 'sale' matches 'sale.create', 'sale.update')
        conditions.append(AuditLog.action.ilike(f"%{action}%"))
    
    if target_type:
        conditions.append(AuditLog.target_type == target_type)
    
    if target_id is not None:
        conditions.append(AuditLog.target_id == target_id)
    
    if start_date:
        conditions.append(AuditLog.created_at >= start_date)
    
    if end_date:
        conditions.append(AuditLog.created_at <= end_date)
    
    # Build base query
    base_query = select(AuditLog)
    if conditions:
        base_query = base_query.where(and_(*conditions))
    
    # Get total count
    from sqlalchemy import func
    count_query = select(func.count(AuditLog.id))
    if conditions:
        count_query = count_query.where(and_(*conditions))
    
    count_result = await db.execute(count_query)
    total = count_result.scalar() or 0
    
    # Get paginated results
    query = (
        base_query
        .order_by(desc(AuditLog.created_at))
        .limit(limit)
        .offset(offset)
    )
    
    result = await db.execute(query)
    logs = result.scalars().all()
    
    return list(logs), total


# Predefined action constants for consistency
class AuditActions:
    """Standard audit action names."""
    # Sales
    SALE_CREATE = "sale.create"
    SALE_UPDATE = "sale.update"
    SALE_DELETE = "sale.delete"
    
    # Inventory
    INVENTORY_CREATE = "inventory.create"
    INVENTORY_UPDATE = "inventory.update"
    INVENTORY_DELETE = "inventory.delete"
    INVENTORY_RESTOCK = "inventory.restock"
    INVENTORY_LOW_STOCK = "inventory.low_stock"
    
    # Orders
    ORDER_CREATE = "order.create"
    ORDER_UPDATE = "order.update"
    ORDER_STATUS_CHANGE = "order.status_change"
    ORDER_DELETE = "order.delete"
    
    # Tasks
    TASK_CREATE = "task.create"
    TASK_UPDATE = "task.update"
    TASK_ASSIGN = "task.assign"
    TASK_STATUS_CHANGE = "task.status_change"
    TASK_COMPLETE = "task.complete"
    TASK_DELETE = "task.delete"
    
    # Admin
    ADMIN_USER_BAN = "admin.user.ban"
    ADMIN_USER_UNBAN = "admin.user.unban"
    ADMIN_USER_MUTE = "admin.user.mute"
    ADMIN_USER_UNMUTE = "admin.user.unmute"
    ADMIN_USER_ROLE_CHANGE = "admin.user.role_change"
    ADMIN_CHANNEL_ARCHIVE = "admin.channel.archive"
    ADMIN_MESSAGE_DELETE = "admin.message.delete"
    ADMIN_VIEW_STATS = "admin.view_stats"
    ADMIN_VIEW_AUDIT = "admin.view_audit"
    
    # Roles & Permissions (Phase 8.5.2)
    ROLE_CREATE = "role.create"
    ROLE_UPDATE = "role.update"
    ROLE_DELETE = "role.delete"
    ROLE_PERMISSIONS_UPDATE = "role.permissions.update"
    USER_ROLE_CHANGE = "user.role.change"
    
    # Auth
    AUTH_LOGIN = "auth.login"
    AUTH_LOGOUT = "auth.logout"
    AUTH_PASSWORD_CHANGE = "auth.password_change"


class AuditTargetTypes:
    """Standard target type names."""
    SALE = "sale"
    INVENTORY = "inventory"
    ORDER = "order"
    TASK = "task"
    USER = "user"
    CHANNEL = "channel"
    MESSAGE = "message"
    AUTH = "auth"
    SYSTEM = "system"
    ROLE = "role"  # Phase 8.5.2
