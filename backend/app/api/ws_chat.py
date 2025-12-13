"""Compatibility wrapper for WebSocket chat endpoint.

This exposes a router with the `/ws/chat/{channel_id}` endpoint using the
existing implementations in `app.api.ws` to avoid duplicating logic.
"""
from fastapi import APIRouter
from app.api.ws import websocket_chat

router = APIRouter()

# Re-exported websocket route (path remains /ws/chat/{channel_id} in app.main)
router.websocket("/chat/{channel_id}")(websocket_chat)
