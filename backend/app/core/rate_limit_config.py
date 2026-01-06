"""
Phase 8.3 - Rate Limiting Configuration

Centralized configuration for rate limits across the API.
Limits are defined per route category with different tiers for:
- Anonymous/IP-based requests
- Authenticated users
- Admin users
"""
from dataclasses import dataclass
from typing import Optional
import os


@dataclass
class RateLimit:
    """Rate limit configuration for a specific tier."""
    requests: int  # Number of requests allowed
    window_seconds: int  # Time window in seconds
    
    @property
    def requests_per_minute(self) -> float:
        """Calculate equivalent requests per minute."""
        return (self.requests / self.window_seconds) * 60


@dataclass
class RateLimitTier:
    """Rate limits for different user types."""
    anonymous: RateLimit  # IP-based for unauthenticated
    authenticated: RateLimit  # User-based for authenticated
    admin: RateLimit  # Higher limits for admins


# === Rate Limit Configurations ===

# Auth endpoints (login, register) - stricter to prevent brute force
AUTH_LIMITS = RateLimitTier(
    anonymous=RateLimit(requests=10, window_seconds=60),  # 10/min per IP
    authenticated=RateLimit(requests=20, window_seconds=60),  # 20/min per user
    admin=RateLimit(requests=50, window_seconds=60),  # 50/min for admins
)

# General API endpoints (channels, messages, users)
API_LIMITS = RateLimitTier(
    anonymous=RateLimit(requests=60, window_seconds=60),  # 60/min per IP
    authenticated=RateLimit(requests=120, window_seconds=60),  # 120/min per user
    admin=RateLimit(requests=300, window_seconds=60),  # 300/min for admins
)

# Sales endpoints
SALES_LIMITS = RateLimitTier(
    anonymous=RateLimit(requests=30, window_seconds=60),  # 30/min per IP
    authenticated=RateLimit(requests=60, window_seconds=60),  # 60/min per user
    admin=RateLimit(requests=200, window_seconds=60),  # 200/min for admins
)

# Inventory endpoints
INVENTORY_LIMITS = RateLimitTier(
    anonymous=RateLimit(requests=30, window_seconds=60),  # 30/min per IP
    authenticated=RateLimit(requests=60, window_seconds=60),  # 60/min per user
    admin=RateLimit(requests=200, window_seconds=60),  # 200/min for admins
)

# Automation endpoints (tasks, orders)
AUTOMATION_LIMITS = RateLimitTier(
    anonymous=RateLimit(requests=20, window_seconds=60),  # 20/min per IP
    authenticated=RateLimit(requests=60, window_seconds=60),  # 60/min per user
    admin=RateLimit(requests=150, window_seconds=60),  # 150/min for admins
)

# Notification endpoints
NOTIFICATION_LIMITS = RateLimitTier(
    anonymous=RateLimit(requests=30, window_seconds=60),  # 30/min per IP
    authenticated=RateLimit(requests=100, window_seconds=60),  # 100/min per user
    admin=RateLimit(requests=200, window_seconds=60),  # 200/min for admins
)

# WebSocket connections (per connection attempt)
WEBSOCKET_LIMITS = RateLimitTier(
    anonymous=RateLimit(requests=5, window_seconds=60),  # 5/min per IP
    authenticated=RateLimit(requests=10, window_seconds=60),  # 10/min per user
    admin=RateLimit(requests=20, window_seconds=60),  # 20/min for admins
)

# File upload endpoints (stricter due to resource usage)
UPLOAD_LIMITS = RateLimitTier(
    anonymous=RateLimit(requests=5, window_seconds=60),  # 5/min per IP
    authenticated=RateLimit(requests=20, window_seconds=60),  # 20/min per user
    admin=RateLimit(requests=50, window_seconds=60),  # 50/min for admins
)

