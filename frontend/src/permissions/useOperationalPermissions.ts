import { UI_PERMISSIONS, NO_ACCESS } from './operationalPermissions'

export function resolveOperationalPermissions(currentUser?: { operational_role_name?: string }) {
  const role = currentUser?.operational_role_name
  if (!role) return NO_ACCESS
  return UI_PERMISSIONS[role] ?? NO_ACCESS
}

// Default export kept for convenience, but REQUIRE caller to pass currentUser to avoid importing the auth store here
export default function useOperationalPermissions(currentUser?: { operational_role_name?: string }) {
  return resolveOperationalPermissions(currentUser)
}