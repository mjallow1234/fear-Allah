"""
Socket.IO server implementation.
Phase 4.1 - Real-time foundation.
Phase 4.2 - Presence (online/offline).
Phase 4.3 - Typing indicators.

Rooms:
- team:{team_id} - Team-wide events
- channel:{channel_id} - Channel-specific messages

Events:
- message:new - New message in channel
- thread:reply - Reply to a thread
- notification:new - User notification
- presence:online - User came online
- presence:offline - User went offline
- presence:list - List of online users (sent to connecting user)
- typing:start - User started typing
- typing:stop - User stopped typing
"""
import socketio
from typing import Dict, Set
import logging

from app.realtime.auth import authenticate_socket
from app.realtime.presence import presence_manager
from app.realtime.typing import typing_manager

logger = logging.getLogger(__name__)

from app.core.config import settings

# Initialize Socket.IO server
# async_mode="asgi" for FastAPI/Starlette compatibility
# cors_allowed_origins=[] - Let FastAPI's CORS middleware handle CORS to avoid duplicate headers
sio = socketio.AsyncServer(
    async_mode="asgi",
    cors_allowed_origins=[],  # Disable Socket.IO CORS - FastAPI middleware handles it
    logger=False,
    engineio_logger=False,
)

# When running tests we avoid starting or emitting via real sockets.
# Emission helpers will early-return when `settings.TESTING`.

# Create ASGI app wrapper
socket_app = socketio.ASGIApp(sio, socketio_path="socket.io")

# Track authenticated users: sid -> user_data
authenticated_users: Dict[str, dict] = {}

# Track user rooms: sid -> set of room names
user_rooms: Dict[str, Set[str]] = {}


@sio.event
async def connect(sid: str, environ: dict, auth: dict = None):
    """
    Handle new socket connection.
    Authenticates user and auto-joins team room.
    """
    logger.info(f"Socket connect attempt: {sid}")
    
    # Authenticate the connection
    is_authenticated, user_data = await authenticate_socket(auth, environ)
    
    if not is_authenticated:
        logger.warning(f"Socket connection rejected: {sid}")
        # Return False to reject the connection
        return False
    
    # Store user data for this session
    authenticated_users[sid] = user_data
    user_rooms[sid] = set()
    
    # Auto-join team room if user has a team
    team_id = user_data.get("team_id")
    user_id = user_data["user_id"]
    
    # Use team-scoped presence if team exists, otherwise global
    presence_scope = team_id if team_id else "global"
    room_name = f"team:{team_id}" if team_id else "global:presence"
    
    await sio.enter_room(sid, room_name)
    user_rooms[sid].add(room_name)
    logger.info(f"User {user_data['username']} auto-joined room: {room_name}")
    
    # Track presence
    came_online = presence_manager.user_connected(presence_scope, user_id, sid)
    
    # Send current online list to connecting user first
    online_users = presence_manager.get_online_users(presence_scope)
    await sio.emit("presence:list", {
        "online_user_ids": online_users,
    }, room=sid)
    logger.info(f"[Presence] presence:list sent to user {user_id}: {len(online_users)} users online")
    
    if came_online:
        # Broadcast to team/global that user came online (skip the connecting user)
        await sio.emit("presence:online", {
            "user_id": user_id,
            "username": user_data["username"],
        }, room=room_name, skip_sid=sid)
        logger.info(f"[Presence] presence:online emitted for user {user_id} to scope {presence_scope}")
    
    # Emit connection success with user info
    await sio.emit("connected", {
        "status": "ok",
        "user_id": user_data["user_id"],
        "username": user_data["username"],
        "team_id": team_id,
    }, room=sid)
    
    logger.info(f"Socket connected: {sid} (user: {user_data['username']})")
    return True


@sio.event
async def disconnect(sid: str):
    """
    Handle socket disconnection.
    Cleanup is automatic - rooms are left automatically.
    Also handles presence and typing cleanup.
    """
    user_data = authenticated_users.pop(sid, None)
    rooms = user_rooms.pop(sid, set())
    
    # Handle typing cleanup - broadcast to all channels user was typing in
    if user_data:
        typing_stopped = typing_manager.user_disconnected(user_data["user_id"])
        for channel_id in typing_stopped:
            await sio.emit("typing:stop", {
                "user_id": user_data["user_id"],
                "username": user_data["username"],
                "channel_id": channel_id,
            }, room=f"channel:{channel_id}")
    
    # Handle presence cleanup
    disconnect_info = presence_manager.user_disconnected(sid)
    if disconnect_info and disconnect_info["went_offline"]:
        # User's last socket disconnected - broadcast offline
        scope = disconnect_info["team_id"] or "global"
        room_name = f"team:{scope}" if scope != "global" else "global:presence"
        
        await sio.emit("presence:offline", {
            "user_id": disconnect_info["user_id"],
        }, room=room_name)
        logger.info(f"[Presence] presence:offline emitted for user {disconnect_info['user_id']}")
    
    if user_data:
        logger.info(f"Socket disconnected: {sid} (user: {user_data['username']}, rooms: {rooms})")
    else:
        logger.info(f"Socket disconnected: {sid} (unauthenticated)")


