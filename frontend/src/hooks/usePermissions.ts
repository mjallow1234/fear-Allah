/**
 * Phase 8.6: Permission Helper Hook
 * 
 * Provides permission checking for UI enforcement.
 * Source of truth: user's assigned roles from backend.
 * System admins automatically have all permissions.
 */
import { create } from 'zustand'
import { useEffect } from 'react'
import api from '../services/api'
import { useAuthStore } from '../stores/authStore'

// Permission constants for type safety
export const PERMISSIONS = {
  // System Console
  MANAGE_USERS: 'system.manage_users',
  MANAGE_ROLES: 'system.manage_roles',
  VIEW_AUDIT: 'system.view_audit',
  MANAGE_SETTINGS: 'system.manage_settings',
  
  // Channels
  CHANNEL_CREATE: 'channel.create',
  CHANNEL_DELETE: 'channel.delete',
  CHANNEL_MANAGE: 'channel.manage',
  
  // Messages
  MESSAGE_DELETE_ANY: 'message.delete_any',
  
  // Users
  USER_BAN: 'user.ban',
  USER_MUTE: 'user.mute',
} as const

export type PermissionKey = typeof PERMISSIONS[keyof typeof PERMISSIONS]

interface PermissionState {
  permissions: string[]
  isSystemAdmin: boolean
  isLoaded: boolean
  isLoading: boolean
  error: string | null
  
  // Actions
  fetchPermissions: () => Promise<void>
  reset: () => void
  
  // Helpers
  hasPermission: (key: string) => boolean
  hasAnyPermission: (keys: string[]) => boolean
  hasAllPermissions: (keys: string[]) => boolean
}

export const usePermissionStore = create<PermissionState>((set, get) => ({
  permissions: [],
  isSystemAdmin: false,
  isLoaded: false,
  isLoading: false,
  error: null,
  
  fetchPermissions: async () => {
    const { isLoading, isLoaded } = get()
    
    // Skip if already loading or loaded
    if (isLoading || isLoaded) return
    
    set({ isLoading: true, error: null })
    
    try {
      const response = await api.get('/api/users/me/permissions')
      set({
        permissions: response.data.permissions || [],
        isSystemAdmin: response.data.is_system_admin || false,
        isLoaded: true,
        isLoading: false,
      })
    } catch (err) {
      console.error('[Permissions] Failed to fetch:', err)
      set({
        permissions: [],
        isSystemAdmin: false,
        isLoaded: true,
        isLoading: false,
        error: 'Failed to load permissions',
      })
    }
  },
  
  reset: () => {
    set({
      permissions: [],
      isSystemAdmin: false,
      isLoaded: false,
      isLoading: false,
      error: null,
    })
  },
  
  hasPermission: (key: string) => {
    const { isSystemAdmin, permissions } = get()
    // System admins have all permissions
    if (isSystemAdmin) return true
    return permissions.includes(key)
  },
  
  hasAnyPermission: (keys: string[]) => {
    const { isSystemAdmin, permissions } = get()
    if (isSystemAdmin) return true
    return keys.some(key => permissions.includes(key))
  },
  
  hasAllPermissions: (keys: string[]) => {
    const { isSystemAdmin, permissions } = get()
    if (isSystemAdmin) return true
    return keys.every(key => permissions.includes(key))
  },
}))

/**
 * Hook to use permissions in components.
 * Automatically fetches permissions on mount if authenticated.
 */
export function usePermissions() {
  const { isAuthenticated } = useAuthStore()
  const store = usePermissionStore()
  
  useEffect(() => {
    if (isAuthenticated && !store.isLoaded && !store.isLoading) {
      store.fetchPermissions()
    }
  }, [isAuthenticated, store.isLoaded, store.isLoading])
  
  // Reset permissions on logout
  useEffect(() => {
    if (!isAuthenticated) {
      store.reset()
    }
  }, [isAuthenticated])
  
  return {
    permissions: store.permissions,
    isSystemAdmin: store.isSystemAdmin,
    isLoaded: store.isLoaded,
    isLoading: store.isLoading,
    hasPermission: store.hasPermission,
    hasAnyPermission: store.hasAnyPermission,
    hasAllPermissions: store.hasAllPermissions,
    refetch: store.fetchPermissions,
  }
}

/**
 * Standalone permission check (for use outside React components)
 */
export function checkPermission(key: string): boolean {
  return usePermissionStore.getState().hasPermission(key)
}

export function checkAnyPermission(keys: string[]): boolean {
  return usePermissionStore.getState().hasAnyPermission(keys)
}
