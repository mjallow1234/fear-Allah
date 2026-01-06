"""
Phase 8.3 - Rate Limiter Service

Provides rate limiting functionality using sliding window algorithm.
Supports both in-memory (single instance) and Redis (distributed) storage.
"""
import time
import asyncio
from typing import Optional, Tuple
from dataclasses import dataclass, field
from collections import defaultdict

from app.core.rate_limit_config import (
    RateLimit,
    RateLimitTier,
    rate_limit_settings,
    get_limit_tier_for_path,
)
from app.core.logging import api_logger


@dataclass
class RateLimitResult:
    """Result of a rate limit check."""
    allowed: bool
    remaining: int  # Requests remaining in window
    reset_after: int  # Seconds until window resets
    limit: int  # Total limit for the window
    
    @property
    def retry_after(self) -> int:
        """Seconds to wait before retrying (for 429 response)."""
        return self.reset_after if not self.allowed else 0


@dataclass
class WindowEntry:
    """Entry for sliding window rate limiting."""
    count: int = 0
    window_start: float = field(default_factory=time.time)


class InMemoryRateLimiter:
    """
    In-memory rate limiter using sliding window algorithm.
    Suitable for single-instance deployments.
    """
    
    def __init__(self):
        # Key -> WindowEntry mapping
        self._windows: dict[str, WindowEntry] = defaultdict(WindowEntry)
        self._lock = asyncio.Lock()
        self._last_cleanup = time.time()
    
    async def check_rate_limit(
        self,
        key: str,
        limit: RateLimit,
    ) -> RateLimitResult:
        """
        Check if a request is allowed under the rate limit.
        
        Args:
            key: Unique identifier (e.g., "ip:192.168.1.1" or "user:123")
            limit: Rate limit configuration
        
        Returns:
            RateLimitResult with allowed status and metadata
        """
        async with self._lock:
            now = time.time()
            entry = self._windows[key]
            
            # Check if window has expired
            window_elapsed = now - entry.window_start
            if window_elapsed >= limit.window_seconds:
                # Reset window
                entry.count = 0
                entry.window_start = now
                window_elapsed = 0
            
            # Calculate remaining requests
            remaining = max(0, limit.requests - entry.count)
            reset_after = max(0, int(limit.window_seconds - window_elapsed))
            
            # Check if allowed
            if entry.count < limit.requests:
                entry.count += 1
                return RateLimitResult(
                    allowed=True,
                    remaining=remaining - 1,
                    reset_after=reset_after,
                    limit=limit.requests,
                )
            else:
                return RateLimitResult(
                    allowed=False,
                    remaining=0,
                    reset_after=reset_after,
                    limit=limit.requests,
                )
    
    async def cleanup_expired(self):
        """Remove expired window entries to prevent memory growth."""
        async with self._lock:
            now = time.time()
            expired_keys = [
                key for key, entry in self._windows.items()
                if now - entry.window_start > rate_limit_settings.CLEANUP_INTERVAL
            ]
            for key in expired_keys:
                del self._windows[key]
            
            if expired_keys:
                api_logger.debug(f"Rate limiter cleanup: removed {len(expired_keys)} expired entries")
    
    def get_stats(self) -> dict:
        """Get current rate limiter statistics."""
        return {
            "active_windows": len(self._windows),
            "last_cleanup": self._last_cleanup,
        }


