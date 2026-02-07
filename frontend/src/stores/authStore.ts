import { create } from 'zustand'
import { persist, createJSONStorage } from 'zustand/middleware'
import { connectSocket, disconnectSocket } from '../realtime'
import api from '../services/api'
import { useTaskStore } from './taskStore'
import { useOrderStore } from './orderStore'

interface User {
  id: number
  username: string
  email: string
  display_name: string | null
  avatar_url: string | null
  is_system_admin: boolean
  role?: string  // Business role: agent, storekeeper, delivery, foreman, customer, member, guest
  operational_role_id?: number
  operational_role_name?: string
  operational_roles: string[]  // Fresh from user_operational_roles table - source of truth for task permissions
  must_change_password?: boolean  // Force password change flag
  is_first_login?: boolean  // First time user logs in
  last_login_at?: string | null  // ISO timestamp of last login
}

interface AuthState {
  user: User | null
  currentUser: User | null
  token: string | null
  isAuthenticated: boolean
  _hasHydrated: boolean
  setHasHydrated: (hydrated: boolean) => void
  login: (token: string, user: User) => void
  logout: () => void
  updateUser: (user: Partial<User>) => void
  setCurrentUser: (user: User) => void
}

let setRef: { set?: (partial: Partial<AuthState>) => void } = {}

