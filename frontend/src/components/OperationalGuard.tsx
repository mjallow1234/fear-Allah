import { Outlet, Navigate } from 'react-router-dom'
import { useAuthStore } from '../stores/authStore'
import useOperationalPermissions from '../permissions/useOperationalPermissions'

interface OperationalGuardProps {
  tab: 'Orders' | 'Sales' | 'Tasks'
}

export default function OperationalGuard({ tab }: OperationalGuardProps) {
  const currentUser = useAuthStore((s) => s.currentUser)
  const hasHydrated = useAuthStore((s) => s._hasHydrated)
  const perms = useOperationalPermissions()

  // Timing guard: while auth is hydrating or permissions are not yet resolved for a user with a role, DO NOT redirect
  if (!currentUser || !hasHydrated) {
    return null
  }

  if (currentUser.operational_role_name && (!perms?.tabs || perms.tabs.length === 0)) {
    // Permissions not yet resolved for this role; avoid premature redirect
    return null
  }

  // Validate access strictly at the tab level using perms.tabs
  const tabKey = tab.toLowerCase() as 'orders' | 'sales' | 'tasks'
  if (!perms.tabs.includes(tabKey)) {
    // Role does not have this tab permission
    return <Navigate to="/unauthorized" replace />
  }

  return <Outlet />
}
