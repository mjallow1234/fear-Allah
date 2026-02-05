"""Admin API endpoints for user/channel management and moderation"""
from datetime import datetime
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel
from sqlalchemy import select, func, or_, and_, desc, delete, insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.database import get_db
from app.db.models import User, Channel, Message, Team, TeamMember, AuditLog, UserRole, ChannelType, UserOperationalRole
from app.core.security import (
    get_current_user, 
    require_admin, 
    require_permission,
    Permission,
    get_password_hash
)
from app.services.audit import (
    log_audit as audit_log_service,
    log_audit_from_user,
    get_audit_logs as get_audit_logs_service,
    AuditActions,
    AuditTargetTypes,
)
import json

router = APIRouter()


# === Pydantic Models ===

class UserUpdateAdmin(BaseModel):
    display_name: Optional[str] = None
    role: Optional[str] = None
    is_active: Optional[bool] = None
    operational_roles: Optional[List[str]] = None


class UserBanRequest(BaseModel):
    reason: Optional[str] = None


class UserMuteRequest(BaseModel):
    duration_minutes: int  # 0 = permanent until unmuted
    reason: Optional[str] = None


class ChannelUpdateAdmin(BaseModel):
    display_name: Optional[str] = None
    description: Optional[str] = None
    type: Optional[str] = None
    retention_days: Optional[int] = None


class ChannelArchiveRequest(BaseModel):
    reason: Optional[str] = None


class CreateUserRequest(BaseModel):
    username: str
    email: str
    password: str
    display_name: Optional[str] = None
    role: Optional[str] = "member"


class AdminStatsResponse(BaseModel):
    total_users: int
    active_users: int
    banned_users: int
    muted_users: int
    total_channels: int
    archived_channels: int
    total_messages: int
    total_teams: int


class AuditLogEntry(BaseModel):
    id: int
    user_id: Optional[int]
    username: Optional[str]
    action: str
    target_type: Optional[str]
    target_id: Optional[int]
    description: Optional[str]
    meta: Optional[dict]
    ip_address: Optional[str]
    request_id: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


class AuditLogResponse(BaseModel):
    logs: List[AuditLogEntry]
    total: int
    skip: int
    limit: int


# === Admin Dashboard ===

