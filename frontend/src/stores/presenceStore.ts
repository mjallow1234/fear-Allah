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
    const normalizedIds = userIds.map(id => Number(id))
    set({ onlineUserIds: new Set(normalizedIds) })
  },
  
  userOnline: (userId: number) => {
    const normalizedId = Number(userId)
    set((state) => {
      const newSet = new Set(state.onlineUserIds)
      newSet.add(normalizedId)
      return { onlineUserIds: newSet }
    })
  },
  
  userOffline: (userId: number) => {
    const normalizedId = Number(userId)
    set((state) => {
      const newSet = new Set(state.onlineUserIds)
      newSet.delete(normalizedId)
      return { onlineUserIds: newSet }
    })
  },
  
  isOnline: (userId: number) => {
    // Ensure ID is a number for comparison
    return get().onlineUserIds.has(Number(userId))
  },
  
  clearPresence: () => {
    set({ onlineUserIds: new Set() })
  },
}))
