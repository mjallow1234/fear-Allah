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
    # Business roles (Phase 6)
    agent = "agent"
    storekeeper = "storekeeper"
    delivery = "delivery"
    foreman = "foreman"
    customer = "customer"


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
    draft = "draft"
    submitted = "submitted"
    in_progress = "in_progress"
    awaiting_confirmation = "awaiting_confirmation"
    completed = "completed"
    cancelled = "cancelled"


class TaskStatus(str, enum.Enum):
    pending = "pending"
    active = "active"
    done = "done"


class OrderType(str, enum.Enum):
    agent_restock = "agent_restock"
    agent_retail = "agent_retail"
    store_keeper_restock = "store_keeper_restock"
    customer_wholesale = "customer_wholesale"


class SaleChannel(str, enum.Enum):
    """Sales channels for recording where a sale occurred."""
    field = "field"      # Agent in the field
    store = "store"      # Walk-in at store
    delivery = "delivery"  # Post-delivery sale
    direct = "direct"    # Direct/other


# ------------------ Automation Engine (Phase 6.1) ------------------

class AutomationTaskType(str, enum.Enum):
    """Types of automation tasks"""
    restock = "restock"
    retail = "retail"
    wholesale = "wholesale"
    sale = "sale"
    custom = "custom"


class AutomationTaskStatus(str, enum.Enum):
    """Status of an automation task"""
    # New lifecycle states for claimable tasks
    open = "open"
    claimed = "claimed"

    pending = "pending"
    in_progress = "in_progress"
    completed = "completed"
    cancelled = "cancelled"


class AssignmentStatus(str, enum.Enum):
    """Status of a task assignment"""
    pending = "pending"
    in_progress = "in_progress"
    done = "done"
    skipped = "skipped"


class TaskEventType(str, enum.Enum):
    """Types of task events for audit log"""
    created = "created"
    assigned = "assigned"
    step_started = "step_started"
    step_completed = "step_completed"
    reassigned = "reassigned"
    cancelled = "cancelled"
    closed = "closed"


# ------------------ Agriculture / Processing (Phase 7) ------------------

class ProductType(str, enum.Enum):
    """Type of inventory product for agriculture-aligned tracking."""
    raw_material = "raw_material"      # Unprocessed agricultural commodity (maize, groundnut)
    finished_good = "finished_good"    # Processed product (groundnut paste, flour)
    trade_good = "trade_good"          # Bought and sold without processing


# ------------------ Form Builder (Phase 8) ------------------

class FormFieldType(str, enum.Enum):
    """Types of fields available in dynamic forms."""
    text = "text"
    number = "number"
    date = "date"
    datetime = "datetime"
    select = "select"           # Dropdown single-select
    multiselect = "multiselect" # Dropdown multi-select
    checkbox = "checkbox"
    textarea = "textarea"
    hidden = "hidden"           # For passing context data


class FormCategory(str, enum.Enum):
    """Categories for form organization."""
    order = "order"
    sale = "sale"
    inventory = "inventory"
    raw_material = "raw_material"
    production = "production"
    custom = "custom"


# ------------------ AI Advisory System (Phase 9) ------------------

class AIRecommendationType(str, enum.Enum):
    """Types of AI recommendations."""
    # Phase 9.1: Insights (facts)
    demand_forecast = "demand_forecast"      # AI-1: Demand forecasting
    production_plan = "production_plan"      # AI-2: Production planning advisor
    waste_alert = "waste_alert"              # AI-3: Waste anomaly detection
    yield_insight = "yield_insight"          # AI-3: Yield efficiency insights
    sales_insight = "sales_insight"          # AI-4: Sales intelligence
    agent_insight = "agent_insight"          # AI-4: Agent performance insights
    # Phase 9.2: Recommendations (suggestions)
    production_recommendation = "production_recommendation"  # Suggest production increase
    reorder_recommendation = "reorder_recommendation"        # Suggest inventory reorder
    procurement_recommendation = "procurement_recommendation"  # Suggest raw material procurement


class AIRecommendationScope(str, enum.Enum):
    """Who can see the recommendation."""
    admin = "admin"              # Admin only
    storekeeper = "storekeeper"  # Storekeeper and above
    agent = "agent"              # Agent and above
    system = "system"            # Internal/system use


class AIGenerationMode(str, enum.Enum):
    """How the recommendation was generated."""
    auto = "auto"                    # Nightly cron job
    on_demand = "on_demand"          # Manual "Run AI Analysis" button
    recommendation = "recommendation"  # Phase 9.2: Derived from insights


class AIRecommendationStatus(str, enum.Enum):
    """Lifecycle status of a recommendation (Phase 9.3)."""
    pending = "pending"          # New, not yet reviewed
    acknowledged = "acknowledged"  # Admin has seen it
    approved = "approved"        # Admin approved (for future execution)
    rejected = "rejected"        # Admin rejected with reason
    expired = "expired"          # Past expiration date


# ------------------ AI Governance Tags (Phase 5.1) ------------------

class AIRecommendationPriority(str, enum.Enum):
    """Priority level for AI recommendations."""
    critical = "critical"    # Requires immediate attention
    high = "high"            # Important, should review soon
    medium = "medium"        # Normal priority
    low = "low"              # Nice to have, can wait


class AIRecommendationCategory(str, enum.Enum):
    """Business category for AI recommendations."""
    inventory = "inventory"        # Stock levels, reordering
    production = "production"      # Manufacturing, processing
    procurement = "procurement"    # Raw material purchasing
    sales = "sales"                # Sales patterns, revenue
    operations = "operations"      # General operational efficiency
    compliance = "compliance"      # Regulatory, quality control


class AIRiskLevel(str, enum.Enum):
    """Risk level assessment for recommendations."""
    high_risk = "high_risk"        # Significant business impact if ignored
    medium_risk = "medium_risk"    # Moderate impact
    low_risk = "low_risk"          # Minor impact
    no_risk = "no_risk"            # Informational only
