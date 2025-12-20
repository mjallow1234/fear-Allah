import { create } from 'zustand'
import { persist } from 'zustand/middleware'

interface User {
  id: number
  username: string
  email: string
  display_name: string | null
  avatar_url: string | null
  is_system_admin: boolean
}

interface AuthState {
  user: User | null
  token: string | null
  isAuthenticated: boolean
  hydrated: boolean
  login: (token: string, user: User) => void
  logout: () => void
  hydrate: () => void
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set) => ({
      user: null,
      token: null,
      isAuthenticated: false,
      hydrated: false,
      login: (token, user) =>
        set({
          token,
          user,
          isAuthenticated: true,
        }),
      logout: () =>
        set({
          token: null,
          user: null,
          isAuthenticated: false,
        }),
      hydrate: () => {
        // read from localStorage and populate state
        if (typeof window === 'undefined') {
          set({ hydrated: true })
          return
        }

        try {
          const raw = localStorage.getItem('auth-storage')
          if (!raw) {
            set({ hydrated: true })
            return
          }

          const parsed = JSON.parse(raw)
          const state = (parsed && parsed.state) ? parsed.state : parsed
          const token = state?.token ?? null
          const user = state?.user ?? null
          set({ token, user, isAuthenticated: !!token, hydrated: true })
        } catch (e) {
          set({ hydrated: true })
        }
      },
    }),
    {
      name: 'auth-storage',
      // only persist the auth-relevant fields; don't persist `hydrated`
      partialize: (state) => ({ token: state.token, user: state.user, isAuthenticated: state.isAuthenticated }),
    }
  )
)
