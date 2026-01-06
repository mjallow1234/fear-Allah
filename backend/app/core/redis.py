import redis
import uuid
import json
from app.core.config import settings
from app.db.enums import UserStatus
from datetime import datetime


class RedisClient:
    def __init__(self):
        # Normal runtime client
        self.client = redis.Redis(
            host=settings.REDIS_HOST,
            port=settings.REDIS_PORT,
            password=settings.REDIS_PASSWORD or None,
            decode_responses=True,
        )
        # Unique instance id so a pod can ignore its own published events
        self.instance_id = uuid.uuid4().hex
    
    async def set_user_status(self, user_id: int, status: str):
        """Set presence for a user and publish presence update.

        Presence key: `presence:user:{user_id}` --> JSON {status, last_seen}
        TTL: 60 seconds
        """
        key = f"presence:user:{user_id}"
        payload = {"status": status, "last_seen": datetime.utcnow().isoformat()}
        try:
            self.client.set(key, json.dumps(payload))
            self.client.expire(key, 60)
            # Publish best-effort presence event to all pods
            self.client.publish("presence", json.dumps({"type": "presence_update", "user_id": user_id, **payload, "origin": self.instance_id}))
        except Exception:
            # Best-effort: don't raise on Redis failure
            return


class NullRedisClient:
    """A test-friendly no-op Redis client.
    Methods mirror the interface used by the app but do nothing / return sensible defaults.
    """
    def __init__(self):
        self.instance_id = uuid.uuid4().hex

    async def set_user_status(self, user_id: int, status: str):
        return

    async def get_user_status(self, user_id: int) -> str:
        return None

    async def set_typing(self, channel_id: int, user_id: int):
        return

    async def clear_typing(self, channel_id: int, user_id: int):
        return

    async def get_typing_users(self, channel_id: int) -> list:
        return []

    async def cache_message(self, channel_id: int, message: dict):
        return

    async def get_cached_messages(self, channel_id: int, limit: int = 50) -> list:
        return []

    def health_check(self) -> bool:
        return False

    def publish_channel_event(self, channel_id: int, payload: dict) -> None:
        return


# Expose a module-level factory/getter so callers can use a simple import
def get_redis():
    if settings.TESTING:
        return NullRedisClient()
    return RedisClient()

# Backwards-compatible module-level instance for code that imports `redis_client`
redis_client = get_redis()
