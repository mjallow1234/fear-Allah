"""
Socket.IO authentication module.
Validates JWT tokens for socket connections.
"""
from typing import Optional, Tuple
from jose import JWTError, jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.database import async_session
from app.db.models import User, TeamMember
import logging

logger = logging.getLogger(__name__)


async def authenticate_socket(auth: dict = None, environ: dict = None) -> Tuple[bool, Optional[dict]]:
    """
    Authenticate a Socket.IO connection using JWT.
    
    Extracts token from:
    1. auth.token (preferred - sent in Socket.IO auth object)
    2. Authorization header (fallback)
    
    Returns:
        Tuple of (is_authenticated, user_data)
        user_data contains: user_id, team_id, username if authenticated
    """
    token = None
    
    # Try auth object first (preferred method)
    if auth and isinstance(auth, dict):
        token = auth.get("token")
    
    # Fallback to Authorization header
    if not token and environ:
        headers = environ.get("HTTP_AUTHORIZATION", "")
        if headers.startswith("Bearer "):
            token = headers[7:]
    
    if not token:
        logger.warning("Socket connection rejected: No token provided")
        return False, None
    
    try:
        # Decode JWT using existing settings
        payload = jwt.decode(
            token, 
            settings.JWT_SECRET, 
            algorithms=[settings.JWT_ALGORITHM]
        )
        
        user_id = payload.get("sub")
        if not user_id:
            logger.warning("Socket connection rejected: No user_id in token")
            return False, None
        
        user_id = int(user_id)
        
        # Fetch user details from database
        async with async_session() as db:
            result = await db.execute(
                select(User).where(User.id == user_id)
            )
            user = result.scalar_one_or_none()
            
            if not user:
                logger.warning(f"Socket connection rejected: User {user_id} not found")
                return False, None
            
            if not user.is_active:
                logger.warning(f"Socket connection rejected: User {user_id} is inactive")
                return False, None

            if getattr(user, "must_change_password", False):
                logger.warning(f"Socket connection rejected: User {user_id} must change password")
                return False, None
            
            # Get user's team_id (first team membership)
            team_result = await db.execute(
                select(TeamMember.team_id).where(TeamMember.user_id == user_id).limit(1)
            )
            team_row = team_result.first()
            team_id = team_row[0] if team_row else None
            
            user_data = {
                "user_id": user_id,
                "username": user.username,
                "display_name": user.display_name,
                "role": user.role,
                "team_id": team_id,
            }
            
            logger.info(f"Socket authenticated for user {user.username} (ID: {user_id})")
            return True, user_data
            
    except JWTError as e:
        logger.warning(f"Socket connection rejected: Invalid JWT - {e}")
        return False, None
    except Exception as e:
        logger.error(f"Socket authentication error: {e}")
        return False, None


def decode_token_sync(token: str) -> Optional[dict]:
    """
    Synchronous token decode for simple validation.
    Does not verify user exists in database.
    """
    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET,
            algorithms=[settings.JWT_ALGORITHM]
        )
        return payload
    except JWTError:
        return None
