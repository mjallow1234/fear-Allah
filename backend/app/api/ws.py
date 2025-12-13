"""
WebSocket API with real-time messaging, presence, typing indicators, reactions, and file uploads.
"""
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, Query
from typing import Dict, Set, Optional, List
from datetime import datetime
import json
import asyncio
import re

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db.database import async_session
from app.db.models import Message, User, Channel, ChannelMember, MessageReaction, FileAttachment, AuditLog, Notification, NotificationType
from app.db.enums import UserStatus
from app.core.redis import RedisClient
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

router = APIRouter(tags=["WebSocket"])

# Initialize Redis client
redis_client = RedisClient()


class ConnectionManager:
    """Manages WebSocket connections for real-time features."""
    
    def __init__(self):
        # channel_id -> set of (websocket, user_id)
        self.channel_connections: Dict[int, Set[tuple]] = {}
        # user_id -> set of websockets (user can be in multiple channels)
        self.user_connections: Dict[int, Set[WebSocket]] = {}
        # user_id -> user info cache
        self.user_info: Dict[int, dict] = {}
        # Global presence subscribers
        self.presence_subscribers: Set[WebSocket] = set()
    
    async def connect(self, websocket: WebSocket, channel_id: int, user_id: int, username: str = ""):
        """Connect a user to a channel."""
        await websocket.accept()
        
        # Add to channel connections
        if channel_id not in self.channel_connections:
            self.channel_connections[channel_id] = set()
        self.channel_connections[channel_id].add((websocket, user_id))
        
        # Add to user connections
        if user_id not in self.user_connections:
            self.user_connections[user_id] = set()
        self.user_connections[user_id].add(websocket)
        
        # Cache user info
        self.user_info[user_id] = {"username": username, "user_id": user_id}
        
        # Update presence in Redis
        await redis_client.set_user_status(user_id, UserStatus.online.value)
        # Presence set to online logged (no debug prints)
        
        # Broadcast user joined
        await self.broadcast_to_channel(channel_id, {
            "type": "user_joined",
            "channel_id": channel_id,
            "user_id": user_id,
            "username": username,
            "timestamp": datetime.utcnow().isoformat(),
        }, exclude_user=user_id)
        
        # Broadcast presence update
        await self.broadcast_presence({
            "type": "presence_update",
            "user_id": user_id,
            "username": username,
            "status": UserStatus.online.value,
        })
    
    def disconnect(self, websocket: WebSocket, channel_id: int, user_id: int):
        """Disconnect a user from a channel."""
        # Remove from channel connections
        if channel_id in self.channel_connections:
            self.channel_connections[channel_id].discard((websocket, user_id))
            if not self.channel_connections[channel_id]:
                del self.channel_connections[channel_id]
        
        # Remove from user connections
        if user_id in self.user_connections:
            self.user_connections[user_id].discard(websocket)
            if not self.user_connections[user_id]:
                del self.user_connections[user_id]
                # User fully offline
                asyncio.create_task(self._set_user_offline(user_id))
    
    async def _set_user_offline(self, user_id: int):
        """Set user offline in Redis and broadcast."""
        await redis_client.set_user_status(user_id, UserStatus.offline.value)
        # Presence set to offline logged (no debug prints)
        username = self.user_info.get(user_id, {}).get("username", "")
        await self.broadcast_presence({
            "type": "presence_update",
            "user_id": user_id,
            "username": username,
            "status": UserStatus.offline.value,
        })
    
    async def broadcast_to_channel(self, channel_id: int, message: dict, exclude_user: int = None):
        """Broadcast message to all users in a channel."""
        if channel_id not in self.channel_connections:
            return
        
        disconnected = []
        for ws, uid in self.channel_connections[channel_id]:
            if exclude_user and uid == exclude_user:
                continue
            try:
                await ws.send_json(message)
            except Exception:
                disconnected.append((ws, uid))
        
        # Clean up disconnected
        for conn in disconnected:
            self.channel_connections[channel_id].discard(conn)
    
    async def send_to_user(self, user_id: int, message: dict):
        """Send message to specific user."""
        if user_id not in self.user_connections:
            return
        
        for ws in self.user_connections[user_id]:
            try:
                await ws.send_json(message)
            except Exception:
                pass
    
    async def broadcast_presence(self, message: dict):
        """Broadcast presence update to all subscribers."""
        disconnected = []
        for ws in self.presence_subscribers:
            try:
                await ws.send_json(message)
            except Exception:
                disconnected.append(ws)
        
        for ws in disconnected:
            self.presence_subscribers.discard(ws)
    
    def subscribe_presence(self, websocket: WebSocket):
        """Subscribe to presence updates."""
        self.presence_subscribers.add(websocket)
    
    def unsubscribe_presence(self, websocket: WebSocket):
        """Unsubscribe from presence updates."""
        self.presence_subscribers.discard(websocket)
    
    def get_online_users(self) -> list:
        """Get list of online user IDs."""
        return list(self.user_connections.keys())


