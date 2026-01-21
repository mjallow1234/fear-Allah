import { useAuthStore } from '@/stores/authStore'
import { UI_PERMISSIONS, NO_ACCESS } from './uiPermissions'

// Authoritative resolver: read currentUser directly from the store state (non-subscribing)
export default function useOperationalPermissions() {
  const currentUser = useAuthStore.getState().currentUser

  if (!currentUser?.operational_role_name) {
    return NO_ACCESS
  }

  const role = currentUser.operational_role_name
    .toLowerCase()
    .replace(/\s+/g, '_')

  const perms = (UI_PERMISSIONS as any)[role]
  if (!perms) {
    // Unknown role — log once and deny access
    // Keep log minimal to avoid console spam
    console.error('[PERMS] Unknown role:', role)
    return NO_ACCESS
  }

  return {
    tabs: perms.tabs ?? [],
    sales: perms.sales ?? {},
  }
}