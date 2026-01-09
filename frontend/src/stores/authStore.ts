import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import { connectSocket, disconnectSocket } from '../realtime'

interface User {
  id: number
  username: string
  email: string
  display_name: string | null
  avatar_url: string | null
  is_system_admin: boolean
  role?: string  // Business role: agent, storekeeper, delivery, foreman, customer, member, guest
  team_id?: number
}

interface AuthState {
  user: User | null
  token: string | null
  isAuthenticated: boolean
  _hasHydrated: boolean
  setHasHydrated: (hydrated: boolean) => void
  login: (token: string, user: User) => void
  logout: () => void
  updateUser: (user: Partial<User>) => void
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set) => ({
      user: null,
      token: null,
      isAuthenticated: false,
      _hasHydrated: false,
      setHasHydrated: (hydrated) => set({ _hasHydrated: hydrated }),
      login: (token, user) => {
        // Persist role to localStorage for session recovery
        if (user.role) {
          localStorage.setItem('user_role', user.role)
        }
        set({
          token,
          user,
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
          isAuthenticated: false,
        })
      },
      updateUser: (userData) =>
        set((state) => ({
          user: state.user ? { ...state.user, ...userData } : null,
        })),
    }),
    {
      name: 'auth-storage',
      partialize: (state) => ({
        user: state.user,
        token: state.token,
        isAuthenticated: state.isAuthenticated,
      }),
      onRehydrateStorage: () => (state) => {
        // Called after store is rehydrated from localStorage
        useAuthStore.getState().setHasHydrated(true)
        // If user is already authenticated (page refresh), connect socket
        if (state?.isAuthenticated && state?.token) {
          setTimeout(() => connectSocket(), 100)
        }
      },
    }
  )
)