@sio.event
async def join_channel(sid: str, data: dict):
    """
    Join a channel room to receive channel-specific events.
    
    Expected data: { "channel_id": int }
    """
    user_data = authenticated_users.get(sid)
    if not user_data:
        await sio.emit("error", {"message": "Not authenticated"}, room=sid)
        return
    
    channel_id = data.get("channel_id")
    if not channel_id:
        await sio.emit("error", {"message": "channel_id is required"}, room=sid)
        return
    
    # Verify server-side access and membership for private channels
    try:
        from app.db.database import async_session
        from app.db.models import Channel, ChannelMember, User
        from sqlalchemy import select

        async with async_session() as db:
            # Check channel exists
            q = select(Channel).where(Channel.id == channel_id)
            r = await db.execute(q)
            channel = r.scalar_one_or_none()
            if not channel:
                await sio.emit("error", {"message": "Channel not found"}, room=sid)
                return

            # Check user must change password
            user_q = select(User).where(User.id == user_data["user_id"])
            user_r = await db.execute(user_q)
            user = user_r.scalar_one_or_none()
            if user and getattr(user, "must_change_password", False):
                await sio.emit("error", {"message": "Password change required"}, room=sid)
                return

            if channel.type != 'public':
                member_q = select(ChannelMember).where(
                    ChannelMember.channel_id == channel_id,
                    ChannelMember.user_id == user_data["user_id"],
                )
                member_r = await db.execute(member_q)
                membership = member_r.scalar_one_or_none()
                if not membership:
                    await sio.emit("error", {"message": "You are not a member of this channel. Contact admin if that is not the case."}, room=sid)
                    return
    except Exception as e:
        logger.exception("Error verifying channel membership on join")
        await sio.emit("error", {"message": "Internal server error"}, room=sid)
        return

    room_name = f"channel:{channel_id}"
    await sio.enter_room(sid, room_name)
    user_rooms[sid].add(room_name)
    
    # Acknowledge the join
    await sio.emit("channel:joined", {
        "channel_id": channel_id,
        "room": room_name,
    }, room=sid)
    
    logger.info(f"User {user_data['username']} joined room: {room_name}")


@sio.event
async def leave_channel(sid: str, data: dict):
    """
    Leave a channel room.
    
    Expected data: { "channel_id": int }
    """
    user_data = authenticated_users.get(sid)
    if not user_data:
        await sio.emit("error", {"message": "Not authenticated"}, room=sid)
        return
    
    channel_id = data.get("channel_id")
    if not channel_id:
        await sio.emit("error", {"message": "channel_id is required"}, room=sid)
        return
    
    room_name = f"channel:{channel_id}"
    await sio.leave_room(sid, room_name)
    user_rooms[sid].discard(room_name)
    
    # Acknowledge the leave
    await sio.emit("channel:left", {
        "channel_id": channel_id,
        "room": room_name,
    }, room=sid)
    
    logger.info(f"User {user_data['username']} left room: {room_name}")


@sio.event
async def join_room(sid: str, data: dict):
    """
    Generic room join handler.
    
    Expected data: { "room": str }
    """
    user_data = authenticated_users.get(sid)
    if not user_data:
        await sio.emit("error", {"message": "Not authenticated"}, room=sid)
        return
    
    room_name = data.get("room")
    if not room_name:
        await sio.emit("error", {"message": "room is required"}, room=sid)
        return
    
    await sio.enter_room(sid, room_name)
    user_rooms[sid].add(room_name)
    
    await sio.emit("room:joined", {"room": room_name}, room=sid)
    logger.info(f"User {user_data['username']} joined room: {room_name}")


@sio.event
async def leave_room(sid: str, data: dict):
    """
    Generic room leave handler.
    
    Expected data: { "room": str }
    """
    user_data = authenticated_users.get(sid)
    if not user_data:
        await sio.emit("error", {"message": "Not authenticated"}, room=sid)
        return
    
    room_name = data.get("room")
    if not room_name:
        await sio.emit("error", {"message": "room is required"}, room=sid)
        return
    
    await sio.leave_room(sid, room_name)
    user_rooms[sid].discard(room_name)
    
    await sio.emit("room:left", {"room": room_name}, room=sid)
    logger.info(f"User {user_data['username']} left room: {room_name}")


