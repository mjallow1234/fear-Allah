from sqlalchemy import Column, Integer, String, ForeignKey, UniqueConstraint, Index
from sqlalchemy.orm import relationship
from app.db.database import Base


class UserOperationalRole(Base):
    __tablename__ = "user_operational_roles"
    __table_args__ = (
        UniqueConstraint("user_id", "role", name="uq_user_operational_role"),
        Index("ix_user_operational_roles_user_id", "user_id"),
    )

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    role = Column(String(50), nullable=False)

    # Relationship back to User (string name to avoid circular import issues)
    user = relationship("User", back_populates="operational_roles")
