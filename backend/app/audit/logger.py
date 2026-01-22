from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.models import AuditLog


async def log_audit(
    db: AsyncSession,
    user,
    action: str,
    resource: str,
    resource_id: Optional[int] = None,
    success: bool = True,
    reason: Optional[str] = None,
    ip: Optional[str] = None,
):
    """Log an audit row for a privileged action."""
    try:
        entry = AuditLog(
            user_id=getattr(user, 'id', getattr(user, 'user_id', None)),
            role=getattr(user, 'operational_role_name', None),
            action=action,
            resource=resource,
            resource_id=resource_id,
            success=success,
            reason=reason,
            ip_address=ip,
        )
        db.add(entry)
        await db.commit()
    except Exception:
        # Fail silently - auditing should not break main flow
        try:
            await db.rollback()
        except Exception:
            pass