export const useAuthStore = create<AuthState>()(
  persist(
    (set) => {
      // capture set reference to avoid referencing the store before initialization
      setRef.set = set
      return {
        user: null,
        currentUser: null,
        token: null,
        isAuthenticated: false,
        _hasHydrated: false,
        setHasHydrated: (hydrated) => set({ _hasHydrated: hydrated }),
        login: (token, user) => {
          // Persist role to localStorage for session recovery (back-compat)
          if (user.role) {
            localStorage.setItem('user_role', user.role)
          }

          // Normalize user to ensure operational_roles is always an array
          const normalizedUser = {
            ...user,
            operational_roles: user.operational_roles ?? [],
          }

          set({
            token,
            user: normalizedUser,
            currentUser: normalizedUser,
            isAuthenticated: true,
          })

          // Decode user_id from JWT (best-effort) for temporary logging
          let userIdFromJwt: string | number | null = null
          try {
            const parts = token.split('.')
            if (parts.length > 1) {
              // atob on the payload, handle URL-safe base64
              const payloadBase64 = parts[1].replace(/-/g, '+').replace(/_/g, '/')
              const json = decodeURIComponent(atob(payloadBase64).split('').map((c) => '%'+('00'+c.charCodeAt(0).toString(16)).slice(-2)).join(''))
              const payload = JSON.parse(json)
              userIdFromJwt = payload.sub ?? payload.user_id ?? payload.uid ?? null
            }
          } catch (e) {
            // ignore decode errors
          }

          // Force-refresh task stores BEFORE connecting socket, then connect.
          // This ensures /api/automation/tasks is called after login, not before socket connect.
          setTimeout(async () => {
            try {
              await useTaskStore.getState().fetchMyTasks()
              await useTaskStore.getState().fetchMyAssignments()
              const tasksCount = useTaskStore.getState().tasks.length
              // Temporary debug log: user_id from JWT and number of tasks returned
              console.log('[Auth] Login user_id_from_jwt:', userIdFromJwt ?? user.id, 'tasks_count:', tasksCount)
            } catch (err) {
              console.error('[Auth] Failed to refresh tasks on login:', err)
            } finally {
              // Connect socket after tasks refreshed
              connectSocket()
            }
          }, 0)
        },
        logout: () => {
          // Disconnect Socket.IO before clearing auth state
          disconnectSocket()
          // Clear persisted role and auth-related keys
          try { localStorage.removeItem('user_role') } catch (e) {}
          try { localStorage.removeItem('auth') } catch (e) {}
          try { localStorage.removeItem('auth-storage') } catch (e) {}
          try { localStorage.removeItem('access_token') } catch (e) {}
          try { sessionStorage.removeItem('auth') } catch (e) {}
          try { sessionStorage.removeItem('access_token') } catch (e) {}
          try { sessionStorage.clear() } catch (e) {}

          // Reset other stores that may contain auth-scoped data
          try { useTaskStore.getState().reset() } catch (e) {}
          try { useOrderStore.getState().reset() } catch (e) {}

          set({
            token: null,
            user: null,
            currentUser: null,
            isAuthenticated: false,
          })
        },
        updateUser: (userData) =>
          set((state) => {
            // Normalize operational_roles if present in update
            const normalizedData = userData.operational_roles !== undefined
              ? { ...userData, operational_roles: userData.operational_roles ?? [] }
              : userData
            return {
              user: state.user ? { ...state.user, ...normalizedData } : null,
              currentUser: state.currentUser ? { ...state.currentUser, ...normalizedData } : null,
            }
          }),
        setCurrentUser: (userData) => {
          // Normalize operational_roles to ensure it's always an array
          const normalizedUser = {
            ...userData,
            operational_roles: userData.operational_roles ?? [],
          }
          set({ user: normalizedUser, currentUser: normalizedUser })
        },
      }
    },
    {
      name: 'auth',
      storage: createJSONStorage(() => localStorage),
      partialize: (state) => ({
        user: state.user,
        currentUser: state.currentUser,
        token: state.token,
        isAuthenticated: state.isAuthenticated,
      }),
      onRehydrateStorage: () => async (state) => {
        // Called after store is rehydrated from localStorage
        // Use captured setRef to avoid referencing the store value during initialization
        setRef.set?.({ _hasHydrated: true })
        // If there's no token, nothing to hydrate
        if (!state?.token) return

        try {
          const resp = await api.get('/api/auth/me', { headers: { Authorization: `Bearer ${state.token}` } })
          if (resp?.data) {
            // Replace stored user with authoritative server copy (includes operational_roles)
            // Normalize to ensure operational_roles is always an array
            const normalizedUser = {
              ...resp.data,
              operational_roles: resp.data.operational_roles ?? [],
            }
            setRef.set?.({ currentUser: normalizedUser, user: normalizedUser })
          }
        } catch (err) {
          // If token invalid or request fails, clear auth
          // Replicate logout actions without calling the store methods (to avoid TDZ)
          disconnectSocket()
          localStorage.removeItem('user_role')
          setRef.set?.({ token: null, user: null, currentUser: null, isAuthenticated: false })
        } finally {
          // Refresh tasks before connecting socket (session restore behaves like login)
          setTimeout(async () => {
            try {
              await useTaskStore.getState().fetchMyTasks()
              await useTaskStore.getState().fetchMyAssignments()
              const tasksCount = useTaskStore.getState().tasks.length

              // Attempt to decode user_id from token for temporary logging
              let userIdFromJwt: string | number | null = null
              try {
                if (state?.token) {
                  const parts = state.token.split('.')
                  if (parts.length > 1) {
                    const payloadBase64 = parts[1].replace(/-/g, '+').replace(/_/g, '/')
                    const json = decodeURIComponent(atob(payloadBase64).split('').map((c) => '%'+('00'+c.charCodeAt(0).toString(16)).slice(-2)).join(''))
                    const payload = JSON.parse(json)
                    userIdFromJwt = payload.sub ?? payload.user_id ?? payload.uid ?? null
                  }
                }
              } catch (e) {}

              console.log('[Auth] Rehydrate user_id_from_jwt:', userIdFromJwt ?? state?.user?.id ?? 'unknown', 'tasks_count:', tasksCount)
            } catch (e) {
              console.error('[Auth] Failed to refresh tasks on rehydrate:', e)
            } finally {
              connectSocket()
            }
          }, 100)
        }
      },
    }
  )
)

// Expose auth store state for runtime inspection and simple guards in the browser console
if (typeof window !== "undefined") {
  // @ts-ignore
  window.__APP_STATE__ = window.__APP_STATE__ || {}
  // @ts-ignore
  window.__APP_STATE__.auth = useAuthStore.getState()

  useAuthStore.subscribe((state) => {
    // @ts-ignore
    window.__APP_STATE__.auth = state
  })
}