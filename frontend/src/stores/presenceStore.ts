/**
 * Presence store for online/offline tracking.
 * Phase 4.2 - Real-time presence.
 * 
 * Tracks which users are currently online in the team.
 * Socket-only, no polling.
 */
import { create } from 'zustand'

interface PresenceState {
  // Set of online user IDs
  onlineUserIds: Set<number>
  
  // Actions
  setInitialPresence: (userIds: number[]) => void
  userOnline: (userId: number) => void
  userOffline: (userId: number) => void
  isOnline: (userId: number) => boolean
  clearPresence: () => void
}

export const usePresenceStore = create<PresenceState>((set, get) => ({
  onlineUserIds: new Set(),
  
  setInitialPresence: (userIds: number[]) => {
    console.log('[Presence] Setting initial presence:', userIds)
    set({ onlineUserIds: new Set(userIds) })
  },
  
  userOnline: (userId: number) => {
    console.log('[Presence] User online:', userId)
    set((state) => {
      const newSet = new Set(state.onlineUserIds)
      newSet.add(userId)
      return { onlineUserIds: newSet }
    })
  },
  
  userOffline: (userId: number) => {
    console.log('[Presence] User offline:', userId)
    set((state) => {
      const newSet = new Set(state.onlineUserIds)
      newSet.delete(userId)
      return { onlineUserIds: newSet }
    })
  },
  
  isOnline: (userId: number) => {
    return get().onlineUserIds.has(userId)
  },
  
  clearPresence: () => {
    console.log('[Presence] Clearing all presence')
    set({ onlineUserIds: new Set() })
  },
}))
