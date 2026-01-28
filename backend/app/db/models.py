from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Text, Index, UniqueConstraint, Float
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.database import Base
from app.db.enums import (
    UserStatus, UserRole, ChannelType, NotificationType, 
    OrderStatus, TaskStatus, OrderType, SaleChannel,
    AutomationTaskType, AutomationTaskStatus, AssignmentStatus, TaskEventType,
    ProductType, FormFieldType, FormCategory,
    AIRecommendationType, AIRecommendationScope, AIGenerationMode, AIRecommendationStatus,
    AIRecommendationPriority, AIRecommendationCategory, AIRiskLevel  # Phase 5.1
)




class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        Index("ix_users_role", "role"),
        Index("ix_users_is_banned", "is_banned"),
        Index("ix_users_is_muted", "is_muted"),
    )
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, index=True, nullable=False)
    email = Column(String(255), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    display_name = Column(String(100))
    avatar_url = Column(String(500))
    status = Column(SAEnum(UserStatus, name="userstatus", create_type=False), default=UserStatus.offline.value, nullable=False)
    role = Column(SAEnum(UserRole, name="userrole", create_type=False), default=UserRole.member.value, nullable=False)  # Global role
    is_active = Column(Boolean, default=True)
    is_system_admin = Column(Boolean, default=False)  # Legacy - use role instead
    is_banned = Column(Boolean, default=False)
    ban_reason = Column(String(500))
    banned_at = Column(DateTime(timezone=True))
    banned_by_id = Column(Integer, ForeignKey("users.id"))
    is_muted = Column(Boolean, default=False)
    muted_until = Column(DateTime(timezone=True))
    muted_reason = Column(String(500))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    # Relationships
    messages = relationship("Message", back_populates="author", foreign_keys="[Message.author_id]")
    team_memberships = relationship("TeamMember", back_populates="user")
    channel_memberships = relationship("ChannelMember", back_populates="user")

    # Operational roles (workflow participation) - separate from system role
    operational_roles = relationship(
        "UserOperationalRole",
        back_populates="user",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    def has_operational_role(self, role: str) -> bool:
        """Return True if the user has the given operational role."""
        return any(r.role == role for r in getattr(self, 'operational_roles', []))


class Team(Base):
    __tablename__ = "teams"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), unique=True, index=True, nullable=False)
    display_name = Column(String(200))
    description = Column(Text)
    icon_url = Column(String(500))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    channels = relationship("Channel", back_populates="team")
    members = relationship("TeamMember", back_populates="team")


class TeamMember(Base):
    __tablename__ = "team_members"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    team_id = Column(Integer, ForeignKey("teams.id"), nullable=False)
    role = Column(String(50), default="member")  # admin, member
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    user = relationship("User", back_populates="team_memberships")
    team = relationship("Team", back_populates="members")


class Channel(Base):
    __tablename__ = "channels"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), index=True, nullable=False)
    display_name = Column(String(200))
    description = Column(Text)
    type = Column(SAEnum(ChannelType, name="channeltype", create_type=False), default=ChannelType.public.value, nullable=False)
    team_id = Column(Integer, ForeignKey("teams.id"), nullable=True)  # Null for global channels
    is_archived = Column(Boolean, default=False)
    archived_at = Column(DateTime(timezone=True))
    archived_by_id = Column(Integer, ForeignKey("users.id"))
    retention_days = Column(Integer, default=0)  # 0 means no limit
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    team = relationship("Team", back_populates="channels")
    messages = relationship("Message", back_populates="channel")
    members = relationship("ChannelMember", back_populates="channel")


class ChannelMember(Base):
    __tablename__ = "channel_members"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    channel_id = Column(Integer, ForeignKey("channels.id"), nullable=False)
    last_read_at = Column(DateTime(timezone=True))
    last_viewed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    user = relationship("User", back_populates="channel_memberships")
    channel = relationship("Channel", back_populates="members")


class ChannelRead(Base):
    """
    Track last read message per user per channel.
    Phase 4.4 - Read Receipts.
    One row per user per channel - efficient, no per-message writes.
    """
    __tablename__ = "channel_reads"
    __table_args__ = (
        Index("ix_channel_reads_channel_message", "channel_id", "last_read_message_id"),
    )
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    channel_id = Column(Integer, ForeignKey("channels.id"), nullable=False)
    last_read_message_id = Column(Integer, ForeignKey("messages.id"), nullable=True)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # Relationships
    user = relationship("User")
    channel = relationship("Channel")
    message = relationship("Message")


