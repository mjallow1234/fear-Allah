import { useAuthStore } from '@/stores/authStore'
import { UI_PERMISSIONS, NO_ACCESS } from './uiPermissions'

// Single-source-of-truth resolver: always read currentUser from the auth store.
// No parameters allowed — callers must not pass a user or props here.
export default function useOperationalPermissions() {
  const currentUser = useAuthStore((s) => s.currentUser)

  if (!currentUser?.operational_role_name) {
    return NO_ACCESS
  }

  const normalizedRole = currentUser.operational_role_name
    .toLowerCase()
    .replace(/\s+/g, '_')

  return UI_PERMISSIONS[normalizedRole] ?? NO_ACCESS
}