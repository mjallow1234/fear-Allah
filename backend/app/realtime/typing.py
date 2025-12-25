"""
Typing indicator tracking for channels.
Phase 4.3 - Real-time typing indicators.

Tracks which users are typing in each channel with TTL-based expiration.
"""
import logging
import time
from typing import Dict, Set, List, Optional
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

# Default typing timeout in seconds
TYPING_TIMEOUT = 2.5


@dataclass
class TypingUser:
    """Represents a user currently typing."""
    user_id: int
    username: str
    started_at: float = field(default_factory=time.time)
    
    def is_expired(self, timeout: float = TYPING_TIMEOUT) -> bool:
        """Check if typing state has expired."""
        return time.time() - self.started_at > timeout


@dataclass
class TypingManager:
    """
    In-memory typing state tracking.
    
    Structure:
    - channel_typing[channel_id] = {user_id: TypingUser}
    - user_channels[user_id] = set(channel_ids)  # for cleanup on disconnect
    """
    # TTL for typing state in seconds
    ttl_seconds: float = TYPING_TIMEOUT
    
    # channel_id -> {user_id -> TypingUser}
    channel_typing: Dict[int, Dict[int, TypingUser]] = field(default_factory=dict)
    
    # user_id -> set of channel_ids where user is typing (for disconnect cleanup)
    user_channels: Dict[int, Set[int]] = field(default_factory=dict)
    
    def start_typing(self, channel_id: int, user_id: int, username: str) -> bool:
        """
        Mark user as typing in a channel.
        
        Returns True if this is a new typing event (should broadcast).
        Returns False if user was already typing (duplicate, refresh timestamp only).
        """
        # Clean expired entries first
        self._cleanup_expired(channel_id)
        
        # Initialize channel dict if needed
        if channel_id not in self.channel_typing:
            self.channel_typing[channel_id] = {}
        
        # Track user -> channels mapping
        if user_id not in self.user_channels:
            self.user_channels[user_id] = set()
        
        was_typing = user_id in self.channel_typing[channel_id]
        
        # Update or create typing state
        self.channel_typing[channel_id][user_id] = TypingUser(
            user_id=user_id,
            username=username,
        )
        self.user_channels[user_id].add(channel_id)
        
        if not was_typing:
            logger.debug(f"User {username} started typing in channel {channel_id}")
        
        return not was_typing
    
    def stop_typing(self, channel_id: int, user_id: int) -> bool:
        """
        Mark user as stopped typing.
        
        Returns True if user was typing (should broadcast stop).
        Returns False if user wasn't typing.
        """
        channel_users = self.channel_typing.get(channel_id, {})
        
        if user_id not in channel_users:
            return False
        
        username = channel_users[user_id].username
        del channel_users[user_id]
        
        # Clean up empty channel dict
        if not channel_users:
            self.channel_typing.pop(channel_id, None)
        
        # Update user -> channels mapping
        if user_id in self.user_channels:
            self.user_channels[user_id].discard(channel_id)
            if not self.user_channels[user_id]:
                del self.user_channels[user_id]
        
        logger.debug(f"User {username} stopped typing in channel {channel_id}")
        return True
    
    def user_disconnected(self, user_id: int) -> List[int]:
        """
        Handle user disconnect - stop typing in all channels.
        
        Returns list of channel_ids where user was typing (for broadcast).
        """
        channels = list(self.user_channels.get(user_id, set()))
        
        for channel_id in channels:
            self.stop_typing(channel_id, user_id)
        
        return channels
    
    def get_typing_users(self, channel_id: int) -> List[Dict]:
        """
        Get list of users currently typing in a channel.
        Returns list of {user_id, username} dicts.
        Automatically cleans expired entries.
        """
        self._cleanup_expired(channel_id)
        
        channel_users = self.channel_typing.get(channel_id, {})
        return [
            {"user_id": u.user_id, "username": u.username}
            for u in channel_users.values()
        ]
    
    def is_user_typing(self, channel_id: int, user_id: int) -> bool:
        """Check if a specific user is typing in a channel."""
        self._cleanup_expired(channel_id)
        return user_id in self.channel_typing.get(channel_id, {})
    
    def _cleanup_expired(self, channel_id: int) -> None:
        """Remove expired typing entries for a channel."""
        if channel_id not in self.channel_typing:
            return
        
        channel_users = self.channel_typing[channel_id]
        expired = [uid for uid, u in channel_users.items() if u.is_expired(self.ttl_seconds)]
        
        for user_id in expired:
            self.stop_typing(channel_id, user_id)
    
    def clear(self) -> None:
        """Clear all typing state (for testing)."""
        self.channel_typing.clear()
        self.user_channels.clear()


# Singleton instance
typing_manager = TypingManager()