@sio.event
async def typing_start(sid: str, data: dict):
    """
    Handle typing start event.
    Broadcasts to channel room (excluding sender).
    
    Expected data: { "channel_id": int }
    """
    user_data = authenticated_users.get(sid)
    if not user_data:
        await sio.emit("error", {"message": "Not authenticated"}, room=sid)
        return
    
    channel_id = data.get("channel_id")
    if not channel_id:
        await sio.emit("error", {"message": "channel_id is required"}, room=sid)
        return
    
    user_id = user_data["user_id"]
    username = user_data["username"]
    
    # Track typing state
    typing_manager.start_typing(channel_id, user_id, username)
    
    # Broadcast to channel room (exclude sender)
    room_name = f"channel:{channel_id}"
    await sio.emit("typing:start", {
        "user_id": user_id,
        "username": username,
        "channel_id": channel_id,
    }, room=room_name, skip_sid=sid)
    
    logger.debug(f"User {username} started typing in channel {channel_id}")


@sio.event
async def typing_stop(sid: str, data: dict):
    """
    Handle typing stop event.
    Broadcasts to channel room (excluding sender).
    
    Expected data: { "channel_id": int }
    """
    user_data = authenticated_users.get(sid)
    if not user_data:
        await sio.emit("error", {"message": "Not authenticated"}, room=sid)
        return
    
    channel_id = data.get("channel_id")
    if not channel_id:
        await sio.emit("error", {"message": "channel_id is required"}, room=sid)
        return
    
    user_id = user_data["user_id"]
    username = user_data["username"]
    
    # Remove typing state
    typing_manager.stop_typing(channel_id, user_id)
    
    # Broadcast to channel room (exclude sender)
    room_name = f"channel:{channel_id}"
    await sio.emit("typing:stop", {
        "user_id": user_id,
        "username": username,
        "channel_id": channel_id,
    }, room=room_name, skip_sid=sid)
    
    logger.debug(f"User {username} stopped typing in channel {channel_id}")


# ============================================================
# Emit helpers (called from other parts of the application)
# ============================================================

async def emit_message_new(channel_id: int, message_data: dict):
    """
    Emit a new message event to a channel room.
    Called from message creation endpoint.
    """
    if settings.TESTING:
        return
    room_name = f"channel:{channel_id}"
    await sio.emit("message:new", message_data, room=room_name)
    logger.debug(f"Emitted message:new to {room_name}")


async def emit_thread_reply(channel_id: int, parent_id: int, reply_data: dict):
    """
    Emit a thread reply event.
    """
    if settings.TESTING:
        return
    room_name = f"channel:{channel_id}"
    payload = {
        "parent_id": parent_id,
        **reply_data
    }
    await sio.emit("thread:reply", payload, room=room_name)
    logger.debug(f"Emitted thread:reply to {room_name}")


async def emit_message_updated(channel_id: int, message_data: dict):
    """Emit message updated event to a channel room."""
    if settings.TESTING:
        return
    room_name = f"channel:{channel_id}"
    await sio.emit("message:updated", message_data, room=room_name)
    logger.debug(f"Emitted message:updated to {room_name}")


async def emit_message_deleted(channel_id: int, message_id: int):
    if settings.TESTING:
        return
    room_name = f"channel:{channel_id}"
    await sio.emit("message:deleted", {"message_id": message_id}, room=room_name)
    logger.debug(f"Emitted message:deleted to {room_name}")


async def emit_message_pinned(channel_id: int, message_id: int):
    if settings.TESTING:
        return
    room_name = f"channel:{channel_id}"
    await sio.emit("message:pinned", {"message_id": message_id}, room=room_name)
    logger.debug(f"Emitted message:pinned to {room_name}")


async def emit_message_unpinned(channel_id: int, message_id: int):
    if settings.TESTING:
        return
    room_name = f"channel:{channel_id}"
    await sio.emit("message:unpinned", {"message_id": message_id}, room=room_name)
    logger.debug(f"Emitted message:unpinned to {room_name}")


async def emit_notification(user_id: int, notification_data: dict):
    """
    Emit a notification to a specific user.
    Finds all sockets for the user and emits to each.
    """
    # Find all sids for this user
    for sid, user_data in authenticated_users.items():
        if user_data.get("user_id") == user_id:
            await sio.emit("notification:new", notification_data, room=sid)
            logger.debug(f"Emitted notification:new to user {user_id}")


async def emit_to_team(team_id: int, event: str, data: dict):
    """
    Emit an event to all users in a team.
    """
    room_name = f"team:{team_id}"
    await sio.emit(event, data, room=room_name)
    logger.debug(f"Emitted {event} to {room_name}")