class RedisRateLimiter:
    """
    Redis-based rate limiter for distributed deployments.
    Uses sliding window with Redis sorted sets.
    """
    
    def __init__(self, redis_client):
        self._redis = redis_client
        self._prefix = rate_limit_settings.REDIS_PREFIX
    
    async def check_rate_limit(
        self,
        key: str,
        limit: RateLimit,
    ) -> RateLimitResult:
        """
        Check if a request is allowed under the rate limit using Redis.
        """
        full_key = f"{self._prefix}{key}"
        now = time.time()
        window_start = now - limit.window_seconds
        
        try:
            # Use Redis pipeline for atomic operations
            pipe = self._redis.pipeline()
            
            # Remove old entries outside window
            pipe.zremrangebyscore(full_key, 0, window_start)
            
            # Count current requests in window
            pipe.zcard(full_key)
            
            # Execute pipeline
            results = await pipe.execute()
            current_count = results[1]
            
            # Check if allowed
            if current_count < limit.requests:
                # Add new request
                await self._redis.zadd(full_key, {str(now): now})
                await self._redis.expire(full_key, limit.window_seconds + 1)
                
                return RateLimitResult(
                    allowed=True,
                    remaining=limit.requests - current_count - 1,
                    reset_after=limit.window_seconds,
                    limit=limit.requests,
                )
            else:
                # Get oldest entry to calculate reset time
                oldest = await self._redis.zrange(full_key, 0, 0, withscores=True)
                if oldest:
                    reset_after = int(oldest[0][1] + limit.window_seconds - now)
                else:
                    reset_after = limit.window_seconds
                
                return RateLimitResult(
                    allowed=False,
                    remaining=0,
                    reset_after=max(0, reset_after),
                    limit=limit.requests,
                )
        
        except Exception as e:
            api_logger.error(f"Redis rate limit error: {e}")
            # Fail open - allow request if Redis fails
            return RateLimitResult(
                allowed=True,
                remaining=limit.requests,
                reset_after=limit.window_seconds,
                limit=limit.requests,
            )
    
    async def cleanup_expired(self):
        """Redis handles expiry automatically via TTL."""
        pass
    
    def get_stats(self) -> dict:
        """Get current rate limiter statistics."""
        return {
            "backend": "redis",
            "prefix": self._prefix,
        }


# Global rate limiter instance
_rate_limiter: Optional[InMemoryRateLimiter | RedisRateLimiter] = None


def get_rate_limiter() -> InMemoryRateLimiter | RedisRateLimiter:
    """Get or create the global rate limiter instance."""
    global _rate_limiter
    
    if _rate_limiter is None:
        if rate_limit_settings.USE_REDIS:
            try:
                from app.core.redis import get_redis
                redis_client = get_redis()
                _rate_limiter = RedisRateLimiter(redis_client)
                api_logger.info("Rate limiter initialized with Redis backend")
            except Exception as e:
                api_logger.warning(f"Failed to initialize Redis rate limiter: {e}, falling back to in-memory")
                _rate_limiter = InMemoryRateLimiter()
        else:
            _rate_limiter = InMemoryRateLimiter()
            api_logger.info("Rate limiter initialized with in-memory backend")
    
    return _rate_limiter


async def check_rate_limit(
    identifier: str,
    identifier_type: str,  # "ip" or "user"
    path: str,
    is_admin: bool = False,
) -> RateLimitResult:
    """
    Check rate limit for a request.
    
    Args:
        identifier: IP address or user ID
        identifier_type: "ip" for anonymous, "user" for authenticated
        path: Request path to determine limit tier
        is_admin: Whether the user is an admin
    
    Returns:
        RateLimitResult indicating if request is allowed
    """
    if not rate_limit_settings.ENABLED:
        # Rate limiting disabled
        return RateLimitResult(allowed=True, remaining=999, reset_after=0, limit=999)
    
    # Check whitelist
    if identifier_type == "ip" and identifier in rate_limit_settings.WHITELIST_IPS:
        return RateLimitResult(allowed=True, remaining=999, reset_after=0, limit=999)
    
    # Get appropriate limit tier for path
    tier = get_limit_tier_for_path(path)
    
    # Select limit based on user type
    if is_admin:
        limit = tier.admin
    elif identifier_type == "user":
        limit = tier.authenticated
    else:
        limit = tier.anonymous
    
    # Build rate limit key
    key = f"{identifier_type}:{identifier}:{path.split('/')[2] if len(path.split('/')) > 2 else 'root'}"
    
    # Check rate limit
    limiter = get_rate_limiter()
    return await limiter.check_rate_limit(key, limit)


def get_client_ip(request) -> str:
    """
    Extract client IP from request, handling proxies.
    """
    # Check for forwarded header (when behind proxy)
    forwarded = request.headers.get(rate_limit_settings.REAL_IP_HEADER)
    if forwarded:
        # X-Forwarded-For can contain multiple IPs: client, proxy1, proxy2
        # Take the first one (original client)
        return forwarded.split(",")[0].strip()
    
    # Fall back to direct client IP
    if request.client:
        return request.client.host
    
    return "unknown"


# Background task for periodic cleanup
async def rate_limit_cleanup_task():
    """Background task to periodically clean up expired rate limit entries."""
    while True:
        await asyncio.sleep(rate_limit_settings.CLEANUP_INTERVAL)
        try:
            limiter = get_rate_limiter()
            await limiter.cleanup_expired()
        except Exception as e:
            api_logger.error(f"Rate limit cleanup error: {e}")
