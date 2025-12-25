"""
Tests for Phase 4.3 - Typing indicator functionality.
"""
import pytest
import time
from app.realtime.typing import TypingManager, TypingUser


class TestTypingManager:
    """Tests for TypingManager class."""
    
    def setup_method(self):
        """Create a fresh TypingManager for each test."""
        self.manager = TypingManager(ttl_seconds=0.1)  # Short TTL for tests
    
    def test_start_typing_tracks_user(self):
        """Starting typing should track user in channel."""
        self.manager.start_typing(channel_id=1, user_id=100, username="alice")
        
        users = self.manager.get_typing_users(channel_id=1)
        assert len(users) == 1
        assert users[0]["user_id"] == 100
        assert users[0]["username"] == "alice"
    
    def test_multiple_users_typing(self):
        """Multiple users can type in same channel."""
        self.manager.start_typing(channel_id=1, user_id=100, username="alice")
        self.manager.start_typing(channel_id=1, user_id=101, username="bob")
        
        users = self.manager.get_typing_users(channel_id=1)
        assert len(users) == 2
        user_ids = {u["user_id"] for u in users}
        assert user_ids == {100, 101}
    
    def test_typing_in_different_channels(self):
        """Users typing in different channels are tracked separately."""
        self.manager.start_typing(channel_id=1, user_id=100, username="alice")
        self.manager.start_typing(channel_id=2, user_id=101, username="bob")
        
        channel1_users = self.manager.get_typing_users(channel_id=1)
        channel2_users = self.manager.get_typing_users(channel_id=2)
        
        assert len(channel1_users) == 1
        assert channel1_users[0]["username"] == "alice"
        assert len(channel2_users) == 1
        assert channel2_users[0]["username"] == "bob"
    
    def test_stop_typing_removes_user(self):
        """Stopping typing should remove user from channel."""
        self.manager.start_typing(channel_id=1, user_id=100, username="alice")
        self.manager.stop_typing(channel_id=1, user_id=100)
        
        users = self.manager.get_typing_users(channel_id=1)
        assert len(users) == 0
    
    def test_stop_typing_nonexistent_user(self):
        """Stopping typing for non-typing user should not error."""
        # Should not raise
        self.manager.stop_typing(channel_id=1, user_id=100)
        
        users = self.manager.get_typing_users(channel_id=1)
        assert len(users) == 0
    
    def test_user_disconnected_clears_all_channels(self):
        """Disconnecting user should clear from all channels."""
        self.manager.start_typing(channel_id=1, user_id=100, username="alice")
        self.manager.start_typing(channel_id=2, user_id=100, username="alice")
        self.manager.start_typing(channel_id=3, user_id=100, username="alice")
        
        affected_channels = self.manager.user_disconnected(user_id=100)
        
        assert set(affected_channels) == {1, 2, 3}
        assert len(self.manager.get_typing_users(channel_id=1)) == 0
        assert len(self.manager.get_typing_users(channel_id=2)) == 0
        assert len(self.manager.get_typing_users(channel_id=3)) == 0
    
    def test_user_disconnected_preserves_other_users(self):
        """Disconnecting one user should not affect others."""
        self.manager.start_typing(channel_id=1, user_id=100, username="alice")
        self.manager.start_typing(channel_id=1, user_id=101, username="bob")
        
        self.manager.user_disconnected(user_id=100)
        
        users = self.manager.get_typing_users(channel_id=1)
        assert len(users) == 1
        assert users[0]["username"] == "bob"
    
    def test_typing_expires_after_ttl(self):
        """Typing should expire after TTL."""
        self.manager.start_typing(channel_id=1, user_id=100, username="alice")
        
        # Immediately, user should be typing
        users = self.manager.get_typing_users(channel_id=1)
        assert len(users) == 1
        
        # Wait for TTL to expire
        time.sleep(0.15)
        
        # Now user should not be typing
        users = self.manager.get_typing_users(channel_id=1)
        assert len(users) == 0
    
    def test_typing_refresh_extends_ttl(self):
        """Calling start_typing again should refresh TTL."""
        self.manager.start_typing(channel_id=1, user_id=100, username="alice")
        
        # Wait half the TTL
        time.sleep(0.05)
        
        # Refresh typing
        self.manager.start_typing(channel_id=1, user_id=100, username="alice")
        
        # Wait another half TTL - should still be typing
        time.sleep(0.05)
        users = self.manager.get_typing_users(channel_id=1)
        assert len(users) == 1
        
        # Wait full TTL - now should expire
        time.sleep(0.15)
        users = self.manager.get_typing_users(channel_id=1)
        assert len(users) == 0
    
    def test_get_typing_users_empty_channel(self):
        """Getting typing users for empty channel returns empty list."""
        users = self.manager.get_typing_users(channel_id=999)
        assert users == []
    
    def test_same_user_multiple_channels(self):
        """Same user can type in multiple channels simultaneously."""
        self.manager.start_typing(channel_id=1, user_id=100, username="alice")
        self.manager.start_typing(channel_id=2, user_id=100, username="alice")
        
        channel1_users = self.manager.get_typing_users(channel_id=1)
        channel2_users = self.manager.get_typing_users(channel_id=2)
        
        assert len(channel1_users) == 1
        assert len(channel2_users) == 1
        assert channel1_users[0]["user_id"] == 100
        assert channel2_users[0]["user_id"] == 100