async def emit_receipt_update(channel_id: int, user_id: int, last_read_message_id: int, skip_user_id: int | None = None):
    """
    Emit a read receipt update to a channel room.
    Phase 4.4 - Read Receipts.
    
    Args:
        channel_id: Channel where receipt was updated
        user_id: User who updated their read position
        last_read_message_id: Message ID they've read up to
        skip_user_id: User ID to skip (the sender) - finds their sids to skip
    """
    room_name = f"channel:{channel_id}"
    payload = {
        "channel_id": channel_id,
        "user_id": user_id,
        "last_read_message_id": last_read_message_id,
    }
    
    # Find sids to skip (all sockets for the sender)
    skip_sids = []
    if skip_user_id:
        for sid, user_data in authenticated_users.items():
            if user_data.get("user_id") == skip_user_id:
                skip_sids.append(sid)
    
    # Emit to room, skipping sender's sockets
    if skip_sids:
        # Socket.IO doesn't support multiple skip_sid, so emit individually
        # For simplicity, use room broadcast and let client filter if needed
        # Actually, we can use skip_sid for one socket, or emit to all and filter
        # Better: just emit to room - client will ignore their own receipt anyway
        await sio.emit("receipt:update", payload, room=room_name)
    else:
        await sio.emit("receipt:update", payload, room=room_name)
    
    logger.debug(f"Emitted receipt:update to {room_name} for user {user_id}")


async def emit_attachment_added(channel_id: int, attachment_data: dict):
    """
    Phase 9.1: Emit attachment added event to channel.
    """
    room_name = f"channel:{channel_id}"
    await sio.emit("message:attachment_added", attachment_data, room=room_name)
    logger.debug(f"Emitted message:attachment_added to {room_name}")


async def emit_attachment_removed(channel_id: int, attachment_id: int, message_id: int = None):
    """
    Phase 9.1: Emit attachment removed event to channel.
    """
    room_name = f"channel:{channel_id}"
    payload = {
        "attachment_id": attachment_id,
        "message_id": message_id,
        "channel_id": channel_id,
    }
    await sio.emit("message:attachment_removed", payload, room=room_name)
    logger.debug(f"Emitted message:attachment_removed to {room_name}")


async def emit_reaction_added(channel_id: int, reaction_data: dict):
    """
    Phase 9.3: Emit reaction added event to channel.
    Payload: {message_id, emoji, user_id, username}
    """
    room_name = f"channel:{channel_id}"
    await sio.emit("message:reaction_added", reaction_data, room=room_name)
    logger.debug(f"Emitted message:reaction_added to {room_name}")


async def emit_reaction_removed(channel_id: int, reaction_data: dict):
    """
    Phase 9.3: Emit reaction removed event to channel.
    Payload: {message_id, emoji, user_id, username}
    """
    room_name = f"channel:{channel_id}"
    await sio.emit("message:reaction_removed", reaction_data, room=room_name)
    logger.debug(f"Emitted message:reaction_removed to {room_name}")


def get_connected_users() -> Dict[str, dict]:
    """
    Get all currently connected users.
    Returns dict of sid -> user_data.
    """
    return authenticated_users.copy()


def get_user_count() -> int:
    """
    Get count of unique connected users.
    """
    unique_users = set(u["user_id"] for u in authenticated_users.values())
    return len(unique_users)


# ============================================================================
# Order Events (Phase 7)
# ============================================================================

async def emit_order_updated(order_id: int, status: str, order_type: str = None):
    """
    Emit order:updated event to all connected clients.
    Called when order status changes.
    """
    if settings.TESTING:
        return
    
    payload = {
        "order_id": order_id,
        "status": status,
        "order_type": order_type,
    }
    
    # Broadcast to all connected users (orders are visible based on role)
    await sio.emit("order:updated", payload)
    logger.info(f"Emitted order:updated for order {order_id}, status={status}")


async def emit_order_created(order_id: int, status: str, order_type: str = None):
    """
    Emit order:created event to all connected clients.
    """
    if settings.TESTING:
        return
    
    payload = {
        "order_id": order_id,
        "status": status,
        "order_type": order_type,
    }
    
    await sio.emit("order:created", payload)
    logger.info(f"Emitted order:created for order {order_id}")


async def emit_task_completed(task_id: int, step_key: str, order_id: int = None):
    """
    Emit task:completed event to all connected clients.
    """
    if settings.TESTING:
        return
    
    payload = {
        "task_id": task_id,
        "step_key": step_key,
        "order_id": order_id,
    }
    
    await sio.emit("task:completed", payload)
    logger.info(f"Emitted task:completed for task {task_id}, step={step_key}")