manager = ConnectionManager()


async def get_db_session():
    """Get async database session."""
    async with async_session() as session:
        yield session


async def save_message(session: AsyncSession, channel_id: int, user_id: int, content: str) -> Message:
    """Save message to database."""
    message = Message(
        content=content,
        channel_id=channel_id,
        author_id=user_id,
    )
    session.add(message)
    await session.commit()
    await session.refresh(message)
    return message


async def log_audit(session: AsyncSession, user_id: int, action: str, target_type: str = None, 
                    target_id: int = None, details: str = None):
    """Log an audit event."""
    audit = AuditLog(
        user_id=user_id,
        action=action,
        target_type=target_type,
        target_id=target_id,
        meta=details,
    )
    session.add(audit)
    await session.commit()


async def extract_mentions(content: str) -> List[str]:
    """Extract @username mentions from message content."""
    # Match @username patterns
    pattern = r'@(\w+)'
    return re.findall(pattern, content)


async def create_mention_notifications(
    session: AsyncSession,
    content: str,
    sender_id: int,
    sender_username: str,
    channel_id: int,
    message_id: int
):
    """Create notifications for mentioned users and send real-time WebSocket notifications."""
    mentions = await extract_mentions(content)
    
    if not mentions:
        return
    
    # Get mentioned users
    for username in mentions:
        result = await session.execute(
            select(User).where(User.username == username)
        )
        user = result.scalar_one_or_none()
        
        if user and user.id != sender_id:
            # Create notification
            notification = Notification(
                user_id=user.id,
                type=NotificationType.mention.value,
                title=f"@{sender_username} mentioned you",
                content=content[:100] + ("..." if len(content) > 100 else ""),
                channel_id=channel_id,
                message_id=message_id,
                sender_id=sender_id
            )
            session.add(notification)
            await session.flush()  # Get the notification ID
            
            # Send real-time WebSocket notification
            await notify_to_user(user.id, {
                "notification_id": notification.id,
                "notification_type": "mention",
                "title": notification.title,
                "content": notification.content,
                "channel_id": channel_id,
                "message_id": message_id,
                "sender_id": sender_id,
                "sender_username": sender_username,
                "created_at": notification.created_at.isoformat() if notification.created_at else None,
            })
    
    await session.commit()


async def notify_to_user(user_id: int, notification_data: dict):
    """Send notification to user via WebSocket if connected."""
    await manager.send_to_user(user_id, {
        "type": "notification",
        **notification_data
    })


