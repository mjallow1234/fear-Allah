from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Text, Index
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.database import Base
from app.db.enums import (
    UserStatus, UserRole, ChannelType, NotificationType, 
    OrderStatus, TaskStatus, OrderType, SaleChannel,
    AutomationTaskType, AutomationTaskStatus, AssignmentStatus, TaskEventType
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
    __tablename__ = "file_attachments"
    
    id = Column(Integer, primary_key=True, index=True)
    message_id = Column(Integer, ForeignKey("messages.id"), nullable=True)
    channel_id = Column(Integer, ForeignKey("channels.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    filename = Column(String(255), nullable=False)
    file_path = Column(String(500), nullable=False)
    file_size = Column(Integer)
    mime_type = Column(String(100))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    user = relationship("User")
    channel = relationship("Channel")


class MessageReaction(Base):
    __tablename__ = "message_reactions"
    
    id = Column(Integer, primary_key=True, index=True)
    message_id = Column(Integer, ForeignKey("messages.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    emoji = Column(String(50), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    message = relationship("Message", back_populates="reactions")
    user = relationship("User")


class Notification(Base):
    __tablename__ = "notifications"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    type = Column(SAEnum(NotificationType, name="notificationtype", create_type=False), nullable=False)
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
    __tablename__ = "audit_logs"
    __table_args__ = (
        Index("ix_audit_logs_user_id", "user_id"),
        Index("ix_audit_logs_created_at", "created_at"),
    )
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    action = Column(String(100), nullable=False)
    target_type = Column(String(50))  # message, channel, user, file, etc.
    target_id = Column(Integer)
    meta = Column(Text)  # JSON details
    ip_address = Column(String(50))
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
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

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
    total_stock = Column(Integer, default=0, nullable=False)
    total_sold = Column(Integer, default=0, nullable=False)
    low_stock_threshold = Column(Integer, default=10, nullable=False)  # Trigger threshold
    version = Column(Integer, default=1)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    transactions = relationship("InventoryTransaction", back_populates="inventory_item", cascade="all, delete-orphan")

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
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    sold_by = relationship("User")
    related_order = relationship("Order")
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
    reason = Column(String(50), nullable=False)  # sale, restock, adjustment, return
    related_sale_id = Column(Integer, ForeignKey("sales.id"), nullable=True)
    related_order_id = Column(Integer, ForeignKey("orders.id"), nullable=True)
    performed_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    inventory_item = relationship("Inventory", back_populates="transactions")
    related_sale = relationship("Sale", back_populates="transaction")
    related_order = relationship("Order")
    performed_by = relationship("User")


# ------------------ Permissions & Roles (Phase 5.2) ------------------
from sqlalchemy import UniqueConstraint


class Role(Base):
    __tablename__ = "roles"

    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False, unique=True)
    scope = Column(String, nullable=False)  # system | channel

    permissions = relationship(
        "RolePermission",
        back_populates="role",
        cascade="all, delete-orphan",
    )


class PermissionModel(Base):
    __tablename__ = "permissions"

    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False, unique=True)


class RolePermission(Base):
    __tablename__ = "role_permissions"

    role_id = Column(Integer, ForeignKey("roles.id"), primary_key=True)
    permission_id = Column(Integer, ForeignKey("permissions.id"), primary_key=True)

    role = relationship("Role", back_populates="permissions")
    permission = relationship("PermissionModel")


class UserRole(Base):
    __tablename__ = "user_roles"

    user_id = Column(Integer, ForeignKey("users.id"), primary_key=True)
    role_id = Column(Integer, ForeignKey("roles.id"), primary_key=True)

    role = relationship("Role")

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
    status = Column(SAEnum(AutomationTaskStatus, name="automationtaskstatus", create_type=False), nullable=False, default=AutomationTaskStatus.pending.value)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    created_by_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    related_order_id = Column(Integer, ForeignKey("orders.id"), nullable=True)
    task_metadata = Column(Text, nullable=True)  # JSON for extensibility (named task_metadata to avoid SQLAlchemy reserved name)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

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
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
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
    event_type = Column(SAEnum(TaskEventType, name="taskeventtype", create_type=False), nullable=False)
    event_metadata = Column(Text, nullable=True)  # JSON for event-specific data (named event_metadata to avoid SQLAlchemy reserved name)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    task = relationship("AutomationTask", back_populates="events")
    user = relationship("User")
