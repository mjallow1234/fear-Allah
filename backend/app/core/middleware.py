"""
Request Middleware (Phase 8.1 + 8.3 + 8.4.4)
Provides request_id injection, timing, global error handling, and rate limiting.
"""
import time
from typing import Callable, Optional
from fastapi import Request, Response, Depends, HTTPException
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from jose import JWTError, jwt

from app.core.logging import (
    get_request_id,
    set_request_id,
    generate_request_id,
    request_id_var,
    request_start_var,
    api_logger,
)
from app.core.rate_limiter import (
    check_rate_limit,
    get_client_ip,
    RateLimitResult,
    rate_limit_cleanup_task,
)
from app.core.rate_limit_config import rate_limit_settings
from app.core.config import settings


class RequestContextMiddleware(BaseHTTPMiddleware):
    """
    Middleware that:
    1. Generates/propagates request_id for tracing
    2. Tracks request timing
    3. Logs request/response summary
    """
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Get or generate request_id
        request_id = request.headers.get('X-Request-ID') or generate_request_id()
        
        # Set context variables
        request_id_var.set(request_id)
        request_start_var.set(time.time())
        
        # Store in request state for handlers
        request.state.request_id = request_id
        
        # Log request start (skip health checks to reduce noise)
        path = request.url.path
        if not path.endswith('/health') and not path.endswith('/ready'):
            api_logger.debug(
                f"{request.method} {path}",
                client=request.client.host if request.client else 'unknown',
            )
        
        try:
            response = await call_next(request)
            
            # Add request_id to response headers
            response.headers['X-Request-ID'] = request_id
            
            # Log response (skip health checks)
            if not path.endswith('/health') and not path.endswith('/ready'):
                duration = round((time.time() - request_start_var.get()) * 1000, 2)
                log_level = 'info' if response.status_code < 400 else 'warning'
                getattr(api_logger, log_level)(
                    f"{request.method} {path} -> {response.status_code}",
                    duration_ms=duration,
                    status=response.status_code,
                )
            
            return response
            
        except Exception as e:
            # Unexpected error - log and return safe JSON response
            duration = round((time.time() - request_start_var.get()) * 1000, 2)
            api_logger.error(
                f"{request.method} {path} -> 500 (unhandled)",
                error=e,
                duration_ms=duration,
            )
            
            return JSONResponse(
                status_code=500,
                content={
                    'detail': 'Internal server error',
                    'request_id': request_id,
                },
                headers={'X-Request-ID': request_id},
            )
        finally:
            # Clear context
            request_id_var.set(None)
            request_start_var.set(None)


async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """
    Global exception handler for unhandled exceptions.
    Returns safe JSON response with request_id for debugging.
    """
    request_id = getattr(request.state, 'request_id', None) or get_request_id() or 'unknown'
    
    api_logger.error(
        f"Unhandled exception in {request.method} {request.url.path}",
        error=exc,
        path=str(request.url.path),
    )
    
    return JSONResponse(
        status_code=500,
        content={
            'detail': 'Internal server error',
            'request_id': request_id,
        },
        headers={'X-Request-ID': request_id},
    )


async def http_exception_handler(request: Request, exc) -> JSONResponse:
    """
    Handler for HTTPException - adds request_id to error responses.
    """
    request_id = getattr(request.state, 'request_id', None) or get_request_id() or 'unknown'
    
    # Log 4xx as warning, 5xx as error
    status_code = getattr(exc, 'status_code', 500)
    detail = getattr(exc, 'detail', 'Unknown error')
    
    if status_code >= 500:
        api_logger.error(
            f"HTTP {status_code}: {detail}",
            path=str(request.url.path),
            status=status_code,
        )
    elif status_code >= 400:
        api_logger.warning(
            f"HTTP {status_code}: {detail}",
            path=str(request.url.path),
            status=status_code,
        )
    
    return JSONResponse(
        status_code=status_code,
        content={
            'detail': detail,
            'request_id': request_id,
        },
        headers={'X-Request-ID': request_id},
    )


async def validation_exception_handler(request: Request, exc) -> JSONResponse:
    """
    Handler for RequestValidationError - returns structured validation errors.
    """
    request_id = getattr(request.state, 'request_id', None) or get_request_id() or 'unknown'
    
    # Extract validation errors
    errors = []
    for error in exc.errors():
        errors.append({
            'field': '.'.join(str(loc) for loc in error.get('loc', [])),
            'message': error.get('msg', 'Validation error'),
            'type': error.get('type', 'value_error'),
        })
    
    api_logger.warning(
        f"Validation error in {request.method} {request.url.path}",
        errors=errors,
    )
    
    return JSONResponse(
        status_code=422,
        content={
            'detail': 'Validation error',
            'errors': errors,
            'request_id': request_id,
        },
        headers={'X-Request-ID': request_id},
    )


# === Rate Limiting (Phase 8.3) ===

