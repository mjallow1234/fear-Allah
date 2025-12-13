import redis
import uuid
import json
from app.core.config import settings
from app.db.enums import UserStatus
from datetime import datetime


class RedisClient:
    def __init__(self):
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
    
    async def get_user_status(self, user_id: int) -> str:
        """Get user online status from presence key (returns status string)."""
        try:
            raw = self.client.get(f"presence:user:{user_id}")
            if not raw:
                return UserStatus.offline.value
            data = json.loads(raw)
            return data.get("status", UserStatus.offline.value)
        except Exception:
            return UserStatus.offline.value
    
    async def set_typing(self, channel_id: int, user_id: int):
        """Set user typing in channel"""
        key = f"typing:channel:{channel_id}"
        self.client.sadd(key, user_id)
        # Reset TTL on each typing set so active typing persists
        self.client.expire(key, 5)
        # Publish typing update to channel-level pubsub
        try:
            self.client.publish(f"channel:{channel_id}", json.dumps({"type": "typing_update", "channel_id": channel_id, "user_id": user_id, "action": "start", "origin": self.instance_id}))
        except Exception:
            pass

    async def clear_typing(self, channel_id: int, user_id: int):
        """Clear a user's typing indicator in a channel and publish update."""
        key = f"typing:channel:{channel_id}"
        try:
            self.client.srem(key, user_id)
            # Publish typing stop
            self.client.publish(f"channel:{channel_id}", json.dumps({"type": "typing_update", "channel_id": channel_id, "user_id": user_id, "action": "stop", "origin": self.instance_id}))
        except Exception:
            pass
    
    async def get_typing_users(self, channel_id: int) -> list:
        """Get users typing in channel"""
        key = f"typing:channel:{channel_id}"
        try:
            return list(self.client.smembers(key))
        except Exception:
            return []
    
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

    def publish_channel_event(self, channel_id: int, payload: dict) -> None:
        """Publish a JSON payload for a channel to Redis pub/sub.

        Adds `origin` to the payload for origin filtering on subscribers.
        """
        try:
            payload = dict(payload)
            payload["origin"] = self.instance_id
            self.client.publish(f"channel:{channel_id}", json.dumps(payload))
        except Exception:
            # Never raise on pub/sub publish failure — best-effort
            return


redis_client = RedisClient()
