/**
 * Socket.IO client for real-time communication.
 * Phase 4.1 - Real-time foundation.
 * 
 * Single source of truth for socket connection.
 * Connect only after login, disconnect on logout.
 */
import { io, Socket } from 'socket.io-client'
import { useAuthStore } from '../stores/authStore'

// Socket instance (singleton)
let socket: Socket | null = null

// Connection state
let isConnecting = false

// Pending channel joins (to retry after connection)
const pendingJoins = new Set<number>()

// Event handlers registered before connection
const pendingHandlers: Map<string, Set<(data: any) => void>> = new Map()

// Master event listeners (one per event type, dispatches to all handlers)
const masterListeners: Map<string, (data: any) => void> = new Map()

/**
 * Get the Socket.IO server URL (LAN-safe)
 */
function getSocketUrl(): string {
  return `http://${window.location.hostname}:8000`
}

/**
 * Connect to Socket.IO server with JWT auth.
 * Should be called after successful login.
 */
export function connectSocket(): Socket | null {
  const token = useAuthStore.getState().token
  
  if (!token) {
    console.warn('[Socket.IO] No token available, cannot connect')
    return null
  }
  
  // Prevent multiple simultaneous connection attempts
  if (isConnecting) {
    console.log('[Socket.IO] Connection already in progress')
    return socket
  }
  
  // If already connected, return existing socket
  if (socket?.connected) {
    console.log('[Socket.IO] Already connected')
    return socket
  }
  
  // Disconnect old socket if exists but not connected
  if (socket) {
    socket.disconnect()
    socket = null
  }
  
  isConnecting = true
  
  const url = getSocketUrl()
  console.log('[Socket.IO] Connecting to', url)
  
  socket = io(url, {
    // Backend mounts socket_app at /socket.io, with internal path socket.io
    // Full path becomes /socket.io/socket.io/
    path: '/socket.io/socket.io/',
    auth: { token },
    autoConnect: true,
    reconnection: true,
    reconnectionAttempts: Infinity,
    reconnectionDelay: 1000,
    reconnectionDelayMax: 5000,
    transports: ['polling', 'websocket'],  // Start with polling for reliability
  })
  
  socket.on('connect', () => {
    console.log('[Socket.IO] Connected, sid:', socket?.id)
    isConnecting = false
    
    // Process pending channel joins
    pendingJoins.forEach(channelId => {
      console.log('[Socket.IO] Joining pending channel:', channelId)
      socket?.emit('join_channel', { channel_id: channelId })
    })
    
    // Register master listeners for any pending handlers
    pendingHandlers.forEach((handlers, event) => {
      if (handlers.size > 0 && !masterListeners.has(event)) {
        const masterListener = (data: any) => {
          pendingHandlers.get(event)?.forEach(h => h(data))
        }
        masterListeners.set(event, masterListener)
        socket?.on(event, masterListener)
      }
    })
  })
  
  socket.on('connected', (data) => {
    console.log('[Socket.IO] Server confirmed connection:', data)
  })
  
  socket.on('channel:joined', (data) => {
    console.log('[Socket.IO] Joined channel room:', data)
  })
  
  socket.on('disconnect', (reason) => {
    console.log('[Socket.IO] Disconnected:', reason)
    isConnecting = false
  })
  
  socket.on('connect_error', (error) => {
    console.error('[Socket.IO] Connection error:', error.message)
    isConnecting = false
  })
  
  socket.on('error', (data) => {
    console.error('[Socket.IO] Server error:', data)
  })
  
  return socket
}

/**
 * Disconnect from Socket.IO server.
 * Should be called on logout.
 */
export function disconnectSocket(): void {
  if (socket) {
    console.log('[Socket.IO] Disconnecting')
    socket.disconnect()
    socket = null
  }
  isConnecting = false
  pendingJoins.clear()
  pendingHandlers.clear()
  masterListeners.clear()
}

/**
 * Get the current socket instance.
 * Returns null if not connected.
 */
export function getSocket(): Socket | null {
  return socket
}

/**
 * Check if socket is connected.
 */
export function isSocketConnected(): boolean {
  return socket?.connected ?? false
}

/**
 * Join a channel room to receive channel-specific events.
 * If not connected yet, queues the join for when connection is established.
 */
export function joinChannel(channelId: number): void {
  // Always track the channel for reconnection scenarios
  pendingJoins.add(channelId)
  
  if (!socket?.connected) {
    console.log('[Socket.IO] Queued channel join (not connected yet):', channelId)
    return
  }
  
  console.log('[Socket.IO] Joining channel:', channelId)
  socket.emit('join_channel', { channel_id: channelId })
}

/**
 * Leave a channel room.
 */
export function leaveChannel(channelId: number): void {
  pendingJoins.delete(channelId)
  
  if (!socket?.connected) {
    return
  }
  
  console.log('[Socket.IO] Leaving channel:', channelId)
  socket.emit('leave_channel', { channel_id: channelId })
}

/**
 * Subscribe to an event.
 * Uses a single master listener per event type to avoid duplicate handlers.
 * Returns unsubscribe function.
 */
export function onSocketEvent<T = any>(
  event: string, 
  handler: (data: T) => void
): () => void {
  // Add handler to the set
  if (!pendingHandlers.has(event)) {
    pendingHandlers.set(event, new Set())
  }
  pendingHandlers.get(event)!.add(handler)
  
  // If socket exists and we don't have a master listener yet, create one
  if (socket && !masterListeners.has(event)) {
    const masterListener = (data: any) => {
      pendingHandlers.get(event)?.forEach(h => h(data))
    }
    masterListeners.set(event, masterListener)
    socket.on(event, masterListener)
  }
  
  // Return unsubscribe function
  return () => {
    pendingHandlers.get(event)?.delete(handler)
    // Note: we keep the master listener active even if no handlers remain
    // This simplifies the logic and avoids edge cases
  }
}

// Export types
export type { Socket }
