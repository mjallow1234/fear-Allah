"""
Make.com Webhook Payload Builder (Phase 6.5)
Constructs standardized payloads following the Make.com automation contract.
"""
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from app.core.config import settings


def generate_event_id() -> str:
    """Generate a unique event ID using UUID v4 with evt_ prefix."""
    return f"evt_{uuid.uuid4().hex[:12].upper()}"


def build_make_payload(
    *,
    event: str,
    actor_user_id: Optional[int] = None,
    actor_username: Optional[str] = None,
    actor_role: Optional[str] = None,
    entity_type: str,
    entity_id: int,
    data: dict[str, Any],
    event_id: Optional[str] = None,
) -> dict[str, Any]:
    """
    Build a Make.com webhook payload following the contract.
    
    Args:
        event: Event type string (e.g., "order.created", "task.completed")
        actor_user_id: ID of user who triggered the event (None for system events)
        actor_username: Username of actor
        actor_role: Role of actor (e.g., "agent", "admin", "system")
        entity_type: Type of entity (e.g., "order", "task", "sale")
        entity_id: ID of the entity
        data: Event-specific data payload
        event_id: Optional pre-generated event ID (for idempotency)
        
    Returns:
        Dict matching the Make.com webhook contract
    """
    if event_id is None:
        event_id = generate_event_id()
    
    # Build actor block (required by contract)
    actor = {
        "user_id": actor_user_id,
        "username": actor_username or "system",
        "role": actor_role or "system",
    }
    
    # Build entity block
    entity = {
        "type": entity_type,
        "id": entity_id,
    }
    
    # Determine environment from settings
    environment = settings.APP_ENV
    
    return {
        "version": "1.0",
        "event": event,
        "event_id": event_id,
        "occurred_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "environment": environment,
        "source": "fear-allah-backend",
        "actor": actor,
        "entity": entity,
        "data": data,
    }


# ------ Event-specific payload builders ------

def build_order_created_payload(
    *,
    order_id: int,
    order_type: str,
    status: str,
    items: list[dict],
    actor_user_id: Optional[int] = None,
    actor_username: Optional[str] = None,
    source: str = "api",
    event_id: Optional[str] = None,
) -> dict[str, Any]:
    """Build payload for order.created event."""
    return build_make_payload(
        event="order.created",
        actor_user_id=actor_user_id,
        actor_username=actor_username,
        actor_role="agent",
        entity_type="order",
        entity_id=order_id,
        data={
            "order_type": order_type,
            "status": status,
            "items": items,
            "meta": {
                "source": source,
            },
        },
        event_id=event_id,
    )


def build_sale_completed_payload(
    *,
    sale_id: int,
    product_id: int,
    quantity: int,
    unit_price: float,
    total_amount: float,
    location: Optional[str] = None,
    related_order_id: Optional[int] = None,
    actor_user_id: Optional[int] = None,
    actor_username: Optional[str] = None,
    event_id: Optional[str] = None,
) -> dict[str, Any]:
    """Build payload for sale.completed event."""
    return build_make_payload(
        event="sale.completed",
        actor_user_id=actor_user_id,
        actor_username=actor_username,
        actor_role="agent",
        entity_type="sale",
        entity_id=sale_id,
        data={
            "product_id": product_id,
            "quantity": quantity,
            "unit_price": unit_price,
            "total_amount": total_amount,
            "location": location,
            "related_order_id": related_order_id,
        },
        event_id=event_id,
    )


def build_inventory_low_stock_payload(
    *,
    inventory_id: int,
    product_id: int,
    current_stock: int,
    threshold: int,
    last_change: int,
    event_id: Optional[str] = None,
) -> dict[str, Any]:
    """Build payload for inventory.low_stock event."""
    return build_make_payload(
        event="inventory.low_stock",
        actor_user_id=None,
        actor_username="system",
        actor_role="system",
        entity_type="inventory",
        entity_id=inventory_id,
        data={
            "product_id": product_id,
            "current_stock": current_stock,
            "threshold": threshold,
            "last_change": last_change,
        },
        event_id=event_id,
    )


def build_task_created_payload(
    *,
    task_id: int,
    title: str,
    assigned_user_id: Optional[int] = None,
    assigned_username: Optional[str] = None,
    related_order_id: Optional[int] = None,
    required: bool = True,
    actor_user_id: Optional[int] = None,
    actor_username: Optional[str] = None,
    event_id: Optional[str] = None,
) -> dict[str, Any]:
    """Build payload for task.created event."""
    assigned_to = None
    if assigned_user_id:
        assigned_to = {
            "user_id": assigned_user_id,
            "username": assigned_username,
        }
    
    return build_make_payload(
        event="task.created",
        actor_user_id=actor_user_id,
        actor_username=actor_username,
        actor_role="system",
        entity_type="task",
        entity_id=task_id,
        data={
            "title": title,
            "assigned_to": assigned_to,
            "related_order_id": related_order_id,
            "required": required,
        },
        event_id=event_id,
    )


def build_task_completed_payload(
    *,
    task_id: int,
    completed_by_user_id: int,
    completed_by_username: str,
    completed_at: Optional[datetime] = None,
    event_id: Optional[str] = None,
) -> dict[str, Any]:
    """Build payload for task.completed event."""
    if completed_at is None:
        completed_at = datetime.now(timezone.utc)
    
    return build_make_payload(
        event="task.completed",
        actor_user_id=completed_by_user_id,
        actor_username=completed_by_username,
        actor_role="agent",
        entity_type="task",
        entity_id=task_id,
        data={
            "completed_by": {
                "user_id": completed_by_user_id,
                "username": completed_by_username,
            },
            "completed_at": completed_at.isoformat().replace("+00:00", "Z"),
        },
        event_id=event_id,
    )


def build_automation_triggered_payload(
    *,
    automation_task_id: int,
    rule: str,
    trigger_event: str,
    status: str = "queued",
    event_id: Optional[str] = None,
) -> dict[str, Any]:
    """Build payload for automation.triggered event."""
    return build_make_payload(
        event="automation.triggered",
        actor_user_id=None,
        actor_username="system",
        actor_role="system",
        entity_type="automation_task",
        entity_id=automation_task_id,
        data={
            "rule": rule,
            "trigger_event": trigger_event,
            "status": status,
        },
        event_id=event_id,
    )


def build_automation_failed_payload(
    *,
    entity_type: str,
    entity_id: int,
    reason: str,
    message: str,
    recoverable: bool = False,
    event_id: Optional[str] = None,
) -> dict[str, Any]:
    """Build payload for automation.failed event."""
    return build_make_payload(
        event="automation.failed",
        actor_user_id=None,
        actor_username="system",
        actor_role="system",
        entity_type=entity_type,
        entity_id=entity_id,
        data={
            "reason": reason,
            "message": message,
            "recoverable": recoverable,
        },
        event_id=event_id,
    )