class Message(Base):
    __tablename__ = "messages"
    
    id = Column(Integer, primary_key=True, index=True)
    content = Column(Text, nullable=False)
    channel_id = Column(Integer, ForeignKey("channels.id"), nullable=False)
    author_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    parent_id = Column(Integer, ForeignKey("messages.id"), nullable=True)  # For threads
    is_edited = Column(Boolean, default=False)
    is_deleted = Column(Boolean, default=False)
    edited_at = Column(DateTime(timezone=True), nullable=True)  # When message was edited
    editor_id = Column(Integer, ForeignKey("users.id"), nullable=True)  # Who edited (for admin edits)
    deleted_at = Column(DateTime(timezone=True), nullable=True)
    is_pinned = Column(Boolean, default=False)
    thread_count = Column(Integer, default=0)  # Cached count of replies
    last_activity_at = Column(DateTime(timezone=True), server_default=func.now())  # Last reply or edit time
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    channel = relationship("Channel", back_populates="messages")
    author = relationship("User", back_populates="messages", foreign_keys=[author_id])
    editor = relationship("User", foreign_keys=[editor_id])
    replies = relationship("Message", backref="parent", remote_side=[id])
    reactions = relationship("MessageReaction", back_populates="message", lazy="selectin")


class FileAttachment(Base):
    """
    Phase 9.1 - File attachments for chat messages.
    Supports local disk storage with configurable path.
    """
    __tablename__ = "file_attachments"
    __table_args__ = (
        Index("ix_file_attachments_message_id", "message_id"),
        Index("ix_file_attachments_channel_id", "channel_id"),
        Index("ix_file_attachments_user_id", "user_id"),
    )
    
    id = Column(Integer, primary_key=True, index=True)
    message_id = Column(Integer, ForeignKey("messages.id", ondelete="CASCADE"), nullable=True)
    channel_id = Column(Integer, ForeignKey("channels.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)  # Uploader
    
    # File metadata
    filename = Column(String(255), nullable=False)  # Sanitized filename stored on disk
    file_path = Column(String(500), nullable=False)  # Legacy field (kept for compatibility)
    storage_path = Column(String(500), nullable=True)  # Full path in storage (Phase 9.1)
    file_size = Column(Integer, nullable=True)  # Size in bytes
    mime_type = Column(String(100), nullable=True)  # MIME type
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    message = relationship("Message", backref="attachments")
    uploader = relationship("User")
    channel = relationship("Channel")


class MessageReaction(Base):
    __tablename__ = "message_reactions"
    
    id = Column(Integer, primary_key=True, index=True)
    message_id = Column(Integer, ForeignKey("messages.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    emoji = Column(String(32), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Prevent duplicate reactions
    __table_args__ = (
        UniqueConstraint("message_id", "user_id", "emoji", name="uq_message_reactions_message_user_emoji"),
        Index("ix_message_reactions_message_emoji", "message_id", "emoji"),
    )
    
    # Relationships
    message = relationship("Message", back_populates="reactions")
    user = relationship("User")


class UserOperationalRole(Base):
    __tablename__ = "user_operational_roles"
    __table_args__ = (
        UniqueConstraint("user_id", "role", name="uq_user_operational_role"),
        Index("ix_user_operational_roles_user_id", "user_id"),
    )

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    role = Column(String(50), nullable=False)

    # Relationship back to User
    user = relationship("User", back_populates="operational_roles")


class Notification(Base):
    __tablename__ = "notifications"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    type = Column(
        SAEnum(
            NotificationType,
            name="notificationtype",
            native_enum=True,
            values_callable=lambda enum: [e.value for e in enum],
            create_type=False,
        ),
        nullable=False,
    )
    title = Column(String(255), nullable=False)
    content = Column(Text)
    channel_id = Column(Integer, ForeignKey("channels.id"), nullable=True)
    message_id = Column(Integer, ForeignKey("messages.id"), nullable=True)
    sender_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    # Automation context (Phase 6.4)
    task_id = Column(Integer, ForeignKey("automation_tasks.id"), nullable=True)
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=True)
    inventory_id = Column(Integer, ForeignKey("inventory.id"), nullable=True)
    sale_id = Column(Integer, ForeignKey("sales.id"), nullable=True)
    extra_data = Column(Text, nullable=True)  # JSON for extra context (named extra_data to avoid SQLAlchemy reserved name)
    is_read = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    user = relationship("User", foreign_keys=[user_id])
    sender = relationship("User", foreign_keys=[sender_id])
    channel = relationship("Channel")
    message = relationship("Message")
    automation_task = relationship("AutomationTask")
    order = relationship("Order")
    inventory = relationship("Inventory")
    sale = relationship("Sale")


class AuditLog(Base):
    """
    System-wide audit log for tracking all significant actions.
    Used by admins to review activity across sales, inventory, tasks, orders, etc.
    Phase 8.2: Enhanced with description, request_id, and actor_username for better tracking.
    """
    __tablename__ = "audit_logs"
    __table_args__ = (
        Index("ix_audit_logs_user_id", "user_id"),
        Index("ix_audit_logs_action", "action"),
        Index("ix_audit_logs_target_type", "target_type"),
        Index("ix_audit_logs_created_at", "created_at"),
    )
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)  # Actor who performed action
    username = Column(String(100), nullable=True)  # Denormalized for fast display (Phase 8.2)
    action = Column(String(100), nullable=False)  # e.g., 'sale.create', 'inventory.restock'
    target_type = Column(String(50))  # e.g., 'sale', 'inventory', 'order', 'user', 'channel'
    target_id = Column(Integer)  # ID of affected entity
    description = Column(String(500), nullable=True)  # Human-readable summary (Phase 8.2)
    meta = Column(Text)  # JSON details
    ip_address = Column(String(50))
    request_id = Column(String(50), nullable=True)  # For correlation with logs (Phase 8.2)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    # Relationships
    user = relationship("User")

# ------------------ Orders & Tasks ------------------
class Order(Base):
    __tablename__ = "orders"

    id = Column(Integer, primary_key=True, index=True)
    order_type = Column(SAEnum(OrderType, name="ordertype", create_type=False), nullable=False)
    status = Column(SAEnum(OrderStatus, name="orderstatus", create_type=False), nullable=False, default=OrderStatus.submitted.value)
    meta = Column(Text)
    items = Column(Text)
    # Extended fields (Forms Extension)
    reference = Column(String(100), nullable=True)
    priority = Column(String(20), nullable=True)  # low, normal, high, urgent
    requested_delivery_date = Column(DateTime(timezone=True), nullable=True)
    customer_name = Column(String(200), nullable=True)
    customer_phone = Column(String(50), nullable=True)
    payment_method = Column(String(50), nullable=True)  # cash, card, transfer, credit
    internal_comment = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Track creator for auditing and notifications
    created_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_by = relationship("User", foreign_keys=[created_by_id])

    # New: channel context for orders (links to legacy Channel where messages originate)
    channel_id = Column(Integer, ForeignKey("channels.id"), nullable=True)
    channel = relationship("Channel")

    tasks = relationship("Task", back_populates="order", order_by="Task.id")


class Task(Base):
    __tablename__ = "tasks"

    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=False)
    step_key = Column(String(100), nullable=False)
    title = Column(String(200), nullable=False)
    assigned_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    status = Column(SAEnum(TaskStatus, name="taskstatus", create_type=False), nullable=False, default=TaskStatus.pending.value)
    required = Column(Boolean, default=True)
    activated_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    version = Column(Integer, default=1)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    order = relationship("Order", back_populates="tasks")


# ------------------ Inventory & Sales (Phase 6.3) ------------------
class Inventory(Base):
    """Inventory item tracking stock levels per product."""
    __tablename__ = "inventory"

    id = Column(Integer, primary_key=True, index=True)
    product_id = Column(Integer, nullable=False, unique=True, index=True)
    product_name = Column(String(255), nullable=True)  # Human-readable name
    product_type = Column(SAEnum(ProductType, name="producttype", create_type=False), 
                         default=ProductType.trade_good.value, nullable=False)  # Agriculture tracking
    total_stock = Column(Integer, default=0, nullable=False)
    total_sold = Column(Integer, default=0, nullable=False)
    low_stock_threshold = Column(Integer, default=10, nullable=False)  # Trigger threshold
    version = Column(Integer, default=1)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    transactions = relationship("InventoryTransaction", back_populates="inventory_item", cascade="all, delete-orphan")
    # Processing recipes where this product is the finished good
    recipes_as_output = relationship("ProcessingRecipe", back_populates="finished_product", 
                                     foreign_keys="ProcessingRecipe.finished_product_id")

    @property
    def is_low_stock(self) -> bool:
        """Check if stock is below threshold."""
        return self.total_stock <= self.low_stock_threshold


class Sale(Base):
    """Sale record tracking individual transactions."""
    __tablename__ = "sales"

    id = Column(Integer, primary_key=True, index=True)
    product_id = Column(Integer, nullable=False, index=True)
    quantity = Column(Integer, nullable=False)
    unit_price = Column(Integer, nullable=False)
    total_amount = Column(Integer, nullable=False)
    sold_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    sale_channel = Column(SAEnum(SaleChannel, name="salechannel", create_type=False), nullable=False)
    related_order_id = Column(Integer, ForeignKey("orders.id"), nullable=True)
    location = Column(String(255), nullable=True)  # Where the sale occurred
    idempotency_key = Column(String(255), nullable=True, unique=False)
    # Extended fields (Forms Extension)
    reference = Column(String(100), nullable=True)
    customer_name = Column(String(200), nullable=True)
    customer_phone = Column(String(50), nullable=True)
    discount = Column(Integer, nullable=True)  # Discount in currency units
    payment_method = Column(String(50), nullable=True)  # cash, card, transfer, credit
    sale_date = Column(DateTime(timezone=True), nullable=True)
    linked_order_id = Column(Integer, ForeignKey("orders.id"), nullable=True)
    # Affiliate fields
    affiliate_code = Column(String(100), nullable=True)
    affiliate_name = Column(String(200), nullable=True)
    affiliate_source = Column(String(50), nullable=True)  # web, whatsapp, referral, unknown
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    sold_by = relationship("User")
    related_order = relationship("Order", foreign_keys=[related_order_id])
    linked_order = relationship("Order", foreign_keys=[linked_order_id])
    transaction = relationship("InventoryTransaction", back_populates="related_sale", uselist=False)


class InventoryTransaction(Base):
    """
    Audit log for inventory changes.
    Tracks all stock movements with reason and related entities.
    """
    __tablename__ = "inventory_transactions"
    __table_args__ = (
        Index("ix_inventory_transactions_inventory_item_id", "inventory_item_id"),
        Index("ix_inventory_transactions_reason", "reason"),
        Index("ix_inventory_transactions_created_at", "created_at"),
    )

    id = Column(Integer, primary_key=True, index=True)
    inventory_item_id = Column(Integer, ForeignKey("inventory.id"), nullable=False)
    change = Column(Integer, nullable=False)  # Negative for sale/removal, positive for restock
    reason = Column(String(50), nullable=False)  # sale, restock, adjustment, return, processing_in
    related_sale_id = Column(Integer, ForeignKey("sales.id"), nullable=True)
    related_order_id = Column(Integer, ForeignKey("orders.id"), nullable=True)
    related_batch_id = Column(Integer, ForeignKey("processing_batches.id"), nullable=True)
    performed_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    inventory_item = relationship("Inventory", back_populates="transactions")
    related_sale = relationship("Sale", back_populates="transaction")
    related_order = relationship("Order")
    related_batch = relationship("ProcessingBatch", back_populates="inventory_transaction")
    performed_by = relationship("User")


# ------------------ Raw Materials (Forms Extension) ------------------
class RawMaterial(Base):
    """Raw material inventory for production/manufacturing."""
    __tablename__ = "raw_materials"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False, index=True)
    description = Column(Text, nullable=True)
    unit = Column(String(50), nullable=False)  # kg, liters, pieces, etc.
    current_stock = Column(Integer, default=0, nullable=False)
    min_stock_level = Column(Integer, default=0, nullable=True)
    cost_per_unit = Column(Integer, nullable=True)  # Cost in smallest currency unit
    supplier = Column(String(255), nullable=True)
    created_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    created_by = relationship("User")
    transactions = relationship("RawMaterialTransaction", back_populates="raw_material", cascade="all, delete-orphan")

    @property
    def is_low_stock(self) -> bool:
        """Check if stock is below minimum level."""
        return self.current_stock <= (self.min_stock_level or 0)


