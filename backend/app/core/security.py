from datetime import datetime, timedelta
from typing import Optional, List
from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.enums import UserRole

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
security = HTTPBearer()


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(hours=settings.JWT_EXPIRATION_HOURS)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)
    return encoded_jwt


def decode_token(token: str) -> dict:
    try:
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
        return payload
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )


async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    token = credentials.credentials
    payload = decode_token(token)
    user_id = payload.get("sub")
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
        )
    return {"user_id": int(user_id), "payload": payload}


# Permission checking utilities
class Permission:
    """Permission constants"""
    # User management
    VIEW_USERS = "view_users"
    MANAGE_USERS = "manage_users"
    BAN_USERS = "ban_users"
    MUTE_USERS = "mute_users"
    
    # Channel management
    CREATE_CHANNELS = "create_channels"
    DELETE_CHANNELS = "delete_channels"
    ARCHIVE_CHANNELS = "archive_channels"
    MANAGE_CHANNEL_MEMBERS = "manage_channel_members"
    
    # Message management
    DELETE_ANY_MESSAGE = "delete_any_message"
    EDIT_ANY_MESSAGE = "edit_any_message"
    
    # Team management
    MANAGE_TEAMS = "manage_teams"
    
    # Admin
    VIEW_AUDIT_LOGS = "view_audit_logs"
    SYSTEM_SETTINGS = "system_settings"


# Role-based permissions mapping
ROLE_PERMISSIONS = {
    "system_admin": [
        Permission.VIEW_USERS,
        Permission.MANAGE_USERS,
        Permission.BAN_USERS,
        Permission.MUTE_USERS,
        Permission.CREATE_CHANNELS,
        Permission.DELETE_CHANNELS,
        Permission.ARCHIVE_CHANNELS,
        Permission.MANAGE_CHANNEL_MEMBERS,
        Permission.DELETE_ANY_MESSAGE,
        Permission.EDIT_ANY_MESSAGE,
        Permission.MANAGE_TEAMS,
        Permission.VIEW_AUDIT_LOGS,
        Permission.SYSTEM_SETTINGS,
    ],
    "team_admin": [
        Permission.VIEW_USERS,
        Permission.MUTE_USERS,
        Permission.CREATE_CHANNELS,
        Permission.ARCHIVE_CHANNELS,
        Permission.MANAGE_CHANNEL_MEMBERS,
        Permission.DELETE_ANY_MESSAGE,
        Permission.VIEW_AUDIT_LOGS,
    ],
    "member": [
        Permission.VIEW_USERS,
        Permission.CREATE_CHANNELS,
    ],
    "guest": [],
}


def get_user_permissions(role: str, is_system_admin: bool = False) -> List[str]:
    """Get all permissions for a user based on role"""
    # System admin flag overrides role
    if is_system_admin:
        return ROLE_PERMISSIONS.get("system_admin", [])
    return ROLE_PERMISSIONS.get(role, [])


def has_permission(role: str, permission: str, is_system_admin: bool = False) -> bool:
    """Check if a role has a specific permission"""
    permissions = get_user_permissions(role, is_system_admin)
    return permission in permissions


async def require_permission(permission: str, db: AsyncSession, user_data: dict):
    """Check if current user has required permission"""
    from app.db.models import User
    
    result = await db.execute(select(User).where(User.id == user_data["user_id"]))
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    if user.is_banned:
        raise HTTPException(status_code=403, detail="User is banned")
    
    role = user.role.value if user.role else "member"
    if not has_permission(role, permission, user.is_system_admin):
        raise HTTPException(
            status_code=403,
            detail=f"Permission denied: {permission} required"
        )
    
    return user


async def require_admin(db: AsyncSession, user_data: dict):
    """Require user to be a system admin"""
    from app.db.models import User
    
    result = await db.execute(select(User).where(User.id == user_data["user_id"]))
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    if user.is_banned:
        raise HTTPException(status_code=403, detail="User is banned")
    
    role_val = user.role.value if hasattr(user.role, 'value') else user.role
    if not user.is_system_admin and (not role_val or role_val != UserRole.system_admin.value):
        raise HTTPException(status_code=403, detail="Admin access required")
    
    return user


