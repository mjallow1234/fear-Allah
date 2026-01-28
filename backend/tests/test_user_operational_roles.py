import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError


@pytest.mark.anyio
async def test_user_operational_roles_relationship(test_session: object):
    """Ensure User <-> UserOperationalRole relationship and helper work."""
    from app.db.models import User, UserOperationalRole

    # Create a user
    u = User(username='op_user', email='op@example.com', hashed_password='pw', role='member')
    test_session.add(u)
    await test_session.commit()
    await test_session.refresh(u)

    # Add an operational role
    r = UserOperationalRole(user_id=u.id, role='foreman')
    test_session.add(r)
    await test_session.commit()
    await test_session.refresh(r)
    await test_session.refresh(u)

    assert any(rr.role == 'foreman' for rr in u.operational_roles)
    assert u.has_operational_role('foreman') is True

    # Unique constraint should prevent duplicate role
    dup = UserOperationalRole(user_id=u.id, role='foreman')
    test_session.add(dup)
    with pytest.raises(IntegrityError):
        await test_session.commit()
    # Rollback session after integrity error
    await test_session.rollback()
