/**
 * Real-time module exports.
 * Phase 4.1 - Socket.IO foundation.
 * Phase 4.2 - Presence.
 */
export {
  connectSocket,
  disconnectSocket,
  getSocket,
  isSocketConnected,
  joinChannel,
  leaveChannel,
  onSocketEvent,
} from './socket'

export {
  subscribeToPresence,
  resetPresenceSubscription,
} from './presence'

export {
  subscribeToTasks,
  resetTaskSubscription,
} from './tasks'

export {
  subscribeToOrders,
  resetOrderSubscription,
} from './orders'
