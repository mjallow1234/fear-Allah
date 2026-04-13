"""
Rule Engine for configurable automation (Phase 6.5).

Simple, code-based rules that match events and execute actions.
No DB storage yet — rules are registered at import time.
"""
import logging
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


class RuleEngine:
    """Lightweight event→condition→action rule processor."""

    def __init__(self):
        self.rules: list[dict] = []

    def register_rule(self, rule: dict):
        """Register a rule dict: {event, conditions, actions}."""
        self.rules.append(rule)
        logger.info("[RuleEngine] Registered rule: event=%s actions=%s", rule.get("event"), rule.get("actions"))

    # ------------------------------------------------------------------
    # Core loop
    # ------------------------------------------------------------------

    async def process(self, event_name: str, payload: dict, db: AsyncSession):
        """Evaluate all rules that match *event_name* against *payload*."""
        for rule in self.rules:
            if rule["event"] != event_name:
                continue

            if not self._check_conditions(rule.get("conditions") or {}, payload):
                continue

            logger.info(
                "[RuleEngine] Rule matched: event=%s conditions=%s",
                event_name, rule.get("conditions"),
            )
            await self._execute_actions(rule["actions"], payload, db)

    # ------------------------------------------------------------------
    # Condition evaluators
    # ------------------------------------------------------------------

    def _check_conditions(self, conditions: dict, payload: dict) -> bool:
        """Return True if every condition passes."""
        for key, threshold in conditions.items():
            field, op = self._parse_condition_key(key)
            value = payload.get(field)
            if value is None:
                return False
            try:
                value = float(value)
                threshold = float(threshold)
            except (TypeError, ValueError):
                return False
            if op == "gt" and not (value > threshold):
                return False
            if op == "lt" and not (value < threshold):
                return False
            if op == "gte" and not (value >= threshold):
                return False
            if op == "lte" and not (value <= threshold):
                return False
            if op == "eq" and not (value == threshold):
                return False
        return True

    @staticmethod
    def _parse_condition_key(key: str) -> tuple[str, str]:
        """Parse 'quantity_gt' → ('quantity', 'gt')."""
        for suffix in ("_gte", "_lte", "_gt", "_lt", "_eq"):
            if key.endswith(suffix):
                return key[: -len(suffix)], suffix[1:]
        # No operator suffix — default to equality
        return key, "eq"

    # ------------------------------------------------------------------
    # Action executors
    # ------------------------------------------------------------------

    async def _execute_actions(self, actions: list[str], payload: dict, db: AsyncSession):
        for action in actions:
            try:
                handler = _ACTION_REGISTRY.get(action)
                if handler:
                    await handler(payload, db)
                else:
                    logger.warning("[RuleEngine] Unknown action: %s", action)
            except Exception as e:
                logger.error("[RuleEngine] Action '%s' failed: %s", action, e)


# ======================================================================
# Action implementations
# ======================================================================

async def _action_notify_manager(payload: dict, db: AsyncSession):
    """Send a system notification to all admins/managers."""
    from app.automation.notification_hooks import get_admins_and_managers
    from app.services.notification_emitter import create_and_emit_to_multiple
    from app.db.enums import NotificationType

    admin_ids = await get_admins_and_managers(db)
    if not admin_ids:
        return

    user_name = payload.get("user_name") or f"User {payload.get('user_id', '?')}"
    event = payload.get("_event", "event")
    quantity = payload.get("quantity", "?")

    # Build event-specific navigation metadata
    if event == "sale:created":
        sale_id = payload.get("sale_id")
        metadata = {
            "action_type": "sale",
            "entity_id": sale_id,
            "action_url": f"/sales?tab=transactions&highlight={sale_id}",
        }
    elif event == "inventory:updated":
        product_id = payload.get("product_id")
        metadata = {
            "action_type": "inventory",
            "entity_id": product_id,
            "action_url": f"/sales?tab=inventory&product={product_id}",
        }
    else:
        metadata = {"action_type": "rule_engine", "event": event}

    await create_and_emit_to_multiple(
        db=db,
        user_ids=admin_ids,
        notification_type=NotificationType.system,
        title="Automation Alert",
        content=f"Rule triggered on {event}: quantity={quantity}, by {user_name}",
        metadata=metadata,
    )
    await db.commit()
    logger.info("[RuleEngine] notify_manager sent to %d admin(s)", len(admin_ids))


async def _action_flag_suspicious(payload: dict, db: AsyncSession):
    """Log a warning for suspicious activity (future: write to audit table)."""
    logger.warning(
        "[RuleEngine] SUSPICIOUS FLAG: event=%s payload=%s",
        payload.get("_event"), payload,
    )


async def _action_create_restock_task(payload: dict, db: AsyncSession):
    """Create an automation restock task for the product."""
    from app.automation.service import AutomationService
    from app.db.enums import AutomationTaskType

    product_id = payload.get("product_id")
    user_id = payload.get("user_id") or 0
    await AutomationService.create_task(
        db=db,
        task_type=AutomationTaskType.restock,
        title=f"Auto-restock: product {product_id}",
        created_by_id=user_id,
        description=f"Rule engine triggered restock task for product {product_id}",
        metadata={"trigger": "rule_engine", "product_id": product_id},
    )
    await db.commit()
    logger.info("[RuleEngine] create_restock_task for product %s", product_id)


# Map action name → async handler
_ACTION_REGISTRY: dict[str, Any] = {
    "notify_manager": _action_notify_manager,
    "flag_suspicious": _action_flag_suspicious,
    "create_restock_task": _action_create_restock_task,
}


# ======================================================================
# Global instance + default rules
# ======================================================================

rule_engine = RuleEngine()

# --- Default rules (code-based) ---

rule_engine.register_rule({
    "event": "sale:created",
    "conditions": {"quantity_gt": 5},
    "actions": ["notify_manager"],
})

rule_engine.register_rule({
    "event": "transaction:reversed",
    "conditions": {},
    "actions": ["flag_suspicious"],
})

rule_engine.register_rule({
    "event": "inventory:updated",
    "conditions": {"change_lt": -10},
    "actions": ["notify_manager"],
})
