from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from pydantic import BaseModel, EmailStr
from typing import Optional

from app.db.database import get_db
from app.db.models import User, Team
from app.core.security import verify_password, get_password_hash, create_access_token
from app.core.rate_limiter import check_rate_limit, get_client_ip
from app.core.rate_limit_config import AUTH_LIMITS, rate_limit_settings

router = APIRouter()


# === Rate Limiting for Auth Endpoints ===
# Note: The RateLimitMiddleware already applies IP-based rate limiting.
# This dependency provides additional per-endpoint tracking for auth abuse detection.
# Both use the same rate bucket so there's no double-counting.

async def auth_rate_limit(request: Request):
    """
    Rate limiting marker for auth endpoints (login/register).
    The actual limiting is done by RateLimitMiddleware.
    This dependency is kept for clarity and potential future per-action tracking.
    """
    # Rate limiting is handled by RateLimitMiddleware
    # This is a no-op but documents that auth endpoints are rate limited
    pass


class LoginRequest(BaseModel):
    identifier: str  # username or email
    password: str


class RegisterRequest(BaseModel):
    username: str
    email: EmailStr
    password: str
    display_name: Optional[str] = None
    role: Optional[str] = None  # Business role: agent, storekeeper, delivery, foreman, customer


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: dict


class UserResponse(BaseModel):
    id: int
    username: str
    email: str
    display_name: Optional[str]
    avatar_url: Optional[str]
    is_system_admin: bool

    class Config:
        from_attributes = True


@router.post("/login", response_model=TokenResponse)
async def login(
    request: LoginRequest,
    http_request: Request,
    db: AsyncSession = Depends(get_db),
    _: None = Depends(auth_rate_limit),
):
    # Prevent login if system is not initialized based on persisted flag
    from app.db.models import SystemState

    result = await db.execute(select(SystemState))
    state = result.scalar_one_or_none()
    if not (state and state.setup_completed):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="System not initialized. Visit /setup",
        )

    # Find user by username or email
    query = select(User).where(
        (User.username == request.identifier) | (User.email == request.identifier)
    )
    result = await db.execute(query)
    user = result.scalar_one_or_none()

    if not user or not verify_password(request.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username/email or password",
        )
    
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is disabled",
        )
    
    # Phase 8.4.4: Include is_system_admin in JWT for rate limit decisions
    access_token = create_access_token(data={
        "sub": str(user.id), 
        "username": user.username,
        "is_system_admin": user.is_system_admin,
    })
    
    return TokenResponse(
        access_token=access_token,
        user={
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "display_name": user.display_name,
            "avatar_url": user.avatar_url,
            "is_system_admin": user.is_system_admin,
            "role": user.role,
        }
    )


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register(
    request: RegisterRequest,
    http_request: Request,
    db: AsyncSession = Depends(get_db),
    _: None = Depends(auth_rate_limit),
):
    # Check if username exists
    query = select(User).where(User.username == request.username)
    result = await db.execute(query)
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already registered",
        )
    
    # Check if email exists
    query = select(User).where(User.email == request.email)
    result = await db.execute(query)
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered",
        )
    
    # Validate role if provided
    valid_roles = {'agent', 'storekeeper', 'delivery', 'foreman', 'customer', 'member', 'guest'}
    user_role = request.role if request.role in valid_roles else 'member'
    
    # Create user
    user = User(
        username=request.username,
        email=request.email,
        hashed_password=get_password_hash(request.password),
        display_name=request.display_name or request.username,
        role=user_role,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    
    # DEV-only: auto-onboard new user to all demo channels
    from app.permissions.demo_onboarding import maybe_onboard_demo_user
    await maybe_onboard_demo_user(user.id, db)

    # Ensure the user is a member of the default 'general' channel so they have a readable channel after first login.
    # Prefer existing channel 'general', otherwise create it as public.
    # Use models to find or create the 'general' channel
    from app.db.models import Channel, ChannelMember, ChannelType, Role, ChannelRoleAssignment
    from app.permissions.roles import ChannelRole

    result = await db.execute(select(Channel).where(Channel.name == 'general'))
    general_channel = result.scalar_one_or_none()
    if not general_channel:
        general_channel = Channel(name='general', display_name='General', description='General discussion', type=ChannelType.public.value)
        db.add(general_channel)
        await db.commit()
        await db.refresh(general_channel)

    # Add membership if not exists
    result = await db.execute(select(ChannelMember).where(ChannelMember.user_id == user.id, ChannelMember.channel_id == general_channel.id))
    membership = result.scalar_one_or_none()
    if not membership:
        new_membership = ChannelMember(user_id=user.id, channel_id=general_channel.id)
        db.add(new_membership)
        await db.commit()

    # Add ChannelRoleAssignment (member role) for the general channel if not exists
    # This ensures new users have read permissions on the general channel
    result = await db.execute(
        select(Role).where(Role.name == ChannelRole.MEMBER.value, Role.scope == "channel")
    )
    member_role = result.scalar_one_or_none()
    
    if member_role:
        result = await db.execute(
            select(ChannelRoleAssignment).where(
                ChannelRoleAssignment.user_id == user.id,
                ChannelRoleAssignment.channel_id == general_channel.id,
                ChannelRoleAssignment.role_id == member_role.id
            )
        )
        if not result.scalar_one_or_none():
            assignment = ChannelRoleAssignment(
                user_id=user.id,
                channel_id=general_channel.id,
                role_id=member_role.id
            )
            db.add(assignment)
            await db.commit()

    # Phase 8.4.4: Include is_system_admin in JWT for rate limit decisions
    access_token = create_access_token(data={
        "sub": str(user.id), 
        "username": user.username,
        "is_system_admin": user.is_system_admin,
    })
    
    return TokenResponse(
        access_token=access_token,
        user={
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "display_name": user.display_name,
            "avatar_url": user.avatar_url,
            "is_system_admin": user.is_system_admin,
            "role": user.role,
        }
    )


@router.post("/logout")
async def logout():
    # For JWT, logout is handled client-side by removing the token
    return {"message": "Successfully logged out"}