async def check_user_can_post(db: AsyncSession, user_id: int) -> bool:
    """Check if a user is allowed to post messages"""
    from app.db.models import User
    
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    
    if not user:
        return False
    
    if user.is_banned:
        return False
    
    if user.is_muted:
        # Check if mute has expired
        if user.muted_until and user.muted_until < datetime.utcnow():
            # Mute expired - should be cleared but allow posting
            return True
        return False
    
    return True


# === Rate Limiting Utilities (Phase 8.3) ===

async def check_user_rate_limit(
    request: Request,
    db: AsyncSession,
    user_data: dict,
) -> dict:
    """
    Check user-based rate limit for authenticated routes.
    Returns rate limit info or raises HTTPException if exceeded.
    
    Usage as dependency:
        @router.get("/endpoint")
        async def endpoint(
            db: AsyncSession = Depends(get_db),
            current_user: dict = Depends(get_current_user),
            rate_info: dict = Depends(lambda r, db, u: check_user_rate_limit(r, db, u)),
        ):
            ...
    """
    from app.db.models import User
    from app.core.rate_limiter import check_rate_limit, get_client_ip
    from app.core.rate_limit_config import rate_limit_settings
    
    if not rate_limit_settings.ENABLED:
        return {"limited": False}
    
    user_id = user_data["user_id"]
    
    # Get user to check if admin
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    
    is_admin = False
    if user:
        role_val = user.role.value if hasattr(user.role, 'value') else user.role
        is_admin = user.is_system_admin or role_val == "system_admin"
    
    # Apply user-based rate limiting
    rate_result = await check_rate_limit(
        identifier=str(user_id),
        identifier_type="user",
        path=str(request.url.path),
        is_admin=is_admin,
    )
    
    if not rate_result.allowed:
        request_id = getattr(request.state, 'request_id', 'unknown')
        raise HTTPException(
            status_code=429,
            detail="Too many requests. Please slow down.",
            headers={
                'Retry-After': str(rate_result.retry_after),
                'X-RateLimit-Limit': str(rate_result.limit),
                'X-RateLimit-Remaining': str(rate_result.remaining),
                'X-RateLimit-Reset': str(rate_result.reset_after),
            },
        )
    
    return {
        "limited": False,
        "remaining": rate_result.remaining,
        "limit": rate_result.limit,
        "reset_after": rate_result.reset_after,
    }


def rate_limited_user():
    """
    Dependency factory for user-based rate limiting.
    Apply to routes after authentication.
    
    Usage:
        @router.post("/create")
        async def create_item(
            db: AsyncSession = Depends(get_db),
            current_user: dict = Depends(get_current_user),
            _rate: dict = Depends(rate_limited_user()),
        ):
            ...
    """
    async def dependency(
        request: Request,
        credentials: HTTPAuthorizationCredentials = Depends(security),
    ):
        from app.core.rate_limiter import check_rate_limit, get_client_ip
        from app.core.rate_limit_config import rate_limit_settings
        
        if not rate_limit_settings.ENABLED:
            return {"limited": False}
        
        # Decode token to get user info
        token = credentials.credentials
        try:
            payload = decode_token(token)
            user_id = payload.get("sub")
        except HTTPException:
            # If token is invalid, fall back to IP-based
            user_id = None
        
        if user_id:
            # User-based rate limiting
            rate_result = await check_rate_limit(
                identifier=str(user_id),
                identifier_type="user",
                path=str(request.url.path),
                is_admin=False,  # Will be checked in actual auth
            )
        else:
            # IP-based fallback
            client_ip = get_client_ip(request)
            rate_result = await check_rate_limit(
                identifier=client_ip,
                identifier_type="ip",
                path=str(request.url.path),
                is_admin=False,
            )
        
        if not rate_result.allowed:
            raise HTTPException(
                status_code=429,
                detail="Too many requests. Please slow down.",
                headers={
                    'Retry-After': str(rate_result.retry_after),
                    'X-RateLimit-Limit': str(rate_result.limit),
                    'X-RateLimit-Remaining': str(rate_result.remaining),
                    'X-RateLimit-Reset': str(rate_result.reset_after),
                },
            )
        
        return {
            "remaining": rate_result.remaining,
            "limit": rate_result.limit,
        }
    
    return dependency
