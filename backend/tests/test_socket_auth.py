"""
Tests for Socket.IO authentication.
Phase 4.1 - Real-time foundation.
"""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from jose import jwt
from datetime import datetime, timedelta

from app.core.config import settings
from app.realtime.auth import authenticate_socket, decode_token_sync


def create_test_token(user_id: int, expires_delta: timedelta = None) -> str:
    """Create a test JWT token."""
    if expires_delta is None:
        expires_delta = timedelta(hours=1)
    
    expire = datetime.utcnow() + expires_delta
    payload = {
        "sub": str(user_id),
        "exp": expire,
    }
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


def create_expired_token(user_id: int) -> str:
    """Create an expired JWT token."""
    return create_test_token(user_id, timedelta(hours=-1))


class TestDecodeTokenSync:
    """Tests for synchronous token decoding."""
    
    def test_valid_token(self):
        """Valid token should decode correctly."""
        token = create_test_token(user_id=123)
        payload = decode_token_sync(token)
        
        assert payload is not None
        assert payload["sub"] == "123"
    
    def test_expired_token(self):
        """Expired token should return None."""
        token = create_expired_token(user_id=123)
        payload = decode_token_sync(token)
        
        assert payload is None
    
    def test_invalid_token(self):
        """Invalid token should return None."""
        payload = decode_token_sync("invalid-token")
        
        assert payload is None
    
    def test_wrong_secret(self):
        """Token signed with wrong secret should return None."""
        wrong_token = jwt.encode(
            {"sub": "123", "exp": datetime.utcnow() + timedelta(hours=1)},
            "wrong-secret",
            algorithm=settings.JWT_ALGORITHM
        )
        payload = decode_token_sync(wrong_token)
        
        assert payload is None


class TestAuthenticateSocket:
    """Tests for socket authentication."""
    
    @pytest.mark.asyncio
    async def test_reject_no_token(self):
        """Should reject connection without token."""
        is_auth, user_data = await authenticate_socket(auth=None, environ=None)
        
        assert is_auth is False
        assert user_data is None
    
    @pytest.mark.asyncio
    async def test_reject_empty_auth(self):
        """Should reject connection with empty auth object."""
        is_auth, user_data = await authenticate_socket(auth={}, environ={})
        
        assert is_auth is False
        assert user_data is None
    
    @pytest.mark.asyncio
    async def test_reject_invalid_token(self):
        """Should reject connection with invalid token."""
        is_auth, user_data = await authenticate_socket(
            auth={"token": "invalid-token"},
            environ={}
        )
        
        assert is_auth is False
        assert user_data is None
    
    @pytest.mark.asyncio
    async def test_reject_expired_token(self):
        """Should reject connection with expired token."""
        token = create_expired_token(user_id=123)
        
        is_auth, user_data = await authenticate_socket(
            auth={"token": token},
            environ={}
        )
        
        assert is_auth is False
        assert user_data is None
    
    @pytest.mark.asyncio
    async def test_accept_valid_token_from_auth(self):
        """Should accept connection with valid token from auth object."""
        # Create a mock user
        mock_user = MagicMock()
        mock_user.id = 123
        mock_user.username = "testuser"
        mock_user.display_name = "Test User"
        mock_user.team_id = 1
        mock_user.role = "member"
        mock_user.is_active = True
        
        token = create_test_token(user_id=123)
        
        # Mock the database session with proper async context manager
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_user
        
        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(return_value=mock_result)
        
        mock_session_cm = AsyncMock()
        mock_session_cm.__aenter__.return_value = mock_db
        mock_session_cm.__aexit__.return_value = None
        
        with patch("app.realtime.auth.async_session", return_value=mock_session_cm):
            is_auth, user_data = await authenticate_socket(
                auth={"token": token},
                environ={}
            )
        
        assert is_auth is True
        assert user_data is not None
        assert user_data["user_id"] == 123
        assert user_data["username"] == "testuser"
        assert user_data["team_id"] == 1
    
    @pytest.mark.asyncio
    async def test_accept_valid_token_from_header(self):
        """Should accept connection with valid token from Authorization header."""
        mock_user = MagicMock()
        mock_user.id = 456
        mock_user.username = "headeruser"
        mock_user.display_name = "Header User"
        mock_user.team_id = 2
        mock_user.role = "member"
        mock_user.is_active = True
        
        token = create_test_token(user_id=456)
        
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_user
        
        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(return_value=mock_result)
        
        mock_session_cm = AsyncMock()
        mock_session_cm.__aenter__.return_value = mock_db
        mock_session_cm.__aexit__.return_value = None
        
        with patch("app.realtime.auth.async_session", return_value=mock_session_cm):
            is_auth, user_data = await authenticate_socket(
                auth=None,
                environ={"HTTP_AUTHORIZATION": f"Bearer {token}"}
            )
        
        assert is_auth is True
        assert user_data is not None
        assert user_data["user_id"] == 456
        assert user_data["username"] == "headeruser"
    
    @pytest.mark.asyncio
    async def test_reject_user_not_found(self):
        """Should reject if user not found in database."""
        token = create_test_token(user_id=999)
        
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None  # User not found
        
        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(return_value=mock_result)
        
        mock_session_cm = AsyncMock()
        mock_session_cm.__aenter__.return_value = mock_db
        mock_session_cm.__aexit__.return_value = None
        
        with patch("app.realtime.auth.async_session", return_value=mock_session_cm):
            is_auth, user_data = await authenticate_socket(
                auth={"token": token},
                environ={}
            )
        
        assert is_auth is False
        assert user_data is None
    
    @pytest.mark.asyncio
    async def test_reject_inactive_user(self):
        """Should reject if user is inactive."""
        mock_user = MagicMock()
        mock_user.id = 123
        mock_user.username = "inactiveuser"
        mock_user.is_active = False  # User is inactive
        
        token = create_test_token(user_id=123)
        
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_user
        
        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(return_value=mock_result)
        
        mock_session_cm = AsyncMock()
        mock_session_cm.__aenter__.return_value = mock_db
        mock_session_cm.__aexit__.return_value = None
        
        with patch("app.realtime.auth.async_session", return_value=mock_session_cm):
            is_auth, user_data = await authenticate_socket(
                auth={"token": token},
                environ={}
            )
        
        assert is_auth is False
        assert user_data is None
    
    @pytest.mark.asyncio
    async def test_auth_token_takes_precedence_over_header(self):
        """Auth token should take precedence over header token."""
        mock_user = MagicMock()
        mock_user.id = 111
        mock_user.username = "authuser"
        mock_user.display_name = "Auth User"
        mock_user.team_id = 1
        mock_user.role = "member"
        mock_user.is_active = True
        
        auth_token = create_test_token(user_id=111)
        header_token = create_test_token(user_id=222)
        
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_user
        
        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(return_value=mock_result)
        
        mock_session_cm = AsyncMock()
        mock_session_cm.__aenter__.return_value = mock_db
        mock_session_cm.__aexit__.return_value = None
        
        with patch("app.realtime.auth.async_session", return_value=mock_session_cm):
            is_auth, user_data = await authenticate_socket(
                auth={"token": auth_token},
                environ={"HTTP_AUTHORIZATION": f"Bearer {header_token}"}
            )
        
        assert is_auth is True
        assert user_data["user_id"] == 111  # Should use auth token user
