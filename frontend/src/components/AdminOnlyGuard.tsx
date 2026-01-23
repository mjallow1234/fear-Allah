import { Navigate } from 'react-router-dom'
import { useAuthStore } from '../stores/authStore'

export default function AdminOnlyGuard({ children }: { children: React.ReactNode }) {
  const currentUser = useAuthStore((s) => s.currentUser)
  const _hasHydrated = useAuthStore((s) => s._hasHydrated)

  // Wait until auth has hydrated
  if (!_hasHydrated) return null

  const isAdmin = currentUser?.is_system_admin || currentUser?.operational_role_name === 'admin'

  if (!isAdmin) return <Navigate to="/unauthorized" replace />

  return <>{children}</>
}