@router.get("/stats", response_model=AdminStatsResponse)
async def get_admin_stats(
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Get admin dashboard statistics"""
    user = await require_admin(db, current_user)
    
    # User stats
    total_users = await db.scalar(select(func.count(User.id)))
    active_users = await db.scalar(select(func.count(User.id)).where(User.is_active == True))
    banned_users = await db.scalar(select(func.count(User.id)).where(User.is_banned == True))
    muted_users = await db.scalar(select(func.count(User.id)).where(User.is_muted == True))
    
    # Channel stats
    total_channels = await db.scalar(select(func.count(Channel.id)))
    archived_channels = await db.scalar(select(func.count(Channel.id)).where(Channel.is_archived == True))
    
    # Message stats
    total_messages = await db.scalar(select(func.count(Message.id)).where(Message.is_deleted == False))
    
    # Team stats
    total_teams = await db.scalar(select(func.count(Team.id)))
    
    await log_audit(db, user.id, "admin.view_stats", "system", None, None)
    
    return AdminStatsResponse(
        total_users=total_users or 0,
        active_users=active_users or 0,
        banned_users=banned_users or 0,
        muted_users=muted_users or 0,
        total_channels=total_channels or 0,
        archived_channels=archived_channels or 0,
        total_messages=total_messages or 0,
        total_teams=total_teams or 0
    )


# === Audit Logs (Phase 8.2) ===

@router.get("/audit", response_model=AuditLogResponse)
async def list_audit_logs(
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(100, ge=1, le=500, description="Max records to return"),
    user_id: Optional[int] = Query(None, description="Filter by actor user ID"),
    action: Optional[str] = Query(None, description="Filter by action (partial match)"),
    target_type: Optional[str] = Query(None, description="Filter by target type"),
    target_id: Optional[int] = Query(None, description="Filter by target ID"),
    start_date: Optional[datetime] = Query(None, description="Start date (ISO format)"),
    end_date: Optional[datetime] = Query(None, description="End date (ISO format)"),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    Get audit logs with optional filters.
    Admin-only endpoint for reviewing system activity.
    """
    user = await require_admin(db, current_user)
    
    logs, total = await get_audit_logs_service(
        db=db,
        user_id=user_id,
        action=action,
        target_type=target_type,
        target_id=target_id,
        start_date=start_date,
        end_date=end_date,
        limit=limit,
        offset=skip,
    )
    
    # Convert to response format
    try:
        log_entries = []
        for log in logs:
            meta_dict = None
            if log.meta:
                try:
                    meta_dict = json.loads(log.meta)
                except Exception:
                    try:
                        meta_dict = {"raw": str(log.meta)}
                    except Exception:
                        meta_dict = None

            created_at = getattr(log, 'created_at', None) or datetime.utcnow()

            log_entries.append(AuditLogEntry(
                id=getattr(log, 'id', None) or 0,
                user_id=getattr(log, 'user_id', None),
                username=getattr(log, 'username', None),
                action=getattr(log, 'action', '') or '',
                target_type=getattr(log, 'target_type', None),
                target_id=getattr(log, 'target_id', None),
                description=getattr(log, 'description', None),
                meta=meta_dict,
                ip_address=getattr(log, 'ip_address', None),
                request_id=getattr(log, 'request_id', None),
                created_at=created_at,
            ))
        
        return AuditLogResponse(
            logs=log_entries,
            total=total or 0,
            skip=skip,
            limit=limit,
        )
    except Exception as e:
        api_logger.error("Failed to list audit logs", error=e)
        return AuditLogResponse(logs=[], total=0, skip=skip, limit=limit)


@router.get("/audit/actions")
async def get_audit_action_types(
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Get list of unique action types for filter dropdown."""
    await require_admin(db, current_user)
    
    result = await db.execute(
        select(AuditLog.action)
        .distinct()
        .order_by(AuditLog.action)
    )
    actions = [row[0] for row in result.fetchall() if row[0]]
    
    return {"actions": actions}


@router.get("/audit/target-types")
async def get_audit_target_types(
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Get list of unique target types for filter dropdown."""
    await require_admin(db, current_user)
    
    result = await db.execute(
        select(AuditLog.target_type)
        .distinct()
        .order_by(AuditLog.target_type)
    )
    types = [row[0] for row in result.fetchall() if row[0]]
    
    return {"target_types": types}


# === User Management ===

@router.get("/users")
async def list_users(
    skip: int = 0,
    limit: int = 50,
    search: Optional[str] = None,
    role: Optional[str] = None,
    status: Optional[str] = None,  # active, banned, muted
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """List all users with filters"""
    await require_permission(Permission.VIEW_USERS, db, current_user)
    
    query = select(User)
    
    # Apply filters
    if search:
        query = query.where(
            or_(
                User.username.ilike(f"%{search}%"),
                User.email.ilike(f"%{search}%"),
                User.display_name.ilike(f"%{search}%")
            )
        )
    
    if role:
        try:
            role_enum = UserRole(role)
            query = query.where(User.role == role_enum)
        except ValueError:
            pass
    
    if status == "banned":
        query = query.where(User.is_banned == True)
    elif status == "muted":
        query = query.where(User.is_muted == True)
    elif status == "active":
        query = query.where(and_(User.is_active == True, User.is_banned == False))
    
    # Get total count
    count_query = select(func.count()).select_from(query.subquery())
    total = await db.scalar(count_query)
    
    # Apply pagination and ordering
    query = query.order_by(User.created_at.desc()).offset(skip).limit(limit)
    
    result = await db.execute(query)
    users = result.scalars().all()
    
    return {
        "users": [
                {
                "id": u.id,
                "username": u.username,
                "email": u.email,
                "display_name": u.display_name,
                "avatar_url": u.avatar_url,
                "role": (u.role.value if hasattr(u.role, 'value') else (u.role or "member")),
                "status": (u.status.value if hasattr(u.status, 'value') else (u.status or "offline")),
                "is_active": u.is_active,
                "is_system_admin": u.is_system_admin,
                "is_banned": u.is_banned,
                "ban_reason": u.ban_reason,
                "banned_at": u.banned_at.isoformat() if u.banned_at else None,
                "is_muted": u.is_muted,
                "muted_until": u.muted_until.isoformat() if u.muted_until else None,
                "muted_reason": u.muted_reason,
                "created_at": u.created_at.isoformat() if u.created_at else None
            }
            for u in users
        ],
        "total": total,
        "skip": skip,
        "limit": limit
    }


@router.get("/users/{user_id}")
async def get_user_details(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Get detailed user information"""
    await require_permission(Permission.VIEW_USERS, db, current_user)
    
    result = await db.execute(
        select(User)
        .options(selectinload(User.team_memberships).selectinload(TeamMember.team))
        .where(User.id == user_id)
    )
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Get message count
    message_count = await db.scalar(
        select(func.count(Message.id))
        .where(and_(Message.author_id == user_id, Message.is_deleted == False))
    )
    
    return {
        "id": user.id,
        "username": user.username,
        "email": user.email,
        "display_name": user.display_name,
        "avatar_url": user.avatar_url,
        "role": (user.role.value if hasattr(user.role, 'value') else (user.role or "member")),
        "status": (user.status.value if hasattr(user.status, 'value') else (user.status or "offline")),
        "is_active": user.is_active,
        "is_system_admin": user.is_system_admin,
        "is_banned": user.is_banned,
        "ban_reason": user.ban_reason,
        "banned_at": user.banned_at.isoformat() if user.banned_at else None,
        "is_muted": user.is_muted,
        "muted_until": user.muted_until.isoformat() if user.muted_until else None,
        "muted_reason": user.muted_reason,
        "created_at": user.created_at.isoformat() if user.created_at else None,
        "updated_at": user.updated_at.isoformat() if user.updated_at else None,
        "message_count": message_count or 0,
        "teams": [
            {
                "id": tm.team.id,
                "name": tm.team.name,
                "display_name": tm.team.display_name,
                    "role": tm.role
            }
            for tm in user.team_memberships
        ]
    }


@router.post("/users")
async def create_user(
    request: CreateUserRequest,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Create a new user (admin only)"""
    admin = await require_permission(Permission.MANAGE_USERS, db, current_user)
    
    # Check if username or email already exists
    existing = await db.execute(
        select(User).where(
            or_(User.username == request.username, User.email == request.email)
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Username or email already exists")
    
    # Create user
    try:
        role_enum = UserRole(request.role) if request.role else UserRole.member
    except ValueError:
        role_enum = UserRole.member

    role_value = role_enum.value
    is_sys_admin = (role_enum == UserRole.system_admin)

    user = User(
        username=request.username,
        email=request.email,
        hashed_password=get_password_hash(request.password),
        display_name=request.display_name or request.username,
        role=role_value,
        is_system_admin=is_sys_admin
    )
    
    db.add(user)
    await db.commit()
    await db.refresh(user)
    
    await log_audit(
        db, admin.id, "admin.create_user", "user", user.id,
        {"username": user.username, "email": user.email, "role": role_value}
    )
    
    return {"id": user.id, "username": user.username, "message": "User created successfully"}


@router.put("/users/{user_id}")
async def update_user(
    user_id: int,
    update: UserUpdateAdmin,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Update user details (admin only)"""
    admin = await require_permission(Permission.MANAGE_USERS, db, current_user)
    
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    changes = {}
    
    if update.display_name is not None:
        changes["display_name"] = {"old": user.display_name, "new": update.display_name}
        user.display_name = update.display_name
    
    # NOTE: users.role is the legacy enum column and is NOT used for task permissions.
    # Operational roles are stored in user_operational_roles table.
    if update.role is not None:
        try:
            new_role_enum = UserRole(update.role)
            changes["role"] = {"old": (user.role.value if hasattr(user.role, 'value') else user.role), "new": new_role_enum.value}
            # Only update is_system_admin flag (for admin access control)
            user.is_system_admin = (new_role_enum == UserRole.system_admin)
            # Keep the legacy enum in sync for backward compatibility
            user.role = new_role_enum.value
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid role")
    
    if update.is_active is not None:
        changes["is_active"] = {"old": user.is_active, "new": update.is_active}
        user.is_active = update.is_active
    
    # Handle operational roles - this is the SOURCE OF TRUTH for task permissions
    if update.operational_roles is not None:
        # Get current operational roles before change
        current_roles_result = await db.execute(
            select(UserOperationalRole.role).where(UserOperationalRole.user_id == user.id)
        )
        old_roles = [r[0] for r in current_roles_result]
        
        changes["operational_roles"] = {"old": old_roles, "new": update.operational_roles}
        
        # Remove all existing operational roles
        await db.execute(
            delete(UserOperationalRole).where(UserOperationalRole.user_id == user.id)
        )
        
        # Insert new operational roles
        for role in update.operational_roles:
            await db.execute(
                insert(UserOperationalRole).values(
                    user_id=user.id,
                    role=role
                )
            )
    
    await db.commit()
    
    # Fetch final operational roles from DB (source of truth)
    final_roles_result = await db.execute(
        select(UserOperationalRole.role).where(UserOperationalRole.user_id == user.id)
    )
    final_operational_roles = [r[0] for r in final_roles_result]
    
    await log_audit(db, admin.id, "admin.update_user", "user", user_id, changes)
    
    return {
        "message": "User updated successfully",
        "changes": changes,
        "user": {
            "id": user.id,
            "username": user.username,
            "operational_roles": final_operational_roles,
        }
    }


@router.post("/users/{user_id}/ban")
async def ban_user(
    user_id: int,
    request: UserBanRequest,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Ban a user"""
    admin = await require_permission(Permission.BAN_USERS, db, current_user)
    
    if user_id == admin.id:
        raise HTTPException(status_code=400, detail="Cannot ban yourself")
    
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    if user.is_system_admin:
        raise HTTPException(status_code=400, detail="Cannot ban a system admin")
    
    user.is_banned = True
    user.ban_reason = request.reason
    user.banned_at = datetime.utcnow()
    user.banned_by_id = admin.id
    
    await db.commit()
    
    await log_audit(
        db, admin.id, "admin.ban_user", "user", user_id,
        {"reason": request.reason, "username": user.username}
    )
    
    return {"message": f"User {user.username} has been banned"}


@router.post("/users/{user_id}/unban")
async def unban_user(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Unban a user"""
    admin = await require_permission(Permission.BAN_USERS, db, current_user)
    
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    user.is_banned = False
    user.ban_reason = None
    user.banned_at = None
    user.banned_by_id = None
    
    await db.commit()
    
    await log_audit(
        db, admin.id, "admin.unban_user", "user", user_id,
        {"username": user.username}
    )
    
    return {"message": f"User {user.username} has been unbanned"}


@router.post("/users/{user_id}/mute")
async def mute_user(
    user_id: int,
    request: UserMuteRequest,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Mute a user (prevent from posting)"""
    admin = await require_permission(Permission.MUTE_USERS, db, current_user)
    
    if user_id == admin.id:
        raise HTTPException(status_code=400, detail="Cannot mute yourself")
    
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    if user.is_system_admin:
        raise HTTPException(status_code=400, detail="Cannot mute a system admin")
    
    user.is_muted = True
    user.muted_reason = request.reason
    
    if request.duration_minutes > 0:
        from datetime import timedelta
        user.muted_until = datetime.utcnow() + timedelta(minutes=request.duration_minutes)
    else:
        user.muted_until = None  # Permanent mute
    
    await db.commit()
    
    await log_audit(
        db, admin.id, "admin.mute_user", "user", user_id,
        {
            "reason": request.reason,
            "duration_minutes": request.duration_minutes,
            "username": user.username
        }
    )
    
    return {"message": f"User {user.username} has been muted"}


@router.post("/users/{user_id}/unmute")
async def unmute_user(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Unmute a user"""
    admin = await require_permission(Permission.MUTE_USERS, db, current_user)
    
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    user.is_muted = False
    user.muted_until = None
    user.muted_reason = None
    
    await db.commit()
    
    await log_audit(
        db, admin.id, "admin.unmute_user", "user", user_id,
        {"username": user.username}
    )
    
    return {"message": f"User {user.username} has been unmuted"}


@router.delete("/users/{user_id}")
async def delete_user(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Delete a user (soft delete - deactivates account)"""
    admin = await require_permission(Permission.MANAGE_USERS, db, current_user)
    
    if user_id == admin.id:
        raise HTTPException(status_code=400, detail="Cannot delete yourself")
    
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    if user.is_system_admin:
        raise HTTPException(status_code=400, detail="Cannot delete a system admin")
    
    user.is_active = False
    user.is_banned = True
    user.ban_reason = "Account deleted by admin"
    
    await db.commit()
    
    await log_audit(
        db, admin.id, "admin.delete_user", "user", user_id,
        {"username": user.username, "email": user.email}
    )
    
    return {"message": f"User {user.username} has been deleted"}


# === Channel Management ===

@router.get("/channels")
async def list_channels(
    skip: int = 0,
    limit: int = 50,
    search: Optional[str] = None,
    type: Optional[str] = None,
    archived: Optional[bool] = None,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """List all channels with filters"""
    await require_admin(db, current_user)
    
    query = select(Channel)
    
    if search:
        query = query.where(
            or_(
                Channel.name.ilike(f"%{search}%"),
                Channel.display_name.ilike(f"%{search}%")
            )
        )
    
    if type:
        try:
            type_enum = ChannelType(type)
            query = query.where(Channel.type == type_enum)
        except ValueError:
            pass
    
    if archived is not None:
        query = query.where(Channel.is_archived == archived)
    
    # Get total count
    count_query = select(func.count()).select_from(query.subquery())
    total = await db.scalar(count_query)
    
    # Apply pagination
    query = query.order_by(Channel.created_at.desc()).offset(skip).limit(limit)
    
    result = await db.execute(query)
    channels = result.scalars().all()
    
    # Get member counts
    channel_data = []
    for ch in channels:
        member_count = await db.scalar(
            select(func.count()).select_from(
                select(1).where(Message.channel_id == ch.id).subquery()
            )
        )
        
        channel_data.append({
            "id": ch.id,
            "name": ch.name,
            "display_name": ch.display_name,
            "description": ch.description,
            "type": ch.type.value if ch.type else "public",
            "team_id": ch.team_id,
            "is_archived": ch.is_archived,
            "archived_at": ch.archived_at.isoformat() if ch.archived_at else None,
            "retention_days": ch.retention_days,
            "created_at": ch.created_at.isoformat() if ch.created_at else None,
        })
    
    return {
        "channels": channel_data,
        "total": total,
        "skip": skip,
        "limit": limit
    }


@router.put("/channels/{channel_id}")
async def update_channel(
    channel_id: int,
    update: ChannelUpdateAdmin,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Update channel settings"""
    admin = await require_admin(db, current_user)
    
    result = await db.execute(select(Channel).where(Channel.id == channel_id))
    channel = result.scalar_one_or_none()
    
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")
    
    changes = {}
    
    if update.display_name is not None:
        changes["display_name"] = {"old": channel.display_name, "new": update.display_name}
        channel.display_name = update.display_name
    
    if update.description is not None:
        changes["description"] = {"old": channel.description, "new": update.description}
        channel.description = update.description
    
    if update.type is not None:
        try:
            new_type = ChannelType(update.type)
            changes["type"] = {"old": channel.type.value if channel.type else None, "new": new_type.value}
            channel.type = new_type
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid channel type")
    
    if update.retention_days is not None:
        changes["retention_days"] = {"old": channel.retention_days, "new": update.retention_days}
        channel.retention_days = update.retention_days
    
    await db.commit()
    
    await log_audit(
        db, admin.id, "admin.update_channel", "channel", channel_id,
        {"channel_name": channel.name, **changes}
    )
    
    return {"message": "Channel updated successfully", "changes": changes}


@router.post("/channels/{channel_id}/archive")
async def archive_channel(
    channel_id: int,
    request: ChannelArchiveRequest,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Archive a channel"""
    admin = await require_permission(Permission.ARCHIVE_CHANNELS, db, current_user)
    
    result = await db.execute(select(Channel).where(Channel.id == channel_id))
    channel = result.scalar_one_or_none()
    
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")
    
    channel.is_archived = True
    channel.archived_at = datetime.utcnow()
    channel.archived_by_id = admin.id
    
    await db.commit()
    
    await log_audit(
        db, admin.id, "admin.archive_channel", "channel", channel_id,
        {"channel_name": channel.name, "reason": request.reason}
    )
    
    return {"message": f"Channel {channel.name} has been archived"}


@router.post("/channels/{channel_id}/unarchive")
async def unarchive_channel(
    channel_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Unarchive a channel"""
    admin = await require_permission(Permission.ARCHIVE_CHANNELS, db, current_user)
    
    result = await db.execute(select(Channel).where(Channel.id == channel_id))
    channel = result.scalar_one_or_none()
    
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")
    
    channel.is_archived = False
    channel.archived_at = None
    channel.archived_by_id = None
    
    await db.commit()
    
    await log_audit(
        db, admin.id, "admin.unarchive_channel", "channel", channel_id,
        {"channel_name": channel.name}
    )
    
    return {"message": f"Channel {channel.name} has been unarchived"}


@router.delete("/channels/{channel_id}")
async def delete_channel(
    channel_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Delete a channel (and all its messages)"""
    admin = await require_permission(Permission.DELETE_CHANNELS, db, current_user)
    
    result = await db.execute(select(Channel).where(Channel.id == channel_id))
    channel = result.scalar_one_or_none()
    
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")
    
    channel_name = channel.name
    channel_id_log = channel.id
    
    # Soft delete - archive and mark messages as deleted
    channel.is_archived = True
    channel.archived_at = datetime.utcnow()
    
    # Mark all messages in channel as deleted
    await db.execute(
        Message.__table__.update()
        .where(Message.channel_id == channel_id)
        .values(is_deleted=True)
    )
    
    await db.commit()
    
    await log_audit(
        db, admin.id, "admin.delete_channel", "channel", channel_id_log,
        {"channel_name": channel_name}
    )
    
    return {"message": f"Channel {channel_name} has been deleted"}


# === Message Management ===

@router.delete("/messages/{message_id}")
async def delete_message_admin(
    message_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Delete any message as admin"""
    admin = await require_permission(Permission.DELETE_ANY_MESSAGE, db, current_user)
    
    result = await db.execute(select(Message).where(Message.id == message_id))
    message = result.scalar_one_or_none()
    
    if not message:
        raise HTTPException(status_code=404, detail="Message not found")
    
    message.is_deleted = True
    await db.commit()
    
    await log_audit(
        db, admin.id, "admin.delete_message", "message", message_id,
        {
            "channel_id": message.channel_id,
            "author_id": message.author_id,
            "content_preview": message.content[:100] if message.content else None
        }
    )
    
    return {"message": "Message deleted"}


# === Audit Logs ===

@router.get("/audit-logs")
async def get_audit_logs(
    skip: int = 0,
    limit: int = 100,
    action: Optional[str] = None,
    user_id: Optional[int] = None,
    target_type: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Get audit logs with filters"""
    await require_permission(Permission.VIEW_AUDIT_LOGS, db, current_user)
    
    query = select(AuditLog).options(selectinload(AuditLog.user))
    
    if action:
        query = query.where(AuditLog.action.ilike(f"%{action}%"))
    
    if user_id:
        query = query.where(AuditLog.user_id == user_id)
    
    if target_type:
        query = query.where(AuditLog.target_type == target_type)
    
    if start_date:
        try:
            start = datetime.fromisoformat(start_date)
            query = query.where(AuditLog.created_at >= start)
        except ValueError:
            pass
    
    if end_date:
        try:
            end = datetime.fromisoformat(end_date)
            query = query.where(AuditLog.created_at <= end)
        except ValueError:
            pass
    
    # Get total count
    count_query = select(func.count()).select_from(query.subquery())
    total = await db.scalar(count_query)
    
    # Apply pagination and ordering
    query = query.order_by(desc(AuditLog.created_at)).offset(skip).limit(limit)
    
    result = await db.execute(query)
    logs = result.scalars().all()
    
    return {
        "logs": [
            {
                "id": log.id,
                "user_id": log.user_id,
                "username": log.user.username if log.user else None,
                "action": log.action,
                "target_type": log.target_type,
                "target_id": log.target_id,
                "details": log.meta,
                "ip_address": log.ip_address,
                "created_at": log.created_at.isoformat() if log.created_at else None
            }
            for log in logs
        ],
        "total": total,
        "skip": skip,
        "limit": limit
    }


# === Helper Functions ===

async def log_audit(
    db: AsyncSession,
    user_id: int,
    action: str,
    target_type: str,
    target_id: Optional[int],
    details: Optional[dict],
    ip_address: Optional[str] = None
):
    """
    Helper to create audit log entries.
    Wrapper around the centralized audit service.
    """
    # Get username for denormalization
    username = None
    if user_id:
        user = await db.get(User, user_id)
        if user:
            username = user.username
    
    await audit_log_service(
        db=db,
        action=action,
        target_type=target_type,
        target_id=target_id,
        meta=details,
        user_id=user_id,
        username=username,
        ip_address=ip_address,
    )
