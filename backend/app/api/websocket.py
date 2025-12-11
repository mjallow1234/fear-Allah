from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends
from typing import Dict, Set
import json

router = APIRouter()


class ConnectionManager:
    def __init__(self):
        # channel_id -> set of websockets
        self.active_connections: Dict[int, Set[WebSocket]] = {}
        # user_id -> websocket
        self.user_connections: Dict[int, WebSocket] = {}
    
    async def connect(self, websocket: WebSocket, channel_id: int, user_id: int):
        await websocket.accept()
        if channel_id not in self.active_connections:
            self.active_connections[channel_id] = set()
        self.active_connections[channel_id].add(websocket)
        self.user_connections[user_id] = websocket
    
    def disconnect(self, websocket: WebSocket, channel_id: int, user_id: int):
        if channel_id in self.active_connections:
            self.active_connections[channel_id].discard(websocket)
        if user_id in self.user_connections:
            del self.user_connections[user_id]
    
    async def broadcast_to_channel(self, channel_id: int, message: dict):
        if channel_id in self.active_connections:
            for connection in self.active_connections[channel_id]:
                try:
                    await connection.send_json(message)
                except Exception:
                    pass
    
    async def send_to_user(self, user_id: int, message: dict):
        if user_id in self.user_connections:
            try:
                await self.user_connections[user_id].send_json(message)
            except Exception:
                pass


manager = ConnectionManager()


@router.websocket("/chat/{channel_id}")
async def websocket_endpoint(
    websocket: WebSocket,
    channel_id: int,
    user_id: int = 0,  # Should be extracted from token in production
):
    await manager.connect(websocket, channel_id, user_id)
    try:
        while True:
            data = await websocket.receive_text()
            message_data = json.loads(data)
            
            # Broadcast message to all users in channel
            await manager.broadcast_to_channel(channel_id, {
                "type": "message",
                "channel_id": channel_id,
                "user_id": user_id,
                "content": message_data.get("content", ""),
                "timestamp": message_data.get("timestamp"),
            })
    except WebSocketDisconnect:
        manager.disconnect(websocket, channel_id, user_id)
        await manager.broadcast_to_channel(channel_id, {
            "type": "user_left",
            "channel_id": channel_id,
            "user_id": user_id,
        })


@router.websocket("/presence")
async def presence_endpoint(
    websocket: WebSocket,
    user_id: int = 0,
):
    await websocket.accept()
    try:
        while True:
            data = await websocket.receive_text()
            message_data = json.loads(data)
            
            # Handle presence updates
            if message_data.get("type") == "status_update":
                # Broadcast to relevant users
                pass
            elif message_data.get("type") == "typing":
                # Broadcast typing indicator
                pass
    except WebSocketDisconnect:
        pass
