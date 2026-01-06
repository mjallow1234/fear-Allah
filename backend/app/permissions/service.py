from .constants import Permission
from .roles import SystemRole, ChannelRole
from .role_map import SYSTEM_ROLE_PERMISSIONS, CHANNEL_ROLE_PERMISSIONS


class PermissionService:
    """Resolve effective permissions for a user in a given context."""

    @staticmethod
    def has_permission(
        permission: Permission,
        system_roles: list[SystemRole] | None = None,
        channel_roles: list[ChannelRole] | None = None,
    ) -> bool:
        """
        Check if user has permission based on their roles.
        Returns True if ANY role grants the permission.
        Admins get all channel permissions.
        """
        system_roles = system_roles or []
        channel_roles = channel_roles or []

        # Collect all permissions from system roles
        all_perms: set[Permission] = set()
        for sr in system_roles:
            all_perms |= SYSTEM_ROLE_PERMISSIONS.get(sr, set())
            # Admins get all channel permissions
            if sr in (SystemRole.SUPER_ADMIN, SystemRole.ADMIN):
                all_perms |= CHANNEL_ROLE_PERMISSIONS[ChannelRole.OWNER]

        # Collect all permissions from channel roles
        for cr in channel_roles:
            all_perms |= CHANNEL_ROLE_PERMISSIONS.get(cr, set())

        return permission in all_perms

    def has_system_permission(
        self,
        system_role: SystemRole,
        permission: Permission,
    ) -> bool:
        """Check system-level permission based on user's system role."""
        perms = SYSTEM_ROLE_PERMISSIONS.get(system_role, set())
        return permission in perms

    def has_channel_permission(
        self,
        channel_role: ChannelRole,
        permission: Permission,
    ) -> bool:
        """Check channel-level permission based on membership role."""
        perms = CHANNEL_ROLE_PERMISSIONS.get(channel_role, set())
        return permission in perms

    def get_effective_channel_permissions(
        self,
        system_role: SystemRole,
        channel_role: ChannelRole | None,
    ) -> set[Permission]:
        """
        Return union of system + channel permissions.
        Admins get elevated channel perms regardless of membership.
        """
        base = SYSTEM_ROLE_PERMISSIONS.get(system_role, set()).copy()
        if channel_role:
            base |= CHANNEL_ROLE_PERMISSIONS.get(channel_role, set())
        # Super-admin / admin override: grant all channel perms
        if system_role in (SystemRole.SUPER_ADMIN, SystemRole.ADMIN):
            base |= CHANNEL_ROLE_PERMISSIONS[ChannelRole.OWNER]
        return base


permission_service = PermissionService()
