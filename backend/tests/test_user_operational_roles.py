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


@pytest.mark.anyio
async def test_backfill_and_normalize_roles(test_session: object):
    """Backfill operational roles from User.role and normalize users.role to 'member'."""
    from app.db.models import User, UserOperationalRole
    from sqlalchemy import text, select

    # Create users with different roles
    admin = User(username='uadmin', email='uadmin@example.com', hashed_password='pw', role='system_admin')
    foreman = User(username='uforeman', email='uforeman@example.com', hashed_password='pw', role='foreman')
    delivery = User(username='udelivery', email='udelivery@example.com', hashed_password='pw', role='delivery')
    member = User(username='umember', email='umember@example.com', hashed_password='pw', role='member')

    test_session.add_all([admin, foreman, delivery, member])
    await test_session.commit()
    await test_session.refresh(admin)
    await test_session.refresh(foreman)
    await test_session.refresh(delivery)
    await test_session.refresh(member)

    # Run the migration SQL (same logic as Alembic migration)
    dialect = test_session.bind.dialect.name
    if dialect == 'postgresql':
        await test_session.execute(text("""
            INSERT INTO user_operational_roles (user_id, role)
            SELECT id, role FROM users WHERE role NOT IN ('system_admin', 'team_admin', 'member')
            ON CONFLICT (user_id, role) DO NOTHING
        """))
    else:
        # SQLite: INSERT OR IGNORE
        await test_session.execute(text("""
            INSERT OR IGNORE INTO user_operational_roles (user_id, role)
            SELECT id, role FROM users WHERE role NOT IN ('system_admin', 'team_admin', 'member')
        """))

    await test_session.execute(text("""
        UPDATE users
        SET role = 'member'
        WHERE role NOT IN ('system_admin', 'team_admin', 'member')
    """))
    await test_session.commit()

    # Validate foreman was normalized and got an operational role
    # Use raw SQL to inspect stored DB values (avoids enum-to-string comparison issues)
    raw_f = await test_session.execute(text("SELECT role FROM users WHERE id = :id"), {'id': foreman.id})
    raw_f_role = raw_f.scalar_one()
    assert raw_f_role == 'member'

    role_rows = await test_session.execute(select(UserOperationalRole).where(UserOperationalRole.user_id == foreman.id))
    role_list = [r.role for r in role_rows.scalars().all()]
    assert 'foreman' in role_list

    # Admin unchanged and has no operational role row
    raw_a = await test_session.execute(text("SELECT role FROM users WHERE id = :id"), {'id': admin.id})
    raw_a_role = raw_a.scalar_one()
    assert raw_a_role == 'system_admin'

    a_roles = await test_session.execute(select(UserOperationalRole).where(UserOperationalRole.user_id == admin.id))
    assert a_roles.scalars().first() is None

    # Idempotency: run migration SQL again and ensure no duplicates and same results
    if dialect == 'postgresql':
        await test_session.execute(text("""
            INSERT INTO user_operational_roles (user_id, role)
            SELECT id, role FROM users WHERE role NOT IN ('system_admin', 'team_admin', 'member')
            ON CONFLICT (user_id, role) DO NOTHING
        """))
    else:
        await test_session.execute(text("""
            INSERT OR IGNORE INTO user_operational_roles (user_id, role)
            SELECT id, role FROM users WHERE role NOT IN ('system_admin', 'team_admin', 'member')
        """))
    await test_session.execute(text("""
        UPDATE users
        SET role = 'member'
        WHERE role NOT IN ('system_admin', 'team_admin', 'member')
    """))
    await test_session.commit()

    # No additional duplicates
    role_rows2 = await test_session.execute(select(UserOperationalRole).where(UserOperationalRole.user_id == foreman.id))
    assert len(role_rows2.scalars().all()) == 1
