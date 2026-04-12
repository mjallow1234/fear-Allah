"""
Centralized event type constants for the event emitter system.
"""


class EventType:
    # Sales
    SALE_CREATED = "sale:created"

    # Inventory
    INVENTORY_UPDATED = "inventory:updated"
    INVENTORY_RESTOCKED = "inventory.restocked"
    INVENTORY_ADJUSTED = "inventory.adjusted"
    INVENTORY_LOW_STOCK = "inventory.low_stock"

    # Transactions
    TRANSACTION_REVERSED = "transaction:reversed"

    # Orders
    ORDER_STATUS_CHANGED = "order.status_changed"
    ORDER_COMPLETED = "order.completed"
    ORDER_SUBMITTED = "order.submitted"

    # Tasks
    TASK_COMPLETED = "task.completed"
    TASK_ACTIVATED = "task.activated"
