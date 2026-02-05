import { useAuthStore } from '@/stores/authStore'
import { UI_PERMISSIONS, NO_ACCESS } from './uiPermissions'

// Authoritative resolver: read currentUser directly from the store state (non-subscribing)
// Uses operational_roles array from user_operational_roles table (source of truth)
export default function useOperationalPermissions() {
  const currentUser = useAuthStore.getState().currentUser

  // System admins always have full access
  if (currentUser?.is_system_admin) {
    return {
      tabs: ['orders', 'sales', 'tasks'] as string[],
      sales: (UI_PERMISSIONS as any).admin?.sales ?? {},
    }
  }

  // Use operational_roles array (from user_operational_roles table)
  const operationalRoles = currentUser?.operational_roles ?? []
  
  // Fallback to legacy operational_role_name if operational_roles is empty
  // This maintains backward compatibility during transition
  if (operationalRoles.length === 0 && currentUser?.operational_role_name) {
    const role = currentUser.operational_role_name
      .toLowerCase()
      .replace(/\\s+/g, '_')
    const perms = (UI_PERMISSIONS as any)[role]
    if (!perms) {
      console.error('[PERMS] Unknown legacy role:', role)
      return NO_ACCESS
    }
    return {
      tabs: perms.tabs ?? [],
      sales: perms.sales ?? {},
    }
  }

  if (operationalRoles.length === 0) {
    return NO_ACCESS
  }

  // Merge permissions from all operational roles
  const mergedTabs = new Set<string>()
  const mergedSales: Record<string, boolean> = {}

  for (const roleName of operationalRoles) {
    const role = roleName.toLowerCase().replace(/\\s+/g, '_')
    const perms = (UI_PERMISSIONS as any)[role]
    
    if (!perms) {
      console.error('[PERMS] Unknown operational role:', role)
      continue
    }

    // Merge tabs (union)
    for (const tab of (perms.tabs ?? [])) {
      mergedTabs.add(tab)
    }

    // Merge sales permissions (OR logic - any role grants access)
    for (const [key, value] of Object.entries(perms.sales ?? {})) {
      if (value === true) {
        mergedSales[key] = true
      } else if (!(key in mergedSales)) {
        mergedSales[key] = false
      }
    }
  }

  return {
    tabs: Array.from(mergedTabs),
    sales: mergedSales,
  }
}