@router.websocket("/chat/{channel_id}")
async def websocket_chat(
    websocket: WebSocket,
    channel_id: int,
    token: str = Query(default=""),
):
    """
    WebSocket endpoint for real-time chat.
    
    Event types:
    - message: Send/receive chat messages
    - typing_start: User started typing
    - typing_stop: User stopped typing
    - reaction_add: Add reaction to message
    - reaction_remove: Remove reaction from message
    - file_upload: File was uploaded
    """
    # Validate and decode token to get user identity
    if not token:
        await websocket.close(code=4403)
        return
    try:
        from app.core.security import decode_token
        payload = decode_token(token)
        if not payload:
            await websocket.close(code=4403)
            return
        user_id = int(payload.get('sub', 0))
        username = payload.get('username', '')
    except Exception:
        await websocket.close(code=4403)
        return

    # Verify channel membership before connecting
    try:
        async with async_session() as session:
            from sqlalchemy import select
            result = await session.execute(select(ChannelMember).where(
                ChannelMember.channel_id == channel_id,
                ChannelMember.user_id == user_id
            ))
            member = result.scalar_one_or_none()
            if member is None:
                await websocket.close(code=4403)
                return
    except Exception:
        # On DB errors, deny connect for safety
        await websocket.close(code=4403)
        return

    await manager.connect(websocket, channel_id, user_id, username)
    
    try:
        while True:
            data = await websocket.receive_text()
            event = json.loads(data)
            event_type = event.get("type", "message")
            
            async with async_session() as session:
                if event_type == "message":
                    # Save message to database
                    content = event.get("content", "").strip()
                    if content:
                        msg = await save_message(session, channel_id, user_id, content)
                        
                        # Cache in Redis
                        await redis_client.cache_message(channel_id, {
                            "id": msg.id,
                            "content": content,
                            "user_id": user_id,
                            "username": username,
                            "channel_id": channel_id,
                            "timestamp": msg.created_at.isoformat(),
                        })
                        
                        # Broadcast to channel
                        await manager.broadcast_to_channel(channel_id, {
                            "type": "message",
                            "id": msg.id,
                            "content": content,
                            "user_id": user_id,
                            "username": username,
                            "channel_id": channel_id,
                            "timestamp": msg.created_at.isoformat(),
                            "reactions": [],
                        })
                        
                        # Publish to Redis for cross-pod fanout (best-effort)
                        try:
                            # Ensure lib call happens without blocking the event loop
                            asyncio.create_task(asyncio.to_thread(redis_client.publish_channel_event, channel_id, {
                                "type": "message",
                                "id": msg.id,
                                "content": content,
                                "user_id": user_id,
                                "username": username,
                                "channel_id": channel_id,
                                "timestamp": msg.created_at.isoformat(),
                            }))
                        except Exception:
                            # ignore publish failures (best effort)
                            pass

                        # Create notifications for mentions
                        await create_mention_notifications(
                            session, content, user_id, username, channel_id, msg.id
                        )
                        
                        # Audit log
                        await log_audit(session, user_id, "message_send", "message", msg.id)
                
                elif event_type == "typing_start":
                    # Set typing in Redis
                    await redis_client.set_typing(channel_id, user_id)
                    
                    # Broadcast typing indicator
                    await manager.broadcast_to_channel(channel_id, {
                        "type": "typing_start",
                        "user_id": user_id,
                        "username": username,
                        "channel_id": channel_id,
                    }, exclude_user=user_id)
                
                elif event_type == "typing_stop":
                    # Broadcast typing stop
                    await manager.broadcast_to_channel(channel_id, {
                        "type": "typing_stop",
                        "user_id": user_id,
                        "username": username,
                        "channel_id": channel_id,
                    }, exclude_user=user_id)
                
                elif event_type == "reaction_add":
                    message_id = event.get("message_id")
                    emoji = event.get("emoji", "👍")
                    
                    if message_id:
                        # Check if reaction exists
                        existing = await session.execute(
                            select(MessageReaction).where(
                                MessageReaction.message_id == message_id,
                                MessageReaction.user_id == user_id,
                                MessageReaction.emoji == emoji,
                            )
                        )
                        if not existing.scalar_one_or_none():
                            # Add reaction
                            reaction = MessageReaction(
                                message_id=message_id,
                                user_id=user_id,
                                emoji=emoji,
                            )
                            session.add(reaction)
                            await session.commit()
                            
                            # Broadcast reaction
                            await manager.broadcast_to_channel(channel_id, {
                                "type": "reaction_add",
                                "message_id": message_id,
                                "user_id": user_id,
                                "username": username,
                                "emoji": emoji,
                                "channel_id": channel_id,
                            })
                            
                            # Audit log
                            await log_audit(session, user_id, "reaction_add", "message", message_id,
                                          json.dumps({"emoji": emoji}))
                
                elif event_type == "reaction_remove":
                    message_id = event.get("message_id")
                    emoji = event.get("emoji")
                    
                    if message_id and emoji:
                        # Remove reaction
                        result = await session.execute(
                            select(MessageReaction).where(
                                MessageReaction.message_id == message_id,
                                MessageReaction.user_id == user_id,
                                MessageReaction.emoji == emoji,
                            )
                        )
                        reaction = result.scalar_one_or_none()
                        if reaction:
                            await session.delete(reaction)
                            await session.commit()
                            
                            # Broadcast reaction removal
                            await manager.broadcast_to_channel(channel_id, {
                                "type": "reaction_remove",
                                "message_id": message_id,
                                "user_id": user_id,
                                "username": username,
                                "emoji": emoji,
                                "channel_id": channel_id,
                            })
                            
                            # Audit log
                            await log_audit(session, user_id, "reaction_remove", "message", message_id,
                                          json.dumps({"emoji": emoji}))
    
    except WebSocketDisconnect:
        manager.disconnect(websocket, channel_id, user_id)
        await manager.broadcast_to_channel(channel_id, {
            "type": "user_left",
            "user_id": user_id,
            "username": username,
            "channel_id": channel_id,
            "timestamp": datetime.utcnow().isoformat(),
        })


