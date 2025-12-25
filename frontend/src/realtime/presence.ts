/**
 * Presence event subscriptions.
 * Phase 4.2 - Real-time presence.
 * 
 * Subscribes to Socket.IO presence events and updates the presence store.
 */
import { onSocketEvent } from './socket'
import { usePresenceStore } from '../stores/presenceStore'

let presenceSubscribed = false

/**
 * Subscribe to presence events from Socket.IO.
 * Should be called once after socket connects.
 */
export function subscribeToPresence(): void {
  if (presenceSubscribed) {
    console.log('[Presence] Already subscribed to presence events')
    return
  }
  
  const store = usePresenceStore.getState()
  
  // Listen for initial presence list (sent on connect)
  onSocketEvent<{ online_user_ids: number[] }>('presence:list', (data) => {
    console.log('[Presence] Received presence:list', data)
    store.setInitialPresence(data.online_user_ids)
  })
  
  // Listen for user coming online
  onSocketEvent<{ user_id: number; username: string }>('presence:online', (data) => {
    console.log('[Presence] Received presence:online', data)
    store.userOnline(data.user_id)
  })
  
  // Listen for user going offline
  onSocketEvent<{ user_id: number }>('presence:offline', (data) => {
    console.log('[Presence] Received presence:offline', data)
    store.userOffline(data.user_id)
  })
  
  presenceSubscribed = true
  console.log('[Presence] Subscribed to presence events')
}

/**
 * Reset presence subscription state (for logout/disconnect).
 */
export function resetPresenceSubscription(): void {
  presenceSubscribed = false
  usePresenceStore.getState().clearPresence()
}
