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
    guest = "guest"


class ChannelType(str, enum.Enum):
    public = "public"
    private = "private"
    direct = "direct"


class NotificationType(str, enum.Enum):
    mention = "mention"
    reply = "reply"
    dm = "dm"
    reaction = "reaction"


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
