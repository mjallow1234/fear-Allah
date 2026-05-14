"""
Operational Real-Time Manager

Broadcasts domain events (order created/updated, sale created/reversed) to
all connected WebSocket clients at /ws/ops.

Design:
- Single shared `ops_manager` instance (module-level singleton).
- Connections are unauthenticated at the transport level; callers may add
  auth at the HTTP-upgrade step if needed.
- broadcast() is fire-and-forget: failures per client are caught silently so
  one bad connection never blocks others.
"""
import asyncio
import json
import logging
from typing import Any, Dict, Set

from fastapi import WebSocket

logger = logging.getLogger(__name__)


class OpsConnectionManager:
    """Manages WebSocket connections for operational real-time events."""

    def __init__(self) -> None:
        self._connections: Set[WebSocket] = set()

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self._connections.add(websocket)
        logger.info("[realtime] client connected (total=%d)", len(self._connections))

    def disconnect(self, websocket: WebSocket) -> None:
        self._connections.discard(websocket)
        logger.info("[realtime] client disconnected (total=%d)", len(self._connections))

    async def broadcast(self, event: Dict[str, Any]) -> None:
        """Fire-and-forget broadcast to all connected clients.

        Broken/slow clients are removed; errors do not propagate to callers.
        """
        if not self._connections:
            return

        message = json.dumps(event)
        dead: Set[WebSocket] = set()

        for ws in list(self._connections):
            try:
                await ws.send_text(message)
            except Exception:
                dead.add(ws)

        for ws in dead:
            self._connections.discard(ws)

        if dead:
            logger.debug("[realtime] removed %d dead connection(s)", len(dead))


# Module-level singleton — imported everywhere events are emitted.
ops_manager = OpsConnectionManager()


async def safe_broadcast(event: Dict[str, Any]) -> None:
    """Wrapper around ops_manager.broadcast that swallows all exceptions."""
    try:
        await ops_manager.broadcast(event)
    except Exception as e:
        print("WS ERROR:", e)


def fire_and_forget(event: Dict[str, Any]) -> None:
    """Schedule a broadcast without awaiting.

    Use this inside synchronous contexts or where you don't want to await.
    In async route handlers, prefer `await ops_manager.broadcast(event)` wrapped
    in asyncio.create_task() to keep it truly non-blocking.
    """
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            asyncio.ensure_future(ops_manager.broadcast(event))
        else:
            loop.run_until_complete(ops_manager.broadcast(event))
    except Exception:
        pass
