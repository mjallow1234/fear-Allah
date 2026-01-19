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

export const useAuthStore = create<AuthState>()(
  persist(
    (set) => ({
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
    }),
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
        useAuthStore.getState().setHasHydrated(true)
        // If there's no token, nothing to hydrate
        if (!state?.token) return

        try {
          const resp = await api.get('/api/auth/me', { headers: { Authorization: `Bearer ${state.token}` } })
          if (resp?.data) {
            // Replace stored user with authoritative server copy (includes operational_role_name)
            useAuthStore.getState().setCurrentUser(resp.data)
          }
        } catch (err) {
          // If token invalid or request fails, clear auth
          useAuthStore.getState().logout()
        } finally {
          setTimeout(() => connectSocket(), 100)
        }
      },
    }
  )
)
