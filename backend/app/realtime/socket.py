"""
Socket.IO server implementation.
Phase 4.1 - Real-time foundation.

Rooms:
- team:{team_id} - Team-wide events
- channel:{channel_id} - Channel-specific messages

Events:
- message:new - New message in channel
- thread:reply - Reply to a thread
- notification:new - User notification
"""
import socketio
from typing import Dict, Set
import logging

from app.realtime.auth import authenticate_socket

logger = logging.getLogger(__name__)

# Initialize Socket.IO server
# async_mode="asgi" for FastAPI/Starlette compatibility
# cors_allowed_origins="*" for development - restrict in production
sio = socketio.AsyncServer(
    async_mode="asgi",
    cors_allowed_origins="*",
    logger=False,
    engineio_logger=False,
)

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
    if team_id:
        team_room = f"team:{team_id}"
        await sio.enter_room(sid, team_room)
        user_rooms[sid].add(team_room)
        logger.info(f"User {user_data['username']} auto-joined room: {team_room}")
    
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
    """
    user_data = authenticated_users.pop(sid, None)
    rooms = user_rooms.pop(sid, set())
    
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


# ============================================================
# Emit helpers (called from other parts of the application)
# ============================================================

async def emit_message_new(channel_id: int, message_data: dict):
    """
    Emit a new message event to a channel room.
    Called from message creation endpoint.
    """
    room_name = f"channel:{channel_id}"
    await sio.emit("message:new", message_data, room=room_name)
    logger.debug(f"Emitted message:new to {room_name}")


async def emit_thread_reply(channel_id: int, parent_id: int, reply_data: dict):
    """
    Emit a thread reply event.
    """
    room_name = f"channel:{channel_id}"
    payload = {
        "parent_id": parent_id,
        **reply_data
    }
    await sio.emit("thread:reply", payload, room=room_name)
    logger.debug(f"Emitted thread:reply to {room_name}")


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
