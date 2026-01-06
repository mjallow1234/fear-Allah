"""
Real-time presence tracking for team members.
Phase 4.2 - Online/Offline status only.

Tracks which users are online per team, supporting multiple
browser tabs/devices per user (multiple socket IDs).
"""
import logging
from typing import Dict, Set, List, Optional
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class PresenceManager:
    """
    In-memory presence tracking.
    
    Structure:
    - team_presence[team_id][user_id] = set(socket_ids)
    - user_team_map[user_id] = team_id (for quick lookup on disconnect)
    - socket_user_map[socket_id] = user_id (for cleanup on disconnect)
    """
    # team_id -> {user_id -> set(socket_ids)}
    team_presence: Dict[int, Dict[int, Set[str]]] = field(default_factory=dict)
    
    # user_id -> team_id (quick lookup)
    user_team_map: Dict[int, int] = field(default_factory=dict)
    
    # socket_id -> user_id (for disconnect cleanup)
    socket_user_map: Dict[str, int] = field(default_factory=dict)
    
    def user_connected(self, team_id: int, user_id: int, socket_id: str) -> bool:
        """
        Register a user connection.
        
        Returns True if this is the user's first socket (they came online).
        Returns False if user already had other sockets (additional tab).
        """
        # Track socket -> user mapping
        self.socket_user_map[socket_id] = user_id
        self.user_team_map[user_id] = team_id
        
        # Initialize team if needed
        if team_id not in self.team_presence:
            self.team_presence[team_id] = {}
        
        team_users = self.team_presence[team_id]
        
        # Check if user was already online
        was_offline = user_id not in team_users or len(team_users.get(user_id, set())) == 0
        
        # Add socket to user's set
        if user_id not in team_users:
            team_users[user_id] = set()
        team_users[user_id].add(socket_id)
        
        if was_offline:
            logger.info(f"User {user_id} came online in team {team_id} (socket: {socket_id})")
        else:
            logger.debug(f"User {user_id} added socket {socket_id} (now {len(team_users[user_id])} connections)")
        
        return was_offline
    
    def user_disconnected(self, socket_id: str) -> Optional[Dict]:
        """
        Handle socket disconnect.
        
        Returns dict with {team_id, user_id, went_offline: bool} if socket was tracked.
        Returns None if socket wasn't tracked.
        """
        if socket_id not in self.socket_user_map:
            return None
        
        user_id = self.socket_user_map.pop(socket_id)
        team_id = self.user_team_map.get(user_id)
        
        if team_id is None:
            return None
        
        team_users = self.team_presence.get(team_id, {})
        
        if user_id in team_users:
            team_users[user_id].discard(socket_id)
            
            # Check if user went offline (no more sockets)
            went_offline = len(team_users[user_id]) == 0
            
            if went_offline:
                # Clean up empty user entry
                del team_users[user_id]
                # Clean up user -> team mapping
                self.user_team_map.pop(user_id, None)
                logger.info(f"User {user_id} went offline in team {team_id}")
            else:
                logger.debug(f"User {user_id} closed socket {socket_id} ({len(team_users[user_id])} remaining)")
            
            return {
                "team_id": team_id,
                "user_id": user_id,
                "went_offline": went_offline
            }
        
        return None
    
    def get_online_users(self, team_id: int) -> List[int]:
        """Get list of online user IDs for a team."""
        team_users = self.team_presence.get(team_id, {})
        return [uid for uid, sockets in team_users.items() if len(sockets) > 0]
    
    def is_user_online(self, team_id: int, user_id: int) -> bool:
        """Check if a specific user is online in a team."""
        team_users = self.team_presence.get(team_id, {})
        return user_id in team_users and len(team_users[user_id]) > 0
    
    def get_socket_count(self, user_id: int) -> int:
        """Get number of active sockets for a user."""
        team_id = self.user_team_map.get(user_id)
        if team_id is None:
            return 0
        team_users = self.team_presence.get(team_id, {})
        return len(team_users.get(user_id, set()))
    
    def clear(self):
        """Clear all presence data (for testing)."""
        self.team_presence.clear()
        self.user_team_map.clear()
        self.socket_user_map.clear()


# Singleton instance
presence_manager = PresenceManager()
