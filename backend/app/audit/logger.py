from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.models import AuditLog
from app.db.database import async_session


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
    """Log an audit row for a privileged action.

    Uses a separate short-lived session to ensure audit writes are independent
    from the caller's transaction (so denials are still recorded even if the
    caller's transaction is rolled back).
    """
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
        # Use independent session for audit to avoid being rolled back with caller
        async with async_session() as s:
            s.add(entry)
            await s.commit()
    except Exception:
        # Fail silently - auditing should not break main flow
        try:
            async with async_session() as s:
                await s.rollback()
        except Exception:
            pass