# Admin endpoints (only accessible by admins anyway)
ADMIN_LIMITS = RateLimitTier(
    anonymous=RateLimit(requests=60, window_seconds=60),   # 60/min - will be rejected by auth anyway
    authenticated=RateLimit(requests=300, window_seconds=60),  # 300/min
    admin=RateLimit(requests=1000, window_seconds=60),  # 1000/min for admins
)

# System Console endpoints (admin-only, Phase 8.4)
SYSTEM_LIMITS = RateLimitTier(
    anonymous=RateLimit(requests=60, window_seconds=60),   # 60/min - will be rejected by auth anyway
    authenticated=RateLimit(requests=300, window_seconds=60),  # 300/min
    admin=RateLimit(requests=1000, window_seconds=60),  # 1000/min for admins
)

# Audit Log endpoints (admin-only, Phase 8.4.1)
AUDIT_LIMITS = RateLimitTier(
    anonymous=RateLimit(requests=60, window_seconds=60),   # 60/min - will be rejected by auth anyway
    authenticated=RateLimit(requests=300, window_seconds=60),  # 300/min
    admin=RateLimit(requests=1000, window_seconds=60),  # 1000/min for admins
)


# === Global Settings ===

class RateLimitSettings:
    """Global rate limiting settings."""
    
    # Enable/disable rate limiting globally
    ENABLED: bool = os.getenv("RATE_LIMIT_ENABLED", "true").lower() == "true"
    
    # Use Redis for distributed rate limiting (vs in-memory for single instance)
    USE_REDIS: bool = os.getenv("RATE_LIMIT_USE_REDIS", "false").lower() == "true"
    
    # Whitelist certain IPs (comma-separated)
    WHITELIST_IPS: list[str] = [
        ip.strip() 
        for ip in os.getenv("RATE_LIMIT_WHITELIST_IPS", "").split(",") 
        if ip.strip()
    ]
    
    # Header to check for real IP (behind proxy)
    REAL_IP_HEADER: str = os.getenv("RATE_LIMIT_REAL_IP_HEADER", "X-Forwarded-For")
    
    # Redis key prefix for rate limit counters
    REDIS_PREFIX: str = "ratelimit:"
    
    # Default cleanup interval for in-memory storage (seconds)
    CLEANUP_INTERVAL: int = 300  # 5 minutes


rate_limit_settings = RateLimitSettings()


# === Route to Limit Mapping ===

def get_limit_tier_for_path(path: str) -> RateLimitTier:
    """
    Get the appropriate rate limit tier based on the request path.
    """
    path_lower = path.lower()
    
    # Auth endpoints
    if '/auth/' in path_lower or path_lower.endswith('/auth'):
        return AUTH_LIMITS
    
    # System Console endpoints (Phase 8.4)
    if '/system/' in path_lower or path_lower.endswith('/system'):
        return SYSTEM_LIMITS
    
    # Audit endpoints
    if '/audit' in path_lower:
        return AUDIT_LIMITS
    
    # Admin endpoints
    if '/admin/' in path_lower or path_lower.endswith('/admin'):
        return ADMIN_LIMITS
    
    # Sales endpoints
    if '/sales/' in path_lower or path_lower.endswith('/sales'):
        return SALES_LIMITS
    
    # Inventory endpoints
    if '/inventory/' in path_lower or path_lower.endswith('/inventory'):
        return INVENTORY_LIMITS
    
    # Automation/tasks/orders
    if any(x in path_lower for x in ['/tasks/', '/orders/', '/automation/']):
        return AUTOMATION_LIMITS
    
    # Notifications
    if '/notifications/' in path_lower or path_lower.endswith('/notifications'):
        return NOTIFICATION_LIMITS
    
    # WebSocket
    if '/ws/' in path_lower or path_lower.endswith('/ws'):
        return WEBSOCKET_LIMITS
    
    # File uploads
    if '/upload' in path_lower or '/files/' in path_lower:
        return UPLOAD_LIMITS
    
    # Default to general API limits
    return API_LIMITS
