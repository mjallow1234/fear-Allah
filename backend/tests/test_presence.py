"""
Tests for real-time presence tracking.
Phase 4.2 - Online/Offline presence.
"""
import pytest
from app.realtime.presence import PresenceManager


class TestPresenceManager:
    """Test presence tracking logic."""
    
    def setup_method(self):
        """Create fresh PresenceManager for each test."""
        self.pm = PresenceManager()
    
    def test_user_connects_first_time_is_online(self):
        """First connection should mark user as coming online."""
        came_online = self.pm.user_connected(team_id=1, user_id=10, socket_id="sock1")
        
        assert came_online is True
        assert self.pm.is_user_online(team_id=1, user_id=10)
        assert 10 in self.pm.get_online_users(team_id=1)
    
    def test_user_second_tab_does_not_duplicate(self):
        """Second connection from same user should NOT report came_online."""
        # First connection
        first = self.pm.user_connected(team_id=1, user_id=10, socket_id="sock1")
        # Second connection (e.g., another tab)
        second = self.pm.user_connected(team_id=1, user_id=10, socket_id="sock2")
        
        assert first is True  # Came online
        assert second is False  # Already online, just added socket
        assert self.pm.get_socket_count(user_id=10) == 2
        # Still only appears once in online list
        assert self.pm.get_online_users(team_id=1).count(10) == 1
    
    def test_disconnect_one_socket_stays_online(self):
        """Closing one tab (socket) should NOT mark user offline if other sockets remain."""
        self.pm.user_connected(team_id=1, user_id=10, socket_id="sock1")
        self.pm.user_connected(team_id=1, user_id=10, socket_id="sock2")
        
        result = self.pm.user_disconnected(socket_id="sock1")
        
        assert result is not None
        assert result["went_offline"] is False
        assert self.pm.is_user_online(team_id=1, user_id=10)
        assert self.pm.get_socket_count(user_id=10) == 1
    
    def test_disconnect_last_socket_goes_offline(self):
        """Closing last socket should mark user offline."""
        self.pm.user_connected(team_id=1, user_id=10, socket_id="sock1")
        
        result = self.pm.user_disconnected(socket_id="sock1")
        
        assert result is not None
        assert result["went_offline"] is True
        assert result["user_id"] == 10
        assert result["team_id"] == 1
        assert not self.pm.is_user_online(team_id=1, user_id=10)
        assert 10 not in self.pm.get_online_users(team_id=1)
    
    def test_disconnect_unknown_socket_returns_none(self):
        """Disconnecting unknown socket should return None."""
        result = self.pm.user_disconnected(socket_id="unknown")
        assert result is None
    
    def test_multiple_users_same_team(self):
        """Multiple users in same team should all be tracked."""
        self.pm.user_connected(team_id=1, user_id=10, socket_id="sock10")
        self.pm.user_connected(team_id=1, user_id=20, socket_id="sock20")
        self.pm.user_connected(team_id=1, user_id=30, socket_id="sock30")
        
        online = self.pm.get_online_users(team_id=1)
        assert len(online) == 3
        assert 10 in online
        assert 20 in online
        assert 30 in online
    
    def test_presence_list_accurate_after_changes(self):
        """Online list should accurately reflect current state."""
        # Add users
        self.pm.user_connected(team_id=1, user_id=10, socket_id="sock10")
        self.pm.user_connected(team_id=1, user_id=20, socket_id="sock20")
        
        assert len(self.pm.get_online_users(team_id=1)) == 2
        
        # One goes offline
        self.pm.user_disconnected(socket_id="sock10")
        
        online = self.pm.get_online_users(team_id=1)
        assert len(online) == 1
        assert 20 in online
        assert 10 not in online
    
    def test_different_teams_isolated(self):
        """Presence in different teams should be isolated."""
        self.pm.user_connected(team_id=1, user_id=10, socket_id="sock10")
        self.pm.user_connected(team_id=2, user_id=20, socket_id="sock20")
        
        team1_online = self.pm.get_online_users(team_id=1)
        team2_online = self.pm.get_online_users(team_id=2)
        
        assert team1_online == [10]
        assert team2_online == [20]
    
    def test_clear_resets_all_state(self):
        """Clear should reset all presence data."""
        self.pm.user_connected(team_id=1, user_id=10, socket_id="sock10")
        self.pm.user_connected(team_id=2, user_id=20, socket_id="sock20")
        
        self.pm.clear()
        
        assert self.pm.get_online_users(team_id=1) == []
        assert self.pm.get_online_users(team_id=2) == []
        assert self.pm.get_socket_count(user_id=10) == 0
