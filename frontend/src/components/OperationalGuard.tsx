import { Outlet, Navigate } from 'react-router-dom'
import { useAuthStore } from '../stores/authStore'
import useOperationalPermissions from '../permissions/useOperationalPermissions'
import { NO_ACCESS } from '../permissions/uiPermissions'

interface OperationalGuardProps {
  tab: 'Orders' | 'Sales' | 'Tasks'
}

export default function OperationalGuard({ tab }: OperationalGuardProps) {
  const auth = useAuthStore((s) => ({ _hasHydrated: s._hasHydrated, currentUser: s.currentUser }))
  const perms = useOperationalPermissions()

  // BEFORE redirecting: wait until auth has hydrated and permissions have resolved
  if (!auth._hasHydrated) return null
  if (!perms || perms === NO_ACCESS) return null

  // Validate access strictly at the tab level using perms.tabs
  const tabKey = tab.toLowerCase() as 'orders' | 'sales' | 'tasks'

  // TEMP: Do not enforce OperationalGuard for sales routes during stabilization
  if (tabKey === 'sales') {
    return <Outlet />
  }

  if (!perms.tabs.includes(tabKey)) {
    // Role does not have this tab permission
    return <Navigate to="/unauthorized" replace />
  }

  return <Outlet />
}
