import { useEffect, useRef, useCallback, useState } from 'react'
import { useAuthStore } from '../stores/authStore'

export type WebSocketEventType =
  | 'message'
  | 'typing_start'
  | 'typing_stop'
  | 'reaction_add'
  | 'reaction_remove'
  | 'file_upload'
  | 'user_joined'
  | 'user_left'
  | 'presence_update'
  | 'presence_list'

export interface WebSocketMessage {
  type: WebSocketEventType
  id?: number
  content?: string
  user_id?: number
  username?: string
  channel_id?: number
  message_id?: number
  emoji?: string
  file?: {
    id: number
    filename: string
    file_path: string
    download_url: string
    mime_type: string
    file_size: number
  }
  timestamp?: string
  status?: string
  users?: number[]
}

export interface Reaction {
  emoji: string
  count: number
  users: number[]
}

export interface Message {
  id: number
  content: string
  user_id: number
  username: string
  channel_id: number
  timestamp: string
  reactions: Reaction[]
  files?: Array<{
    id: number
    filename: string
    download_url: string
    mime_type: string
  }>
}

interface UseWebSocketOptions {
  channelId: number
  onMessage?: (message: WebSocketMessage) => void
  onTypingStart?: (userId: number, username: string) => void
  onTypingStop?: (userId: number, username: string) => void
  onReaction?: (messageId: number, emoji: string, userId: number, action: 'add' | 'remove') => void
  onFileUpload?: (file: WebSocketMessage['file']) => void
  onUserJoined?: (userId: number, username: string) => void
  onUserLeft?: (userId: number, username: string) => void
  onPresenceUpdate?: (userId: number, status: string) => void
}

export function useWebSocket({
  channelId,
  onMessage,
  onTypingStart,
  onTypingStop,
  onReaction,
  onFileUpload,
  onUserJoined,
  onUserLeft,
  onPresenceUpdate,
}: UseWebSocketOptions) {
  const wsRef = useRef<WebSocket | null>(null)
  const [isConnected, setIsConnected] = useState(false)
  const [typingUsers, setTypingUsers] = useState<Map<number, string>>(new Map())
  const typingTimeoutRef = useRef<Map<number, ReturnType<typeof setTimeout>>>(new Map())
  const reconnectTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const currentChannelRef = useRef<number>(channelId)
  
  // Store callbacks in refs to avoid recreating connect function
  const callbacksRef = useRef({
    onMessage,
    onTypingStart,
    onTypingStop,
    onReaction,
    onFileUpload,
    onUserJoined,
    onUserLeft,
    onPresenceUpdate,
  })
  
  // Update callbacks ref when they change
  useEffect(() => {
    callbacksRef.current = {
      onMessage,
      onTypingStart,
      onTypingStop,
      onReaction,
      onFileUpload,
      onUserJoined,
      onUserLeft,
      onPresenceUpdate,
    }
  })
  
  const user = useAuthStore((state) => state.user)
  const userRef = useRef(user)
  
  useEffect(() => {
    userRef.current = user
  }, [user])

  const disconnect = useCallback(() => {
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current)
      reconnectTimeoutRef.current = null
    }
    if (wsRef.current) {
      wsRef.current.close()
      wsRef.current = null
    }
    setIsConnected(false)
  }, [])

  const connect = useCallback(() => {
    const currentUser = userRef.current
    const currentChannel = currentChannelRef.current
    
    if (!currentChannel || !currentUser) return

    // Close existing connection before opening new one
    if (wsRef.current) {
      wsRef.current.close()
      wsRef.current = null
    }

    const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const wsHost = window.location.host
    const wsUrl = `${wsProtocol}//${wsHost}/ws/chat/${currentChannel}?user_id=${currentUser.id}&username=${encodeURIComponent(currentUser.username || currentUser.display_name || '')}`
    
    console.log('Connecting to WebSocket:', wsUrl)
    const ws = new WebSocket(wsUrl)
    wsRef.current = ws

    ws.onopen = () => {
      console.log(`WebSocket connected to channel ${currentChannel}`)
      setIsConnected(true)
    }

    ws.onmessage = (event) => {
      try {
        const data: WebSocketMessage = JSON.parse(event.data)
        const callbacks = callbacksRef.current
        
        switch (data.type) {
          case 'message':
            callbacks.onMessage?.(data)
            break
          
          case 'typing_start':
            if (data.user_id && data.username) {
              setTypingUsers((prev) => {
                const next = new Map(prev)
                next.set(data.user_id!, data.username!)
                return next
              })
              callbacks.onTypingStart?.(data.user_id, data.username)
              
              // Clear typing after 3 seconds
              const existingTimeout = typingTimeoutRef.current.get(data.user_id)
              if (existingTimeout) clearTimeout(existingTimeout)
              
              const timeout = setTimeout(() => {
                setTypingUsers((prev) => {
                  const next = new Map(prev)
                  next.delete(data.user_id!)
                  return next
                })
              }, 3000)
              typingTimeoutRef.current.set(data.user_id, timeout)
            }
            break
          
          case 'typing_stop':
            if (data.user_id) {
              setTypingUsers((prev) => {
                const next = new Map(prev)
                next.delete(data.user_id!)
                return next
              })
              callbacks.onTypingStop?.(data.user_id!, data.username || '')
            }
            break
          
          case 'reaction_add':
            if (data.message_id && data.emoji && data.user_id) {
              callbacks.onReaction?.(data.message_id, data.emoji, data.user_id, 'add')
            }
            break
          
          case 'reaction_remove':
            if (data.message_id && data.emoji && data.user_id) {
              callbacks.onReaction?.(data.message_id, data.emoji, data.user_id, 'remove')
            }
            break
          
          case 'file_upload':
            if (data.file) {
              callbacks.onFileUpload?.(data.file)
            }
            break
          
          case 'user_joined':
            if (data.user_id && data.username) {
              callbacks.onUserJoined?.(data.user_id, data.username)
            }
            break
          
          case 'user_left':
            if (data.user_id) {
              callbacks.onUserLeft?.(data.user_id!, data.username || '')
            }
            break
          
          case 'presence_update':
            if (data.user_id && data.status) {
              callbacks.onPresenceUpdate?.(data.user_id, data.status)
            }
            break
        }
      } catch (err) {
        console.error('Failed to parse WebSocket message:', err)
      }
    }

    ws.onclose = () => {
      console.log('WebSocket disconnected')
      setIsConnected(false)
      
      // Only attempt reconnection if this is still the current channel
      if (currentChannelRef.current === currentChannel && userRef.current) {
        reconnectTimeoutRef.current = setTimeout(() => {
          connect()
        }, 3000)
      }
    }

    ws.onerror = (error) => {
      console.error('WebSocket error:', error)
    }
  }, []) // No dependencies - uses refs instead

  // Connect/disconnect when channelId or user changes
  useEffect(() => {
    currentChannelRef.current = channelId
    
    if (!channelId || !user) {
      disconnect()
      return
    }
    
    // Clear typing users when channel changes
    setTypingUsers(new Map())
    
    // Clear any pending reconnect
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current)
      reconnectTimeoutRef.current = null
    }
    
    connect()
    
    return () => {
      disconnect()
    }
  }, [channelId, user?.id, connect, disconnect])

  // Send message
  const sendMessage = useCallback((content: string) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({
        type: 'message',
        content,
        timestamp: new Date().toISOString(),
      }))
    }
  }, [])

  // Send typing indicator (debounced)
  const typingDebounceRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const lastTypingSentRef = useRef<number>(0)
  
  const sendTyping = useCallback((isTyping: boolean) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      const now = Date.now()
      
      if (isTyping) {
        // Only send typing_start if we haven't sent one in the last 2 seconds
        if (now - lastTypingSentRef.current > 2000) {
          wsRef.current.send(JSON.stringify({ type: 'typing_start' }))
          lastTypingSentRef.current = now
        }
        
        // Clear existing timeout and set new one for typing_stop
        if (typingDebounceRef.current) {
          clearTimeout(typingDebounceRef.current)
        }
        typingDebounceRef.current = setTimeout(() => {
          if (wsRef.current?.readyState === WebSocket.OPEN) {
            wsRef.current.send(JSON.stringify({ type: 'typing_stop' }))
          }
        }, 2000)
      } else {
        if (typingDebounceRef.current) {
          clearTimeout(typingDebounceRef.current)
        }
        wsRef.current.send(JSON.stringify({ type: 'typing_stop' }))
      }
    }
  }, [])

  // Send reaction
  const sendReaction = useCallback((messageId: number, emoji: string, action: 'add' | 'remove') => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({
        type: action === 'add' ? 'reaction_add' : 'reaction_remove',
        message_id: messageId,
        emoji,
      }))
    }
  }, [])

  return {
    isConnected,
    typingUsers: Array.from(typingUsers.entries()).map(([id, name]) => ({ id, name })),
    sendMessage,
    sendTyping,
    sendReaction,
    disconnect,
    reconnect: connect,
  }
}

