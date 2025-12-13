import json
import threading
import asyncio
from typing import Optional


def start_redis_listener(redis_client, manager) -> dict:
    """Start a background redis pubsub listener for channel:* and broadcast events to local manager.

    Returns a control dict with 'thread' and 'stop_event' for later shutdown.
    """
    stop_event = threading.Event()

    try:
        pubsub = redis_client.client.pubsub()
        pubsub.psubscribe("channel:*")
    except Exception:
        # If redis is not reachable, we still return a control structure
        return {"thread": None, "stop_event": stop_event, "pubsub": None}

    loop = asyncio.get_event_loop()

    def _listener():
        try:
            while not stop_event.is_set():
                msg = pubsub.get_message(timeout=1)
                if not msg:
                    continue
                # msg types: 'psubscribe', 'pmessage', 'subscribe', 'message'
                t = msg.get('type')
                if t not in ("pmessage", "message"):
                    continue
                try:
                    data_raw = msg.get('data')
                    if isinstance(data_raw, bytes):
                        data_raw = data_raw.decode('utf-8')
                    payload = json.loads(data_raw)
                except Exception:
                    continue

                origin = payload.get('origin')
                if origin == getattr(redis_client, 'instance_id', None):
                    # Ignore our own events
                    continue

                # Extract channel_id from message channel name
                channel_name = msg.get('channel') or msg.get('pattern')
                if not channel_name:
                    continue
                # channel:123 -> 123
                try:
                    if isinstance(channel_name, bytes):
                        channel_name = channel_name.decode('utf-8')
                    parts = channel_name.split(b":") if isinstance(channel_name, bytes) else channel_name.split(":" )
                    channel_id = int(parts[-1])
                except Exception:
                    continue

                coro = manager.broadcast_to_channel(channel_id, payload)
                try:
                    asyncio.run_coroutine_threadsafe(coro, loop)
                except Exception:
                    # If event loop closed or failed, ignore and continue
                    pass
        finally:
            try:
                pubsub.close()
            except Exception:
                pass

    thread = threading.Thread(target=_listener, daemon=True)
    thread.start()
    return {"thread": thread, "stop_event": stop_event, "pubsub": pubsub}