class RawMaterialTransaction(Base):
    """Audit log for raw material stock changes."""
    __tablename__ = "raw_material_transactions"
    __table_args__ = (
        Index("ix_raw_material_transactions_raw_material_id", "raw_material_id"),
    )

    id = Column(Integer, primary_key=True, index=True)
    raw_material_id = Column(Integer, ForeignKey("raw_materials.id"), nullable=False)
    change = Column(Integer, nullable=False)  # positive for add, negative for consume
    reason = Column(String(50), nullable=False)  # add, consume, adjust, return, processing_out
    notes = Column(Text, nullable=True)
    performed_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    related_batch_id = Column(Integer, ForeignKey("processing_batches.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    raw_material = relationship("RawMaterial", back_populates="transactions")
    performed_by = relationship("User")
    related_batch = relationship("ProcessingBatch", back_populates="raw_material_transactions")


# ------------------ Processing / Manufacturing (Agriculture Phase) ------------------

class ProcessingRecipe(Base):
    """
    Recipe defining raw materials needed to produce a finished good.
    E.g., Groundnut Paste requires X kg of Groundnuts.
    """
    __tablename__ = "processing_recipes"
    __table_args__ = (
        UniqueConstraint("finished_product_id", "raw_material_id", name="uq_recipe_product_material"),
        Index("ix_processing_recipes_finished_product_id", "finished_product_id"),
    )

    id = Column(Integer, primary_key=True, index=True)
    finished_product_id = Column(Integer, ForeignKey("inventory.id"), nullable=False)
    raw_material_id = Column(Integer, ForeignKey("raw_materials.id"), nullable=False)
    quantity_required = Column(Integer, nullable=False)  # Amount of raw material per unit of finished good
    unit = Column(String(50), nullable=False)  # kg, liters, pieces
    waste_percentage = Column(Integer, default=0, nullable=True)  # Expected waste (0-100)
    notes = Column(Text, nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    created_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    finished_product = relationship("Inventory", back_populates="recipes_as_output")
    raw_material = relationship("RawMaterial")
    created_by = relationship("User")


class ProcessingBatch(Base):
    """
    Record of a processing/manufacturing run.
    Tracks raw material consumption and finished good production.
    
    Yield/Waste Tracking (Phase 7.2):
    - expected_quantity: What recipe predicted
    - quantity_produced: What was actually produced
    - actual_waste_quantity: Measured waste
    - yield_efficiency: actual/expected * 100
    """
    __tablename__ = "processing_batches"
    __table_args__ = (
        Index("ix_processing_batches_finished_product_id", "finished_product_id"),
        Index("ix_processing_batches_status", "status"),
        Index("ix_processing_batches_created_at", "created_at"),
    )

    id = Column(Integer, primary_key=True, index=True)
    batch_reference = Column(String(100), nullable=True, unique=True)  # Optional batch number
    finished_product_id = Column(Integer, ForeignKey("inventory.id"), nullable=False)
    quantity_produced = Column(Integer, nullable=False)  # Actual units produced
    expected_quantity = Column(Integer, nullable=True)  # Expected based on recipe
    actual_waste_quantity = Column(Integer, default=0, nullable=True)  # Measured waste
    waste_notes = Column(Text, nullable=True)  # Notes about waste cause
    raw_materials_used = Column(Text, nullable=True)  # JSON snapshot of inputs
    yield_efficiency = Column(Integer, nullable=True)  # (actual/expected)*100
    status = Column(String(50), default="completed", nullable=False)  # completed, cancelled, in_progress
    notes = Column(Text, nullable=True)
    processed_by_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    completed_at = Column(DateTime(timezone=True), nullable=True)  # When batch was completed

    # Relationships
    finished_product = relationship("Inventory")
    processed_by = relationship("User")
    raw_material_transactions = relationship("RawMaterialTransaction", back_populates="related_batch")
    inventory_transaction = relationship("InventoryTransaction", back_populates="related_batch", uselist=False)


# ------------------ Permissions & Roles (Phase 5.2 + 8.5.2) ------------------


class Role(Base):
    """
    Role model for permission-based access control.
    
    Phase 8.5.2 - Enhanced with:
    - is_system: Flag for immutable system roles (system_admin, default)
    - description: Human-readable description
    - created_at: Timestamp for audit
    
    System roles cannot be deleted and have minimum permissions.
    """
    __tablename__ = "roles"
    __table_args__ = (
        Index("ix_roles_is_system", "is_system"),
    )

    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False, unique=True)  # lowercase, snake_case
    description = Column(String(500), nullable=True)
    scope = Column(String(50), nullable=False, default="system")  # system | channel
    is_system = Column(Boolean, nullable=False, default=False)  # Immutable system roles
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    permissions = relationship(
        "RolePermission",
        back_populates="role",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    user_roles = relationship("UserRole", back_populates="role")


class PermissionModel(Base):
    """
    Permission model - global permissions referenced by roles.
    
    Phase 8.5.2 - Permissions are DB-driven, not hardcoded enums.
    Key format: category.action (e.g., channel.create, system.manage_users)
    """
    __tablename__ = "permissions"
    __table_args__ = (
        Index("ix_permissions_key", "key"),
    )

    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False, unique=True)  # Legacy - kept for compatibility
    key = Column(String(100), nullable=True, unique=True)  # New: category.action format
    description = Column(String(500), nullable=True)


class RolePermission(Base):
    """Junction table for role-permission many-to-many relationship."""
    __tablename__ = "role_permissions"

    role_id = Column(Integer, ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True)
    permission_id = Column(Integer, ForeignKey("permissions.id", ondelete="CASCADE"), primary_key=True)

    role = relationship("Role", back_populates="permissions")
    permission = relationship("PermissionModel")


class UserRole(Base):
    """User-role assignment for global/system permissions."""
    __tablename__ = "user_roles"

    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    role_id = Column(Integer, ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True)

    role = relationship("Role", back_populates="user_roles")
    user = relationship("User")

    __table_args__ = (
        UniqueConstraint("user_id", "role_id", name="uq_user_role"),
    )


class ChannelRoleAssignment(Base):
    __tablename__ = "channel_roles"

    user_id = Column(Integer, ForeignKey("users.id"), primary_key=True)
    channel_id = Column(Integer, ForeignKey("channels.id"), primary_key=True)
    role_id = Column(Integer, ForeignKey("roles.id"), primary_key=True)

    role = relationship("Role")

    __table_args__ = (
        UniqueConstraint("user_id", "channel_id", "role_id", name="uq_channel_role"),
    )


# ------------------ Automation Engine (Phase 6.1) ------------------

class AutomationTask(Base):
    """
    Generic task for workflow automation.
    Can be standalone or linked to an order.
    """
    __tablename__ = "automation_tasks"
    __table_args__ = (
        Index("ix_automation_tasks_status", "status"),
        Index("ix_automation_tasks_type", "task_type"),
        Index("ix_automation_tasks_created_by", "created_by_id"),
    )

    id = Column(Integer, primary_key=True, index=True)
    task_type = Column(SAEnum(AutomationTaskType, name="automationtasktype", create_type=False), nullable=False)
    # New default state is OPEN; existing PENDING tasks will be mapped to OPEN in migration
    status = Column(SAEnum(AutomationTaskStatus, name="automationtaskstatus", create_type=False), nullable=False, default=AutomationTaskStatus.open.value)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    created_by_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    related_order_id = Column(Integer, ForeignKey("orders.id"), nullable=True)
    task_metadata = Column(Text, nullable=True)  # JSON for extensibility (named task_metadata to avoid SQLAlchemy reserved name)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Claiming fields (nullable until we enable claiming behavior)
    required_role = Column(String(100), nullable=True)
    claimed_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    claimed_at = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    created_by = relationship("User", foreign_keys=[created_by_id])
    claimed_by = relationship("User", foreign_keys=[claimed_by_user_id])

    # Relationships
    created_by = relationship("User", foreign_keys=[created_by_id])
    related_order = relationship("Order")
    assignments = relationship("TaskAssignment", back_populates="task", cascade="all, delete-orphan")
    events = relationship("TaskEvent", back_populates="task", cascade="all, delete-orphan", order_by="TaskEvent.created_at")


class TaskAssignment(Base):
    """
    Assignment of a user to a task with a specific role.
    Multiple users can be assigned to the same task.
    """
    __tablename__ = "task_assignments"
    __table_args__ = (
        Index("ix_task_assignments_task_id", "task_id"),
        Index("ix_task_assignments_user_id", "user_id"),
        UniqueConstraint("task_id", "user_id", name="uq_task_user_assignment"),
    )

    id = Column(Integer, primary_key=True, index=True)
    task_id = Column(Integer, ForeignKey("automation_tasks.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    role_hint = Column(String(100), nullable=True)  # e.g., "foreman", "delivery", "agent"
    status = Column(SAEnum(AssignmentStatus, name="assignmentstatus", create_type=False), nullable=False, default=AssignmentStatus.pending.value)
    notes = Column(Text, nullable=True)
    assigned_at = Column(DateTime(timezone=True), server_default=func.now())
    completed_at = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    task = relationship("AutomationTask", back_populates="assignments")
    user = relationship("User")


class TaskEvent(Base):
    """
    Audit log for task lifecycle events.
    Tracks who did what and when.
    """
    __tablename__ = "task_events"
    __table_args__ = (
        Index("ix_task_events_task_id", "task_id"),
        Index("ix_task_events_created_at", "created_at"),
    )

    id = Column(Integer, primary_key=True, index=True)
    task_id = Column(Integer, ForeignKey("automation_tasks.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)  # Nullable for system events
    event_type = Column(
        SAEnum(
            TaskEventType,
            name="taskeventtype",
            native_enum=True,
            values_callable=lambda enum: [e.value for e in enum],
            create_type=False,
        ),
        nullable=False,
    )
    event_metadata = Column(Text, nullable=True)  # JSON for event-specific data (named event_metadata to avoid SQLAlchemy reserved name)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    task = relationship("AutomationTask", back_populates="events")
    user = relationship("User")


# ============================================================================
# FORM BUILDER (Phase 8) - Dynamic Forms System
# ============================================================================

class Form(Base):
    """
    Dynamic form definition.
    Forms define the structure of data entry - not business logic.
    """
    __tablename__ = "forms"
    __table_args__ = (
        Index("ix_forms_slug", "slug"),
        Index("ix_forms_category", "category"),
        Index("ix_forms_is_active", "is_active"),
    )

    id = Column(Integer, primary_key=True, index=True)
    slug = Column(String(100), unique=True, nullable=False)  # e.g., "sales", "agent_restock_order"
    name = Column(String(255), nullable=False)  # Display name
    description = Column(Text, nullable=True)
    category = Column(SAEnum(FormCategory, name="formcategory", create_type=False), nullable=False)
    
    # Permissions
    allowed_roles = Column(Text, nullable=True)  # JSON array of roles that can use this form
    
    # Service routing - which backend service handles submissions
    service_target = Column(String(100), nullable=True)  # e.g., "sales", "orders", "inventory"
    
    # Mapping config - maps form fields to service fields
    field_mapping = Column(Text, nullable=True)  # JSON mapping config
    
    # Status
    is_active = Column(Boolean, default=True)
    current_version = Column(Integer, default=1)
    
    # Audit
    created_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    fields = relationship("FormField", back_populates="form", cascade="all, delete-orphan", order_by="FormField.order_index")
    versions = relationship("FormVersion", back_populates="form", cascade="all, delete-orphan")
    submissions = relationship("FormSubmission", back_populates="form")
    created_by = relationship("User")


class FormField(Base):
    """
    Individual field in a form.
    Fields can have role-based visibility and validation rules.
    """
    __tablename__ = "form_fields"
    __table_args__ = (
        Index("ix_form_fields_form_id", "form_id"),
        Index("ix_form_fields_key", "key"),
    )

    id = Column(Integer, primary_key=True, index=True)
    form_id = Column(Integer, ForeignKey("forms.id", ondelete="CASCADE"), nullable=False)
    
    # Field definition
    key = Column(String(100), nullable=False)  # e.g., "product_id", "quantity"
    label = Column(String(255), nullable=False)  # Display label
    field_type = Column(SAEnum(FormFieldType, name="formfieldtype", create_type=False), nullable=False)
    placeholder = Column(String(255), nullable=True)
    help_text = Column(Text, nullable=True)
    
    # Validation
    required = Column(Boolean, default=False)
    min_value = Column(Integer, nullable=True)  # For number fields
    max_value = Column(Integer, nullable=True)
    min_length = Column(Integer, nullable=True)  # For text fields
    max_length = Column(Integer, nullable=True)
    pattern = Column(String(500), nullable=True)  # Regex pattern
    
    # Options for select/multiselect
    options = Column(Text, nullable=True)  # JSON array of {value, label} or just strings
    
    # Data source for dynamic options
    options_source = Column(String(255), nullable=True)  # e.g., "products", "raw_materials", "users:agent"
    
    # Default value
    default_value = Column(Text, nullable=True)  # JSON for complex defaults
    
    # Visibility
    role_visibility = Column(Text, nullable=True)  # JSON array of roles that can see this field
    conditional_visibility = Column(Text, nullable=True)  # JSON rules for showing/hiding based on other fields
    
    # Ordering
    order_index = Column(Integer, default=0)
    
    # Grouping
    field_group = Column(String(100), nullable=True)  # For grouping related fields
    
    # Audit
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    form = relationship("Form", back_populates="fields")


class FormVersion(Base):
    """
    Version history for forms.
    Allows rollback and audit of form changes.
    """
    __tablename__ = "form_versions"
    __table_args__ = (
        Index("ix_form_versions_form_id", "form_id"),
        Index("ix_form_versions_version", "version"),
    )

    id = Column(Integer, primary_key=True, index=True)
    form_id = Column(Integer, ForeignKey("forms.id", ondelete="CASCADE"), nullable=False)
    version = Column(Integer, nullable=False)
    
    # Complete snapshot of form definition at this version
    snapshot = Column(Text, nullable=False)  # JSON snapshot
    
    # Change notes
    change_notes = Column(Text, nullable=True)
    
    # Audit
    created_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    form = relationship("Form", back_populates="versions")
    created_by = relationship("User")


class FormSubmission(Base):
    """
    Record of form submissions.
    Stores the submitted data and routing result.
    """
    __tablename__ = "form_submissions"
    __table_args__ = (
        Index("ix_form_submissions_form_id", "form_id"),
        Index("ix_form_submissions_submitted_by_id", "submitted_by_id"),
        Index("ix_form_submissions_created_at", "created_at"),
    )

    id = Column(Integer, primary_key=True, index=True)
    form_id = Column(Integer, ForeignKey("forms.id"), nullable=False)
    form_version = Column(Integer, nullable=False)  # Version at time of submission
    
    # Submitted data
    data = Column(Text, nullable=False)  # JSON of submitted field values
    
    # Routing result
    service_target = Column(String(100), nullable=True)
    result_id = Column(Integer, nullable=True)  # ID from the target service (e.g., sale_id, order_id)
    result_type = Column(String(50), nullable=True)  # e.g., "sale", "order"
    
    # Status
    status = Column(String(50), default="pending")  # pending, processed, failed
    error_message = Column(Text, nullable=True)
    
    # Audit
    submitted_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    form = relationship("Form", back_populates="submissions")
    submitted_by = relationship("User")


# ------------------ AI Advisory System (Phase 9) ------------------

class AIRecommendation(Base):
    """
    AI-generated recommendations (advisory only).
    
    SAFETY GUARANTEE:
    - AI reads from: sales, inventory, raw_materials, processing_batches, recipes
    - AI writes ONLY to: ai_recommendations
    - AI NEVER mutates core business tables
    
    All recommendations include:
    - Summary (human-readable)
    - Explanation (why this recommendation)
    - Confidence score (0.0-1.0)
    - Data references (which entities were analyzed)
    
    Phase 4.1: Lifecycle states
    - status: pending → acknowledged → approved/rejected → expired
    - Admin feedback with notes
    """
    __tablename__ = "ai_recommendations"
    __table_args__ = (
        Index("ix_ai_recommendations_type", "type"),
        Index("ix_ai_recommendations_scope", "scope"),
        Index("ix_ai_recommendations_generated_by", "generated_by"),
        Index("ix_ai_recommendations_created_at", "created_at"),
        Index("ix_ai_recommendations_is_dismissed", "is_dismissed"),
    )

    id = Column(Integer, primary_key=True, index=True)
    
    # Recommendation type and scope
    type = Column(SAEnum(AIRecommendationType, name="airecommendationtype", create_type=False), nullable=False)
    scope = Column(SAEnum(AIRecommendationScope, name="airecommendationscope", create_type=False), 
                   nullable=False, default=AIRecommendationScope.admin.value)
    
    # Confidence and content
    confidence = Column(Float, nullable=True)  # 0.0 - 1.0
    summary = Column(String(500), nullable=False)  # Short human-readable summary
    explanation = Column(Text, nullable=True)  # JSON array of explanation points
    data_refs = Column(Text, nullable=True)  # JSON object with referenced entity IDs
    
    # Generation metadata
    generated_by = Column(SAEnum(AIGenerationMode, name="aigenerationmode", create_type=False), 
                         nullable=False, default=AIGenerationMode.auto.value)
    
    # Lifecycle status (Phase 4.1)
    status = Column(SAEnum(AIRecommendationStatus, name="airecommendationstatus", create_type=False),
                   nullable=False, default=AIRecommendationStatus.pending.value)
    
    # Admin feedback (Phase 4.1)
    feedback_note = Column(Text, nullable=True)  # Admin comments on this recommendation
    feedback_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    feedback_at = Column(DateTime(timezone=True), nullable=True)
    
    # Governance tags (Phase 5.1)
    priority = Column(SAEnum(AIRecommendationPriority, name="airecommendationpriority", create_type=False),
                     nullable=True)  # Admin-assigned priority
    category = Column(SAEnum(AIRecommendationCategory, name="airecommendationcategory", create_type=False),
                     nullable=True)  # Business category
    risk_level = Column(SAEnum(AIRiskLevel, name="airisklevel", create_type=False),
                       nullable=True)  # Risk assessment
    assigned_to_id = Column(Integer, ForeignKey("users.id"), nullable=True)  # Owner/assignee
    tags = Column(Text, nullable=True)  # JSON array of custom tags
    governance_note = Column(Text, nullable=True)  # Admin governance notes
    
    # Dismissal tracking (legacy - consider using status=rejected instead)
    is_dismissed = Column(Boolean, default=False, nullable=False)
    dismissed_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    dismissed_at = Column(DateTime(timezone=True), nullable=True)
    
    # Expiration
    expires_at = Column(DateTime(timezone=True), nullable=True)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    dismissed_by = relationship("User", foreign_keys=[dismissed_by_id])
    feedback_by = relationship("User", foreign_keys=[feedback_by_id])
    assigned_to = relationship("User", foreign_keys=[assigned_to_id])  # Phase 5.1


