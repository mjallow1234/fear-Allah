import { create } from 'zustand'
import { persist, createJSONStorage } from 'zustand/middleware'
import api from '../services/api'

export interface UserPreferences {
  dark_mode: boolean
  compact_mode: boolean
  notifications: boolean
  sound: boolean
}

const DEFAULT_PREFERENCES: UserPreferences = {
  dark_mode: true,
  compact_mode: false,
  notifications: true,
  sound: true,
}

interface PreferencesState {
  preferences: UserPreferences
  isLoading: boolean
  error: string | null
  setPreference: <K extends keyof UserPreferences>(key: K, value: UserPreferences[K]) => Promise<void>
  fetchPreferences: () => Promise<void>
  resetToDefaults: () => void
}

export const usePreferencesStore = create<PreferencesState>()(
  persist(
    (set, get) => ({
      preferences: { ...DEFAULT_PREFERENCES },
      isLoading: false,
      error: null,

      setPreference: async (key, value) => {
        // Optimistic update
        const prevPreferences = get().preferences
        const newPreferences = { ...prevPreferences, [key]: value }
        set({ preferences: newPreferences, error: null })

        try {
          await api.put('/api/users/me/preferences', newPreferences)
        } catch (err) {
          // Revert on error
          set({ preferences: prevPreferences, error: 'Failed to save preference' })
          console.error('[Preferences] Failed to save:', err)
        }
      },

      fetchPreferences: async () => {
        set({ isLoading: true, error: null })
        try {
          const response = await api.get('/api/users/me/preferences')
          set({ preferences: response.data.preferences, isLoading: false })
        } catch (err) {
          // On error, keep local defaults
          set({ isLoading: false, error: 'Failed to load preferences' })
          console.error('[Preferences] Failed to fetch:', err)
        }
      },

      resetToDefaults: () => {
        set({ preferences: { ...DEFAULT_PREFERENCES } })
      },
    }),
    {
      name: 'user-preferences',
      storage: createJSONStorage(() => localStorage),
      partialize: (state) => ({ preferences: state.preferences }),
    }
  )
)
