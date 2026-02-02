"""
Notification Type Constants
Single source of truth for notification types.
"""
from app.db.enums import NotificationType

# Re-export for convenient import
ORDER_CREATED = NotificationType.order_created
ORDER_COMPLETED = NotificationType.order_completed
TASK_OPENED = NotificationType.task_opened
TASK_ASSIGNED = NotificationType.task_assigned
TASK_CLAIMED = NotificationType.task_claimed
TASK_COMPLETED = NotificationType.task_completed
TASK_AUTO_CLOSED = NotificationType.task_auto_closed
TASK_OVERDUE = NotificationType.task_overdue
INVENTORY_LOW = NotificationType.low_stock
INVENTORY_RESTOCKED = NotificationType.inventory_restocked
SALE_RECORDED = NotificationType.sale_recorded
SYSTEM_ALERT = NotificationType.system

# Types that should show toast notifications (interrupting)
TOAST_NOTIFICATION_TYPES = {
    NotificationType.task_assigned,
    NotificationType.task_overdue,
    NotificationType.low_stock,
    NotificationType.system,
}

# Types that update silently (no toast, just unread counter)
SILENT_NOTIFICATION_TYPES = {
    NotificationType.task_completed,
    NotificationType.task_auto_closed,
    NotificationType.order_completed,
    NotificationType.task_claimed,
    NotificationType.task_opened,
    NotificationType.order_created,
    NotificationType.inventory_restocked,
    NotificationType.sale_recorded,
}
