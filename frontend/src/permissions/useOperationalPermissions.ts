import { UI_PERMISSIONS, NO_ACCESS } from './operationalPermissions'

export function resolveOperationalPermissions(currentUser?: { operational_role_name?: string, operational_role?: string }) {
  const role = currentUser?.operational_role_name ?? currentUser?.operational_role ?? null
  if (!role) return NO_ACCESS

  const normalizedRole = role
    ?.toLowerCase()
    .replace(/\s+/g, '_')

  const rolePerms = UI_PERMISSIONS[normalizedRole]

  if (rolePerms) {
    return { ...rolePerms, tabs: rolePerms.tabs ?? [] }
  }
  return NO_ACCESS
}

// Default export kept for convenience, but REQUIRE caller to pass currentUser to avoid importing the auth store here
export default function useOperationalPermissions(currentUser?: { operational_role_name?: string }) {
  return resolveOperationalPermissions(currentUser)
}