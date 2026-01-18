/**
 * System Store for admin system console management.
 * Phase 8.4 - System Console
 * Phase 8.4.4 - Once-per-session guards and 429 handling
 * Phase 8.5.3 - Full admin actions (user management, role management)
 * 
 * Manages system users, roles, permissions, settings, and stats.
 */
import { create } from 'zustand'
import api from '../services/api'
import axios from 'axios'

// === Types ===

export interface SystemUser {
  id: number
  username: string
  email: string
  display_name: string | null
  role: string
  is_active: boolean
  is_system_admin: boolean
  is_banned: boolean
  is_muted: boolean
  created_at: string | null
}

// Phase 8.5.2: Updated RoleInfo with full backend model
export interface RoleInfo {
  id: number
  name: string
  description: string | null
  scope: string
  is_system: boolean
  permissions: string[]
  created_at: string | null
}

// Phase 8.5.2: Updated PermissionInfo with full backend model
export interface PermissionInfo {
  id: number
  key: string
  name: string
  description: string | null
}

export interface SystemSettings {
  app_name: string
  environment: string
  features: {
    websockets_enabled: boolean
    automations_enabled: boolean
    rate_limiting_enabled: boolean
  }
  upload_limits: {
    max_upload_mb: number
  }
  rate_limits: {
    auth: {
      anonymous: string
      authenticated: string
      admin: string
    }
    api: {
      anonymous: string
      authenticated: string
      admin: string
    }
    sales: {
      anonymous: string
      authenticated: string
      admin: string
    }
  }
}

export interface SystemStats {
  users: {
    total: number
    active: number
    admins: number
    banned: number
  }
  channels: {
    total: number
  }
  messages: {
    total: number
  }
  teams: {
    total: number
  }
  audit: {
    last_24h: number
  }
}

interface UserFilters {
  search?: string
  role?: string
  status?: string
}

interface SystemState {
  // Users
  users: SystemUser[]
  usersTotal: number
  usersPage: number
  usersLimit: number
  userFilters: UserFilters
  usersLoading: boolean
  
  // Roles & Permissions
  roles: RoleInfo[]
  operationalRoles: RoleInfo[]
  permissions: PermissionInfo[]
  rolesLoading: boolean
  operationalRolesLoading: boolean
  
  // Settings
  settings: SystemSettings | null
  settingsLoading: boolean
  
  // Stats
  stats: SystemStats | null
  statsLoading: boolean
  
  // Error
  error: string | null
  
  // Phase 8.4.4: Rate limit state
  rateLimited: boolean
  rateLimitRetryAt: number | null
  
  // Phase 8.4.4: Once-per-session fetch guards (private flags)
  _statsFetched: boolean
  _usersFetched: boolean
  _rolesFetched: boolean
  _permissionsFetched: boolean
  _settingsFetched: boolean
  
  // In-flight guards
  _fetchingStats: boolean
  _fetchingUsers: boolean
  _fetchingRoles: boolean
  _fetchingPermissions: boolean
  _fetchingSettings: boolean
  
  // User Actions
  setUsersPage: (page: number) => void
  setUserFilters: (filters: Partial<UserFilters>) => void
  clearUserFilters: () => void
  fetchUsers: (force?: boolean) => Promise<void>
  updateUser: (userId: number, data: { is_active?: boolean; is_system_admin?: boolean; role?: string }) => Promise<void>
  resetUserPassword: (userId: number) => Promise<string>
  forceLogoutUser: (userId: number) => Promise<void>
  
  // Phase 8.5.5: Admin creates user
  createUser: (data: {
    username: string
    email: string | null
    role_id: number
    operational_role_id?: number | null
    is_system_admin: boolean
    active: boolean
  }) => Promise<{ user: { id: number; username: string; email: string; active: boolean; is_system_admin: boolean; role_id: number; role_name: string; operational_role_id?: number | null; operational_role_name?: string | null }; temporary_password: string }>
  
  assignOperationalRole: (userId: number, operationalRoleId: number | null) => Promise<{ changed: boolean; message: string }>
  
  // Phase 8.5.3: New user action methods
  setUserStatus: (userId: number, active: boolean) => Promise<{ changed: boolean; message: string }>
  setUserAdmin: (userId: number, isAdmin: boolean) => Promise<{ changed: boolean; message: string }>
  assignUserRole: (userId: number, roleId: number) => Promise<{ changed: boolean; message: string }>
  
