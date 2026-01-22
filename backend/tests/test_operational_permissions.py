import pytest
from types import SimpleNamespace

from app.permissions.operational_permissions import OPERATIONAL_PERMISSIONS, resolve_permissions


@pytest.mark.parametrize("role", list(OPERATIONAL_PERMISSIONS.keys()))
def test_resolve_permissions_for_role(role):
    """Each defined operational role should return the expected permission map."""
    user = SimpleNamespace(id=1, operational_role_name=role, is_system_admin=False)
    perms = resolve_permissions(user)
    assert perms == OPERATIONAL_PERMISSIONS[role]


def test_resolve_permissions_system_admin_overrides_role():
    """System admins should always be treated as operational admin."""
    # System admin with no operational_role_name
    user = SimpleNamespace(id=2, operational_role_name=None, is_system_admin=True)
    perms = resolve_permissions(user)
    assert perms == OPERATIONAL_PERMISSIONS["admin"]

    # System admin with a different role set - still treated as admin
    user2 = SimpleNamespace(id=3, operational_role_name='foreman', is_system_admin=True)
    perms2 = resolve_permissions(user2)
    assert perms2 == OPERATIONAL_PERMISSIONS["admin"]


def test_resolve_permissions_no_role_returns_empty_dict():
    user = SimpleNamespace(id=4, operational_role_name=None, is_system_admin=False)
    perms = resolve_permissions(user)
    assert perms == {}
