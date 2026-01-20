import { create } from 'zustand'
import { persist, createJSONStorage } from 'zustand/middleware'
import { connectSocket, disconnectSocket } from '../realtime'
import api from '../services/api'

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
          set({
            token,
            user,
            currentUser: user,
            isAuthenticated: true,
          })
          // Connect Socket.IO after login
          setTimeout(() => connectSocket(), 0)
        },
        logout: () => {
          // Disconnect Socket.IO before clearing auth state
          disconnectSocket()
          // Clear persisted role
          localStorage.removeItem('user_role')
          set({
            token: null,
            user: null,
            currentUser: null,
            isAuthenticated: false,
          })
        },
        updateUser: (userData) =>
          set((state) => ({
            user: state.user ? { ...state.user, ...userData } : null,
            currentUser: state.currentUser ? { ...state.currentUser, ...userData } : null,
          })),
        setCurrentUser: (userData) => set({ user: userData, currentUser: userData }),
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
            // Replace stored user with authoritative server copy (includes operational_role_name)
            setRef.set?.({ currentUser: resp.data, user: resp.data })
          }
        } catch (err) {
          // If token invalid or request fails, clear auth
          // Replicate logout actions without calling the store methods (to avoid TDZ)
          disconnectSocket()
          localStorage.removeItem('user_role')
          setRef.set?.({ token: null, user: null, currentUser: null, isAuthenticated: false })
        } finally {
          setTimeout(() => connectSocket(), 100)
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