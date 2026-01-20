import { Outlet, Navigate } from 'react-router-dom'
import { useAuthStore } from '../stores/authStore'
import useOperationalPermissions from '../permissions/useOperationalPermissions'

interface OperationalGuardProps {
  tab: 'Orders' | 'Sales' | 'Tasks'
}

export default function OperationalGuard({ tab }: OperationalGuardProps) {
  const currentUser = useAuthStore((s) => s.currentUser)
  // Do NOT block while auth is loading — return null so UI can render a loading state / avoid lockout
  if (!currentUser) {
    return null
  }

  const perms = useOperationalPermissions()

  // Validate access strictly at the tab level using perms.tabs
  const tabKey = tab.toLowerCase() as 'orders' | 'sales' | 'tasks'
  if (!perms.tabs.includes(tabKey)) {
    // Role does not have this tab permission
    return <Navigate to="/unauthorized" replace />
  }

  return <Outlet />
}
