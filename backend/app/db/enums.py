import enum


class UserStatus(str, enum.Enum):
    online = "online"
    away = "away"
    dnd = "dnd"
    offline = "offline"


class UserRole(str, enum.Enum):
    system_admin = "system_admin"
    team_admin = "team_admin"
    member = "member"
    storekeeper = "storekeeper"
    guest = "guest"


class ChannelType(str, enum.Enum):
    public = "public"
    private = "private"
    direct = "direct"


class NotificationType(str, enum.Enum):
    # Chat notifications
    mention = "mention"
    reply = "reply"
    dm = "dm"
    reaction = "reaction"
    # Automation notifications (Phase 6.4)
    task_assigned = "task_assigned"
    task_completed = "task_completed"
    task_auto_closed = "task_auto_closed"
    order_created = "order_created"
    order_completed = "order_completed"
    low_stock = "low_stock"
    inventory_restocked = "inventory_restocked"
    sale_recorded = "sale_recorded"
    system = "system"


class OrderStatus(str, enum.Enum):
    draft = "DRAFT"
    submitted = "SUBMITTED"
    in_progress = "IN_PROGRESS"
    awaiting_confirmation = "AWAITING_CONFIRMATION"
    completed = "COMPLETED"
    cancelled = "CANCELLED"


class TaskStatus(str, enum.Enum):
    pending = "PENDING"
    active = "ACTIVE"
    done = "DONE"


class OrderType(str, enum.Enum):
    agent_restock = "AGENT_RESTOCK"
    agent_retail = "AGENT_RETAIL"
    store_keeper_restock = "STORE_KEEPER_RESTOCK"
    customer_wholesale = "CUSTOMER_WHOLESALE"


class SaleChannel(str, enum.Enum):
    agent = "AGENT"
    store = "STORE"
    direct = "DIRECT"


# ------------------ Automation Engine (Phase 6.1) ------------------

class AutomationTaskType(str, enum.Enum):
    """Types of automation tasks"""
    restock = "RESTOCK"
    retail = "RETAIL"
    wholesale = "WHOLESALE"
    sale = "SALE"
    custom = "CUSTOM"


class AutomationTaskStatus(str, enum.Enum):
    """Status of an automation task"""
    pending = "PENDING"
    in_progress = "IN_PROGRESS"
    completed = "COMPLETED"
    cancelled = "CANCELLED"


class AssignmentStatus(str, enum.Enum):
    """Status of a task assignment"""
    pending = "PENDING"
    in_progress = "IN_PROGRESS"
    done = "DONE"
    skipped = "SKIPPED"


class TaskEventType(str, enum.Enum):
    """Types of task events for audit log"""
    created = "CREATED"
    assigned = "ASSIGNED"
    step_started = "STEP_STARTED"
    step_completed = "STEP_COMPLETED"
    reassigned = "REASSIGNED"
    cancelled = "CANCELLED"
    closed = "CLOSED"