  // Roles & Permissions Actions
  fetchRoles: (force?: boolean) => Promise<void>
  fetchPermissions: (force?: boolean) => Promise<void>
  updateRolePermissions: (roleName: string, permissions: string[]) => Promise<void>
  
  // Phase 8.5.3: New role management methods
  createRole: (name: string, description: string, permissions: string[]) => Promise<RoleInfo>
  updateRolePermissionsById: (roleId: number, permissions: string[]) => Promise<{ changed: boolean; added: string[]; removed: string[] }>
  deleteRole: (roleId: number) => Promise<{ deleted: boolean; message: string }>
  getRoleUsersCount: (roleId: number) => Promise<number>
  
  // Settings Actions
  fetchSettings: (force?: boolean) => Promise<void>
  
  // Stats Actions
  fetchStats: (force?: boolean) => Promise<void>
  
  // Reset session flags (for manual refresh)
  resetSessionFlags: () => void
}

const initialUserFilters: UserFilters = {
  search: '',
  role: '',
  status: '',
}

// Helper to check if response is 429 rate limit
const isRateLimitError = (err: unknown): { retryAfter: number } | null => {
  if (axios.isAxiosError(err) && err.response?.status === 429) {
    const retryAfter = parseInt(err.response.headers['retry-after'] || '60', 10)
    return { retryAfter }
  }
  return null
}