// Presence hook for global online/offline tracking
export function usePresence() {
  const wsRef = useRef<WebSocket | null>(null)
  const [isConnected, setIsConnected] = useState(false)
  const [onlineUsers, setOnlineUsers] = useState<Set<number>>(new Set())
  
  const user = useAuthStore((state) => state.user)

  useEffect(() => {
    if (!user) return

    const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const wsHost = window.location.host
    const wsUrl = `${wsProtocol}//${wsHost}/ws/presence?user_id=${user.id}&username=${encodeURIComponent(user.username || user.display_name || '')}`
    
    const ws = new WebSocket(wsUrl)
    wsRef.current = ws

    ws.onopen = () => {
      setIsConnected(true)
      
      // Send heartbeat every 30 seconds
      const heartbeatInterval = setInterval(() => {
        if (ws.readyState === WebSocket.OPEN) {
          ws.send(JSON.stringify({ type: 'heartbeat' }))
        }
      }, 30000)
      
      ws.onclose = () => {
        clearInterval(heartbeatInterval)
        setIsConnected(false)
      }
    }

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data)
        
        if (data.type === 'presence_list') {
          setOnlineUsers(new Set(data.users || []))
        } else if (data.type === 'presence_update') {
          setOnlineUsers((prev) => {
            const next = new Set(prev)
            if (data.status === 'online') {
              next.add(data.user_id)
            } else {
              next.delete(data.user_id)
            }
            return next
          })
        }
      } catch (err) {
        console.error('Failed to parse presence message:', err)
      }
    }

    return () => {
      ws.close()
    }
  }, [user])

  const isUserOnline = useCallback((userId: number) => {
    return onlineUsers.has(userId)
  }, [onlineUsers])

  return {
    isConnected,
    onlineUsers: Array.from(onlineUsers),
    isUserOnline,
  }
}
