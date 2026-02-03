"""
Order type to role mappings.

This defines which user roles should receive notifications
when an order of a specific type is created.

NOTE: This is used for order_created notifications BEFORE tasks exist.
For task-based notifications, use participant-based resolution instead.
"""
from app.db.enums import OrderType, UserRole

# Maps order types to the roles that should be notified on order creation
ORDER_TYPE_ROLES: dict[str, list[str]] = {
    OrderType.agent_restock.value: [UserRole.foreman.value, UserRole.delivery.value],
    OrderType.agent_retail.value: [UserRole.delivery.value],
    OrderType.customer_wholesale.value: [UserRole.delivery.value],
    OrderType.store_keeper_restock.value: [UserRole.storekeeper.value, UserRole.delivery.value],
}