class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Middleware that applies rate limiting to all requests.
    
    - Uses IP-based limiting for unauthenticated requests
    - Uses user-based limiting for authenticated requests
    - Admins get higher limits
    - Returns proper 429 with Retry-After header when exceeded
    """
    
    # Paths to skip rate limiting
    SKIP_PATHS = {
        '/health',
        '/ready',
        '/docs',
        '/redoc',
        '/openapi.json',
        '/api/system/status',
        '/api/system/status/',
    }
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        path = request.url.path
        
        # Skip rate limiting for health checks and docs
        if any(path.endswith(skip) for skip in self.SKIP_PATHS):
            return await call_next(request)
        
        # Skip rate limiting for OPTIONS (CORS preflight) - Phase 8.4.3
        if request.method == "OPTIONS":
            return await call_next(request)
        
        # Skip if rate limiting is disabled
        if not rate_limit_settings.ENABLED:
            return await call_next(request)

        # Path-based exemptions (Socket.IO and websocket API endpoints)
        # Socket.IO uses polling which results in many initial requests immediately after login.
        # Exempting these paths prevents the rate limiter from blocking legitimate socket bootstrap traffic.
        if path.startswith('/socket.io/') or path.startswith('/api/ws/'):
            return await call_next(request)
        
        # Get client identifier
        client_ip = get_client_ip(request)
        request_id = getattr(request.state, 'request_id', None) or 'unknown'
        
        # Phase 8.4.4: User-based rate limiting for authenticated requests
        # Try to extract user_id from JWT (best-effort, don't fail on invalid token)
        user_id: Optional[int] = None
        is_admin: bool = False
        identifier = client_ip
        identifier_type = "ip"
        
        auth_header = request.headers.get('Authorization', '')
        if auth_header.startswith('Bearer '):
            token = auth_header[7:]  # Remove "Bearer " prefix
            try:
                # Decode JWT to get user_id (don't raise on failure - fall back to IP)
                payload = jwt.decode(
                    token, 
                    settings.JWT_SECRET, 
                    algorithms=[settings.JWT_ALGORITHM]
                )
                user_id = payload.get("sub")
                is_admin = payload.get("is_system_admin", False)
                if user_id:
                    identifier = f"user:{user_id}"
                    identifier_type = "user"
            except JWTError:
                # Invalid token - fall back to IP-based limiting
                # Auth will be properly rejected by route handlers
                pass

        # Exempt authenticated GET routes used during app bootstrap from rate limiting
        # These requests are low-rate, critical for app bootstrap (teams/channels) and are made
        # immediately after login; exempting them prevents 429s while preserving global limits.
        # Exempt authenticated GET routes used during app bootstrap from rate limiting
        # These requests are low-rate, critical for app bootstrap (teams/channels) and are made
        # immediately after login; exempting them prevents 429s while preserving global limits.
        bootstrap_get_exempt_prefixes = (
            '/api/teams',
            '/api/users/me/teams',
            '/api/channels',
            '/api/channels/direct/list',
        )
        if identifier_type == 'user' and request.method == 'GET' and any(path.startswith(p) for p in bootstrap_get_exempt_prefixes):
            return await call_next(request)

        # Exempt onboarding POST endpoint so an authenticated non-admin user can complete first-team setup
        onboarding_post_exempt_prefixes = (
            '/api/onboarding/first-team',
        )
        if identifier_type == 'user' and request.method == 'POST' and any(path.startswith(p) for p in onboarding_post_exempt_prefixes):
            return await call_next(request)
        
        # Apply rate limiting (user-based if authenticated, IP-based otherwise)
        result = await check_rate_limit(
            identifier=identifier,
            identifier_type=identifier_type,
            path=path,
            is_admin=is_admin,
        )
        
        if not result.allowed:
            api_logger.warning(
                f"Rate limit exceeded for IP {client_ip}",
                path=path,
                limit=result.limit,
                reset_after=result.reset_after,
            )
            
            return JSONResponse(
                status_code=429,
                content={
                    'detail': 'Too many requests. Please slow down.',
                    'retry_after': result.retry_after,
                    'request_id': request_id,
                },
                headers={
                    'X-Request-ID': request_id,
                    'Retry-After': str(result.retry_after),
                    'X-RateLimit-Limit': str(result.limit),
                    'X-RateLimit-Remaining': str(result.remaining),
                    'X-RateLimit-Reset': str(result.reset_after),
                },
            )
        
        # Call next middleware/handler
        response = await call_next(request)
        
        # Add rate limit headers to response
        response.headers['X-RateLimit-Limit'] = str(result.limit)
        response.headers['X-RateLimit-Remaining'] = str(result.remaining)
        response.headers['X-RateLimit-Reset'] = str(result.reset_after)
        
        return response


async def rate_limit_429_response(
    result: RateLimitResult,
    request_id: str,
) -> JSONResponse:
    """Create a 429 Too Many Requests response."""
    return JSONResponse(
        status_code=429,
        content={
            'detail': 'Too many requests. Please slow down.',
            'retry_after': result.retry_after,
            'request_id': request_id,
        },
        headers={
            'X-Request-ID': request_id,
            'Retry-After': str(result.retry_after),
            'X-RateLimit-Limit': str(result.limit),
            'X-RateLimit-Remaining': str(result.remaining),
            'X-RateLimit-Reset': str(result.reset_after),
        },
    )


# === Rate Limit Dependencies for Routes ===

async def get_rate_limit_info(request: Request) -> dict:
    """
    Get rate limit info from request (set by middleware).
    Can be used by route handlers to access rate limit details.
    """
    return {
        'client_ip': get_client_ip(request),
        'request_id': getattr(request.state, 'request_id', 'unknown'),
    }


def create_user_rate_limiter(path_prefix: str = "api"):
    """
    Create a dependency that applies user-based rate limiting.
    Use this as a dependency in authenticated routes for stricter per-user limits.
    
    Usage:
        @router.get("/endpoint")
        async def endpoint(
            rate_limit: dict = Depends(create_user_rate_limiter("sales")),
            current_user: dict = Depends(get_current_user),
        ):
            ...
    """
    async def rate_limit_dependency(
        request: Request,
    ) -> dict:
        # This will be called after auth, so we could access user info
        # For now, just return info - the actual limiting is done in middleware
        return {
            'client_ip': get_client_ip(request),
            'path_prefix': path_prefix,
        }
    
    return rate_limit_dependency
