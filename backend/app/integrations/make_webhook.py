"""
Make.com Webhook Integration (Phase 6.5)
Handles outbound webhook calls to Make.com for automation events.
"""
import json
from typing import Any, Optional

import httpx

from app.core.config import settings, logger


# Cache for sent event IDs to prevent duplicate sends within same process
# Note: For multi-process deployments, use database or Redis
_sent_event_ids: set[str] = set()


async def emit_make_webhook(
    payload: dict[str, Any],
    *,
    webhook_url: Optional[str] = None,
) -> bool:
    """
    Send a webhook payload to Make.com.
    
    Args:
        payload: The webhook payload (must follow Make.com contract)
        webhook_url: Override URL (mainly for testing)
        
    Returns:
        True if webhook was sent successfully, False otherwise
        
    Note:
        - Fails silently (logs error but never raises)
        - Skips if MAKE_WEBHOOK_URL is not configured
        - Skips duplicate event_ids (idempotency)
    """
    # Get webhook URL
    url = webhook_url or getattr(settings, 'MAKE_WEBHOOK_URL', None)
    
    if not url:
        logger.debug("[MakeWebhook] MAKE_WEBHOOK_URL not configured, skipping webhook")
        return False
    
    # Extract event_id for idempotency check
    event_id = payload.get("event_id")
    if not event_id:
        logger.warning("[MakeWebhook] Payload missing event_id, skipping")
        return False
    
    # Idempotency: Skip if already sent
    if event_id in _sent_event_ids:
        logger.info(f"[MakeWebhook] Event {event_id} already sent, skipping duplicate")
        return True  # Return True because it was already successfully sent
    
    # Prepare headers
    headers = {
        "Content-Type": "application/json",
        "X-Event-ID": event_id,
    }
    
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.post(
                url,
                json=payload,
                headers=headers,
            )
            
            if response.status_code >= 200 and response.status_code < 300:
                # Mark as sent for idempotency
                _sent_event_ids.add(event_id)
                logger.info(f"[MakeWebhook] Successfully sent event {event_id} ({payload.get('event')})")
                return True
            else:
                logger.warning(
                    f"[MakeWebhook] Failed to send event {event_id}: "
                    f"HTTP {response.status_code} - {response.text[:200]}"
                )
                return False
                
    except httpx.TimeoutException:
        logger.warning(f"[MakeWebhook] Timeout sending event {event_id}")
        return False
    except httpx.RequestError as e:
        logger.warning(f"[MakeWebhook] Request error sending event {event_id}: {e}")
        return False
    except Exception as e:
        logger.error(f"[MakeWebhook] Unexpected error sending event {event_id}: {e}")
        return False


def clear_sent_events_cache() -> None:
    """Clear the sent events cache (for testing)."""
    _sent_event_ids.clear()


def get_sent_events_cache() -> set[str]:
    """Get copy of sent events cache (for testing)."""
    return _sent_event_ids.copy()
