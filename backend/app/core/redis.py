import redis
from app.core.config import settings
from app.db.enums import UserStatus


class RedisClient:
    def __init__(self):
        self.client = redis.Redis(
            host=settings.REDIS_HOST,
            port=settings.REDIS_PORT,
            password=settings.REDIS_PASSWORD or None,
            decode_responses=True,
        )
    
    async def set_user_status(self, user_id: int, status: str):
        """Set user online status"""
        self.client.hset(f"user:{user_id}", "status", status)
        self.client.expire(f"user:{user_id}", 300)  # 5 minute TTL
    
    async def get_user_status(self, user_id: int) -> str:
        """Get user online status"""
        status = self.client.hget(f"user:{user_id}", "status")
        return status or UserStatus.offline.value
    
    async def set_typing(self, channel_id: int, user_id: int):
        """Set user typing in channel"""
        key = f"typing:{channel_id}"
        self.client.sadd(key, user_id)
        self.client.expire(key, 5)  # 5 second TTL
    
    async def get_typing_users(self, channel_id: int) -> list:
        """Get users typing in channel"""
        key = f"typing:{channel_id}"
        return list(self.client.smembers(key))
    
    async def cache_message(self, channel_id: int, message: dict):
        """Cache recent message"""
        key = f"messages:{channel_id}"
        import json
        self.client.lpush(key, json.dumps(message))
        self.client.ltrim(key, 0, 99)  # Keep last 100 messages
    
    async def get_cached_messages(self, channel_id: int, limit: int = 50) -> list:
        """Get cached messages for channel"""
        key = f"messages:{channel_id}"
        import json
        messages = self.client.lrange(key, 0, limit - 1)
        return [json.loads(m) for m in messages]
    
    def health_check(self) -> bool:
        """Check Redis connectivity"""
        try:
            return self.client.ping()
        except Exception:
            return False


redis_client = RedisClient()
