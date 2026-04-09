import { useAuthStore } from '../stores/authStore'

// ── Role-based UI capabilities (mirrors backend ROLE_PERMISSIONS) ────────────

interface UICapabilities {
  canManageUsers: boolean
  canBanUsers: boolean
  canViewSystemConsole: boolean
  canCreateChannels: boolean
}

const NO_CAPABILITIES: UICapabilities = {
  canManageUsers: false,
  canBanUsers: false,
  canViewSystemConsole: false,
  canCreateChannels: false,
}

/**
 * Derive UI capabilities from user object.
 * This is a pure function — no hooks, safe outside React.
 *
 * NOTE: UI visibility only. Backend is always the source of truth.
 */
export function getUserCapabilities(user: { role?: string; is_system_admin?: boolean } | null): UICapabilities {
  if (!user) return NO_CAPABILITIES

  const role = user.role
  const isSystemAdmin = user.is_system_admin === true

  return {
    canManageUsers: isSystemAdmin || role === 'system_admin' || role === 'team_admin',
    canBanUsers: isSystemAdmin || role === 'system_admin',
    canViewSystemConsole: isSystemAdmin || role === 'system_admin' || role === 'team_admin',
    canCreateChannels: true, // all authenticated users
  }
}

/**
 * React hook — reads user from authStore and returns capabilities.
 */
export function useUICapabilities(): UICapabilities {
  const user = useAuthStore((s) => s.user)
  return getUserCapabilities(user)
}

// ── Operational role permissions (unchanged) ─────────────────────────────────

export const NO_ACCESS = { tabs: [], sales: {} } as const

export const UI_PERMISSIONS = {
  admin: {
    tabs: ["orders", "sales", "tasks"],
    sales: {
      overview: true,
      record: true,
      agentPerformance: true,
      inventory: true,
      rawMaterials: true,
      transactions: true,
    },
  },
  sales_agent: {
    tabs: ["orders", "sales", "tasks"],
    sales: {
      overview: true,
      record: true,
      agentPerformance: false,
      inventory: false,
      rawMaterials: false,
      transactions: false,
    },
  },
  storekeeper: {
    tabs: ["orders", "sales", "tasks"],
    sales: {
      overview: true,
      record: true,
      agentPerformance: false,
      inventory: false,
      rawMaterials: false,
      transactions: false,
    },
  },
  foreman: {
    tabs: ["sales", "tasks"],
    sales: {
      overview: false,
      record: false,
      agentPerformance: false,
      inventory: true,
      rawMaterials: true,
      transactions: false,
    },
  },
  agent: {
    tabs: ["orders", "tasks"],
    sales: {
      overview: false,
      record: false,
      agentPerformance: false,
      inventory: false,
      rawMaterials: false,
      transactions: false,
    },
  },
  delivery: {
    tabs: ["tasks"],
    sales: {
      overview: false,
      record: false,
      agentPerformance: false,
      inventory: false,
      rawMaterials: false,
      transactions: false,
    },
  },
} as const;
