import { useAuthStore } from '../stores/authStore'
import { UI_PERMISSIONS, NO_ACCESS } from './operationalPermissions'

export default function useOperationalPermissions() {
  const currentUser = useAuthStore((s) => s.currentUser)
  const role = currentUser?.operational_role_name
  if (!role) return NO_ACCESS
  return UI_PERMISSIONS[role] ?? NO_ACCESS
}