@router.websocket("/presence")
async def websocket_presence(
    websocket: WebSocket,
    token: str = Query(default=""),
):
    """
    WebSocket endpoint for presence tracking.
    Subscribe to receive online/offline status updates for all users.
    Accepts either token for auth or user_id/username for backwards compatibility.
    """
    await websocket.accept()
    manager.subscribe_presence(websocket)
    
    # Validate and decode token to get user identity
    user_id = 0
    username = ""
    if token:
        try:
            from app.core.security import decode_token
            payload = decode_token(token)
            if payload:
                user_id = int(payload.get("sub", 0))
                username = payload.get("username", "")
        except Exception:
            pass
    
    # Set user online
        if user_id:
            # Add to user connections to track presence
            if user_id not in manager.user_connections:
                manager.user_connections[user_id] = set()
            manager.user_connections[user_id].add(websocket)
            manager.user_info[user_id] = {"username": username, "user_id": user_id}
        
        await redis_client.set_user_status(user_id, UserStatus.online.value)
        await manager.broadcast_presence({
            "type": "presence_update",
            "user_id": user_id,
            "username": username,
            "status": UserStatus.online.value,
        })
    
    # Send current online users with full info
    online_user_list = []
    for uid in manager.get_online_users():
        info = manager.user_info.get(uid, {})
        online_user_list.append({
            "user_id": str(uid),
            "username": info.get("username", f"User {uid}"),
            "status": UserStatus.online.value,
        })
    
    await websocket.send_json({
        "type": "presence_list",
        "users": online_user_list,
    })
    
    try:
        while True:
            data = await websocket.receive_text()
            event = json.loads(data)

            if event.get("type") == "heartbeat":
                # Refresh presence TTL
                if user_id:
                    await redis_client.set_user_status(user_id, UserStatus.online.value)
                    # Heartbeat refreshed presence TTL (no debug prints)
                await websocket.send_json({"type": "heartbeat_ack"})

            elif event.get("type") == "status_update":
                new_status = event.get("status", "online")
                # Validate and normalize status to enum value
                try:
                    status_val = UserStatus(new_status).value
                except Exception:
                    status_val = UserStatus.online.value
                if user_id:
                    await redis_client.set_user_status(user_id, status_val)
                    # Status update logged (no debug prints)
                    await manager.broadcast_presence({
                        "type": "presence_update",
                        "user_id": user_id,
                        "username": username,
                        "status": status_val,
                    })
    
    except WebSocketDisconnect:
        manager.unsubscribe_presence(websocket)
        if user_id:
            # Remove from user connections
            if user_id in manager.user_connections:
                manager.user_connections[user_id].discard(websocket)
                if not manager.user_connections[user_id]:
                    del manager.user_connections[user_id]
                    # User fully offline
                    await redis_client.set_user_status(user_id, UserStatus.offline.value)
                    # Socket disconnect presence offline (no debug prints)
                    await manager.broadcast_presence({
                        "type": "presence_update",
                        "user_id": user_id,
                        "username": username,
                        "status": UserStatus.offline.value,
                    })
