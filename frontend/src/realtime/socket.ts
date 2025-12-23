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
  
  isConnecting = true
  
  const url = getSocketUrl()
  console.log('[Socket.IO] Connecting to', url)
  
  socket = io(url, {
    path: '/socket.io/socket.io',
    auth: { token },
    autoConnect: true,
    reconnection: true,
    reconnectionAttempts: Infinity,
    reconnectionDelay: 1000,
    reconnectionDelayMax: 5000,
    transports: ['websocket', 'polling'],
  })
  
  socket.on('connect', () => {
    console.log('[Socket.IO] Connected, sid:', socket?.id)
    isConnecting = false
  })
  
  socket.on('connected', (data) => {
    console.log('[Socket.IO] Server confirmed connection:', data)
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
 */
export function joinChannel(channelId: number): void {
  if (!socket?.connected) {
    console.warn('[Socket.IO] Cannot join channel, not connected')
    return
  }
  console.log('[Socket.IO] Joining channel:', channelId)
  socket.emit('join_channel', { channel_id: channelId })
}

/**
 * Leave a channel room.
 */
export function leaveChannel(channelId: number): void {
  if (!socket?.connected) {
    return
  }
  console.log('[Socket.IO] Leaving channel:', channelId)
  socket.emit('leave_channel', { channel_id: channelId })
}

/**
 * Subscribe to an event.
 * Returns unsubscribe function.
 */
export function onSocketEvent<T = any>(
  event: string, 
  handler: (data: T) => void
): () => void {
  if (!socket) {
    console.warn('[Socket.IO] Cannot subscribe, socket not initialized')
    return () => {}
  }
  
  socket.on(event, handler)
  return () => {
    socket?.off(event, handler)
  }
}

// Export types
export type { Socket }