export const useSystemStore = create<SystemState>((set, get) => ({
  // Initial state
  users: [],
  usersTotal: 0,
  usersPage: 1,
  usersLimit: 50,
  userFilters: { ...initialUserFilters },
  usersLoading: false,
  
  roles: [],
  operationalRoles: [],
  permissions: [],
  rolesLoading: false,
  operationalRolesLoading: false,
  
  settings: null,
  settingsLoading: false,
  
  stats: null,
  statsLoading: false,
  
  error: null,
  
  // Phase 8.4.4: Rate limit state
  rateLimited: false,
  rateLimitRetryAt: null,
  
  // Phase 8.4.4: Once-per-session fetch guards
  _statsFetched: false,
  _usersFetched: false,
  _rolesFetched: false,
  _operationalRolesFetched: false,
  _permissionsFetched: false,
  _settingsFetched: false,
  
  // In-flight guards
  _fetchingStats: false,
  _fetchingUsers: false,
  _fetchingRoles: false,
  _fetchingOperationalRoles: false,
  _fetchingPermissions: false,
  _fetchingSettings: false,
  
  // User Actions
  setUsersPage: (page) => {
    set({ usersPage: page })
    get().fetchUsers(true)  // Force refresh on page change
  },
  
  setUserFilters: (filters) => {
    set({ 
      userFilters: { ...get().userFilters, ...filters },
      usersPage: 1
    })
    get().fetchUsers(true)  // Force refresh on filter change
  },
  
  clearUserFilters: () => {
    set({ userFilters: { ...initialUserFilters }, usersPage: 1 })
    get().fetchUsers(true)  // Force refresh on filter clear
  },
  
  fetchUsers: async (force = false) => {
    const { _usersFetched, _fetchingUsers, rateLimited } = get()
    
    // Skip if rate limited
    if (rateLimited && !force) {
      console.log('[SystemStore] Skipping fetchUsers - rate limited')
      return
    }
    
    // Skip if already fetched this session (unless forced)
    if (_usersFetched && !force) {
      console.log('[SystemStore] Skipping fetchUsers - already fetched')
      return
    }
    
    // Skip if already in-flight
    if (_fetchingUsers) {
      console.log('[SystemStore] Skipping fetchUsers - in-flight')
      return
    }
    
    const { usersPage, usersLimit, userFilters } = get()
    set({ usersLoading: true, _fetchingUsers: true, error: null })
    
    try {
      const params = new URLSearchParams()
      params.append('page', String(usersPage))
      params.append('limit', String(usersLimit))
      
      if (userFilters.search) params.append('search', userFilters.search)
      if (userFilters.role) params.append('role', userFilters.role)
      if (userFilters.status) params.append('status', userFilters.status)
      
      const response = await api.get(`/api/system/users?${params}`)
      set({
        users: response.data.users,
        usersTotal: response.data.total,
        usersLoading: false,
        _fetchingUsers: false,
        _usersFetched: true,
        rateLimited: false,
      })
    } catch (err) {
      console.error('[SystemStore] Failed to fetch users:', err)
      
      // Check for 429 rate limit
      const rateLimit = isRateLimitError(err)
      if (rateLimit) {
        set({ 
          rateLimited: true,
          rateLimitRetryAt: Date.now() + rateLimit.retryAfter * 1000,
          usersLoading: false,
          _fetchingUsers: false,
        })
        return
      }
      
      // Defensive: show empty state, don't throw
      set({ 
        users: [],
        usersTotal: 0,
        error: err instanceof Error ? err.message : 'Failed to fetch users',
        usersLoading: false,
        _fetchingUsers: false,
      })
    }
  },
  
  updateUser: async (userId, data) => {
    try {
      await api.patch(`/api/system/users/${userId}`, data)
      // Refresh user list
      await get().fetchUsers(true)
      // Refresh stats
      await get().fetchStats(true)
    } catch (err) {
      console.error('[SystemStore] Failed to update user:', err)
      throw err
    }
  },
  
  // Phase 8.5.3: Dedicated user status endpoint
  setUserStatus: async (userId, active) => {
    try {
      const response = await api.patch(`/api/system/users/${userId}/status`, { active })
      // Refresh user list and stats
      await get().fetchUsers(true)
      await get().fetchStats(true)
      return { changed: response.data.changed, message: response.data.message }
    } catch (err) {
      console.error('[SystemStore] Failed to set user status:', err)
      throw err
    }
  },
  
  // Phase 8.5.3: Dedicated admin promotion/demotion endpoint
  setUserAdmin: async (userId, isAdmin) => {
    try {
      const response = await api.patch(`/api/system/users/${userId}/admin`, { is_system_admin: isAdmin })
      // Refresh user list and stats
      await get().fetchUsers(true)
      await get().fetchStats(true)
      return { changed: response.data.changed, message: response.data.message }
    } catch (err) {
      console.error('[SystemStore] Failed to set user admin status:', err)
      throw err
    }
  },
  
  // Phase 8.5.3: Assign role to user via new endpoint
  assignUserRole: async (userId, roleId) => {
    try {
      const response = await api.patch(`/api/system/users/${userId}/assign-role`, { role_id: roleId })
      // Refresh user list
      await get().fetchUsers(true)
      return { changed: response.data.changed, message: response.data.message }
    } catch (err) {
      console.error('[SystemStore] Failed to assign user role:', err)
      throw err
    }
  },
  
  resetUserPassword: async (userId) => {
    try {
      const response = await api.post(`/api/system/users/${userId}/reset-password`)
      return response.data.temporary_password
    } catch (err) {
      console.error('[SystemStore] Failed to reset password:', err)
      throw err
    }
  },
  
  forceLogoutUser: async (userId) => {
    try {
      await api.post(`/api/system/users/${userId}/force-logout`)
    } catch (err) {
      console.error('[SystemStore] Failed to force logout:', err)
      throw err
    }
  },
  
  // Phase 8.5.5: Admin creates new user
  createUser: async (data) => {
    try {
      const response = await api.post('/api/system/users', data)
      // Refresh user list and stats after creation
      await get().fetchUsers(true)
      await get().fetchStats(true)
      return response.data
    } catch (err) {
      console.error('[SystemStore] Failed to create user:', err)
      throw err
    }
  },

  assignOperationalRole: async (userId, operationalRoleId) => {
    try {
      const response = await api.patch(`/api/system/users/${userId}/operational-role`, { operational_role_id: operationalRoleId })
      await get().fetchUsers(true)
      return { changed: response.data.changed, message: response.data.message }
    } catch (err) {
      console.error('[SystemStore] Failed to set operational role:', err)
      throw err
    }
  },
  
  // Roles & Permissions Actions
  fetchRoles: async (force = false) => {
    const { _rolesFetched, _fetchingRoles, rateLimited } = get()
    
    // Skip if rate limited
    if (rateLimited && !force) {
      console.log('[SystemStore] Skipping fetchRoles - rate limited')
      return
    }
    
    // Skip if already fetched this session (unless forced)
    if (_rolesFetched && !force) {
      console.log('[SystemStore] Skipping fetchRoles - already fetched')
      return
    }
    
    // Skip if already in-flight
    if (_fetchingRoles) {
      console.log('[SystemStore] Skipping fetchRoles - in-flight')
      return
    }
    
    set({ rolesLoading: true, _fetchingRoles: true, error: null })
    try {
      const response = await api.get('/api/system/roles')
      // Phase 8.5.3: Backend now returns { roles: [...], total: N }
      const rolesData = response.data.roles || response.data || []
      set({ 
        roles: rolesData, 
        rolesLoading: false,
        _fetchingRoles: false,
        _rolesFetched: true,
        rateLimited: false,
      })
    } catch (err) {
      console.error('[SystemStore] Failed to fetch roles:', err)
      
      // Check for 429 rate limit
      const rateLimit = isRateLimitError(err)
      if (rateLimit) {
        set({ 
          rateLimited: true,
          rateLimitRetryAt: Date.now() + rateLimit.retryAfter * 1000,
          rolesLoading: false,
          _fetchingRoles: false,
        })
        return
      }
      
      // Defensive: show empty state, don't throw
      set({ 
        roles: [],
        error: err instanceof Error ? err.message : 'Failed to fetch roles',
        rolesLoading: false,
        _fetchingRoles: false,
      })
    }
  },

  // New: fetch operational roles only (admin-only)
  fetchOperationalRoles: async (force = false) => {
    const { _operationalRolesFetched, _fetchingOperationalRoles, rateLimited } = get()

    if (rateLimited && !force) {
      console.log('[SystemStore] Skipping fetchOperationalRoles - rate limited')
      return
    }

    if (_operationalRolesFetched && !force) {
      console.log('[SystemStore] Skipping fetchOperationalRoles - already fetched')
      return
    }

    if (_fetchingOperationalRoles) {
      console.log('[SystemStore] Skipping fetchOperationalRoles - in-flight')
      return
    }

    set({ operationalRolesLoading: true, _fetchingOperationalRoles: true, error: null })
    try {
      const response = await api.get('/api/system/roles/operational')
      const rolesData = response.data.roles || response.data || []
      set({
        operationalRoles: rolesData,
        operationalRolesLoading: false,
        _fetchingOperationalRoles: false,
        _operationalRolesFetched: true,
        rateLimited: false,
      })
    } catch (err) {
      console.error('[SystemStore] Failed to fetch operational roles:', err)
      const rateLimit = isRateLimitError(err)
      if (rateLimit) {
        set({
          rateLimited: true,
          rateLimitRetryAt: Date.now() + rateLimit.retryAfter * 1000,
          operationalRolesLoading: false,
          _fetchingOperationalRoles: false,
        })
        return
      }

      set({
        operationalRoles: [],
        error: err instanceof Error ? err.message : 'Failed to fetch operational roles',
        operationalRolesLoading: false,
        _fetchingOperationalRoles: false,
      })
    }
  },
  
  fetchPermissions: async (force = false) => {
    const { _permissionsFetched, _fetchingPermissions, rateLimited } = get()
    
    // Skip if rate limited
    if (rateLimited && !force) {
      console.log('[SystemStore] Skipping fetchPermissions - rate limited')
      return
    }
    
    // Skip if already fetched this session (unless forced)
    if (_permissionsFetched && !force) {
      console.log('[SystemStore] Skipping fetchPermissions - already fetched')
      return
    }
    
    // Skip if already in-flight
    if (_fetchingPermissions) {
      console.log('[SystemStore] Skipping fetchPermissions - in-flight')
      return
    }
    
    set({ _fetchingPermissions: true })
    try {
      const response = await api.get('/api/system/permissions')
      // Phase 8.5.3: Backend now returns { permissions: [...], total: N }
      const permsData = response.data.permissions || response.data || []
      set({ 
        permissions: permsData,
        _fetchingPermissions: false,
        _permissionsFetched: true,
        rateLimited: false,
      })
    } catch (err) {
      console.error('[SystemStore] Failed to fetch permissions:', err)
      
      // Check for 429 rate limit
      const rateLimit = isRateLimitError(err)
      if (rateLimit) {
        set({ 
          rateLimited: true,
          rateLimitRetryAt: Date.now() + rateLimit.retryAfter * 1000,
          _fetchingPermissions: false,
        })
        return
      }
      
      // Defensive: show empty state, don't throw
      set({ 
        permissions: [],
        _fetchingPermissions: false,
      })
    }
  },
  
  updateRolePermissions: async (roleName, permissions) => {
    try {
      await api.patch(`/api/system/roles/${roleName}`, permissions)
      // Refresh roles
      await get().fetchRoles(true)
    } catch (err) {
      console.error('[SystemStore] Failed to update role permissions:', err)
      throw err
    }
  },
  
  // Phase 8.5.3: Create a new role
  createRole: async (name, description, permissions) => {
    try {
      const response = await api.post('/api/system/roles', { name, description, permissions })
      // Refresh roles list
      await get().fetchRoles(true)
      return response.data
    } catch (err) {
      console.error('[SystemStore] Failed to create role:', err)
      throw err
    }
  },
  
  // Phase 8.5.3: Update role permissions by ID (with diff response)
  updateRolePermissionsById: async (roleId, permissions) => {
    try {
      const response = await api.patch(`/api/system/roles/${roleId}/permissions`, { permissions })
      // Refresh roles list
      await get().fetchRoles(true)
      return {
        changed: response.data.changed,
        added: response.data.added || [],
        removed: response.data.removed || [],
      }
    } catch (err) {
      console.error('[SystemStore] Failed to update role permissions:', err)
      throw err
    }
  },
  
  // Phase 8.5.3: Delete a role
  deleteRole: async (roleId) => {
    try {
      const response = await api.delete(`/api/system/roles/${roleId}`)
      // Refresh roles list
      await get().fetchRoles(true)
      return { deleted: response.data.deleted, message: response.data.message }
    } catch (err) {
      console.error('[SystemStore] Failed to delete role:', err)
      throw err
    }
  },
  
  // Phase 8.5.3: Get count of users assigned to a role (for deletion guard)
  getRoleUsersCount: async (_roleId) => {
    // This is checked server-side on delete, but we can also use users endpoint with filter
    // For now, return 0 and rely on server-side validation
    return 0
  },
  
  // Settings Actions
  fetchSettings: async (force = false) => {
    const { _settingsFetched, _fetchingSettings, rateLimited } = get()
    
    // Skip if rate limited
    if (rateLimited && !force) {
      console.log('[SystemStore] Skipping fetchSettings - rate limited')
      return
    }
    
    // Skip if already fetched this session (unless forced)
    if (_settingsFetched && !force) {
      console.log('[SystemStore] Skipping fetchSettings - already fetched')
      return
    }
    
    // Skip if already in-flight
    if (_fetchingSettings) {
      console.log('[SystemStore] Skipping fetchSettings - in-flight')
      return
    }
    
    set({ settingsLoading: true, _fetchingSettings: true, error: null })
    try {
      const response = await api.get('/api/system/settings')
      set({ 
        settings: response.data, 
        settingsLoading: false,
        _fetchingSettings: false,
        _settingsFetched: true,
        rateLimited: false,
      })
    } catch (err) {
      console.error('[SystemStore] Failed to fetch settings:', err)
      
      // Check for 429 rate limit
      const rateLimit = isRateLimitError(err)
      if (rateLimit) {
        set({ 
          rateLimited: true,
          rateLimitRetryAt: Date.now() + rateLimit.retryAfter * 1000,
          settingsLoading: false,
          _fetchingSettings: false,
        })
        return
      }
      
      set({ 
        error: err instanceof Error ? err.message : 'Failed to fetch settings',
        settingsLoading: false,
        _fetchingSettings: false,
      })
    }
  },
  
  // Stats Actions
  fetchStats: async (force = false) => {
    const { _statsFetched, _fetchingStats, rateLimited } = get()
    
    // Skip if rate limited
    if (rateLimited && !force) {
      console.log('[SystemStore] Skipping fetchStats - rate limited')
      return
    }
    
    // Skip if already fetched this session (unless forced)
    if (_statsFetched && !force) {
      console.log('[SystemStore] Skipping fetchStats - already fetched')
      return
    }
    
    // Skip if already in-flight
    if (_fetchingStats) {
      console.log('[SystemStore] Skipping fetchStats - in-flight')
      return
    }
    
    set({ statsLoading: true, _fetchingStats: true, error: null })
    try {
      const response = await api.get('/api/system/stats')
      set({ 
        stats: response.data, 
        statsLoading: false,
        _fetchingStats: false,
        _statsFetched: true,
        rateLimited: false,
      })
    } catch (err) {
      console.error('[SystemStore] Failed to fetch stats:', err)
      
      // Check for 429 rate limit
      const rateLimit = isRateLimitError(err)
      if (rateLimit) {
        set({ 
          rateLimited: true,
          rateLimitRetryAt: Date.now() + rateLimit.retryAfter * 1000,
          statsLoading: false,
          _fetchingStats: false,
        })
        return
      }
      
      // Defensive: show empty state, don't throw
      set({ 
        stats: null,
        error: err instanceof Error ? err.message : 'Failed to fetch stats',
        statsLoading: false,
        _fetchingStats: false,
      })
    }
  },
  
  // Reset session flags (for manual refresh)
  resetSessionFlags: () => {
    set({
      _statsFetched: false,
      _usersFetched: false,
      _rolesFetched: false,
      _permissionsFetched: false,
      _settingsFetched: false,
      rateLimited: false,
      rateLimitRetryAt: null,
    })
  },
}))
