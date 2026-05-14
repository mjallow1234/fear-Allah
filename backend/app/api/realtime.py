"""
Operational Real-Time WebSocket Endpoint

Clients connect to /ws/ops and receive push notifications for:
  ORDER_CREATED, ORDER_UPDATED, SALE_CREATED, SALE_REVERSED

No authentication is required at the transport level (same pattern as the
existing chat /ws endpoint). Add token-based auth here if needed later.
"""
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.core.realtime import ops_manager

router = APIRouter(tags=["Realtime"])


@router.websocket("/ops")
async def ops_websocket(websocket: WebSocket) -> None:
    """Operational events feed. Clients receive broadcast JSON events."""
    await ops_manager.connect(websocket)
    try:
        # Keep connection alive; we only push, clients don't send messages.
        while True:
            # recv_text() will raise WebSocketDisconnect when the client closes.
            await websocket.receive_text()
    except WebSocketDisconnect:
        ops_manager.disconnect(websocket)
    except Exception:
        ops_manager.disconnect(websocket)
