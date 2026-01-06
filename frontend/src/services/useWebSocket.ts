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

export interface Attachment {
  id: number
  filename: string
  file_size?: number
  mime_type?: string
  url: string
  created_at?: string
}

export interface Message {
  id: number
  content: string
  user_id: number
  username: string
  channel_id: number
  timestamp: string
  reactions: Reaction[]
  attachments?: Attachment[]
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

// Small runtime flag to opt in to WebSocket usage. Default: DISABLED in dev/devops unless explicitly enabled.
function websocketsEnabled() {
  try {
    // Runtime global flag set by devs when WebSockets should be enabled
    // e.g. window.__ENABLE_WEBSOCKETS__ = true
    if (typeof window === 'undefined') return false
    return !!(window as any).__ENABLE_WEBSOCKETS__
  } catch (e) {
    return false
  }
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
  const [wsStatus, setWsStatus] = useState<'connecting' | 'connected' | 'disconnected' | 'error'>('disconnected')
  const [typingUsers, setTypingUsers] = useState<Map<number, string>>(new Map())
  const typingTimeoutRef = useRef<Map<number, ReturnType<typeof setTimeout>>>(new Map())
  const reconnectTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const reconnectAttemptsRef = useRef<number>(0)
  const currentChannelRef = useRef<number>(channelId)
  // diagnostic: unique id for this connection to trace lifecycle
  const connectionId = useRef(Math.random().toString(36).slice(2))
  const manualCloseRef = useRef<boolean>(false)
  
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
  const token = useAuthStore((state) => state.token)
  const userRef = useRef(user)
  const tokenRef = useRef(token)

  useEffect(() => {
    userRef.current = user
    tokenRef.current = token
  }, [user, token])

  const disconnect = useCallback(() => {
    console.log(`[WS ${connectionId.current}] disconnect (manual)`)

    // Mark manual close so onclose doesn't schedule reconnect
    manualCloseRef.current = true

    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current)
      reconnectTimeoutRef.current = null
    }
    // reset reconnect attempts when manually disconnecting
    reconnectAttemptsRef.current = 0
    if (wsRef.current) {
      wsRef.current.close()
      wsRef.current = null
    }
    setIsConnected(false)
    setWsStatus('disconnected')
  }, [])

  const connect = useCallback(() => {
    const currentUser = userRef.current
    const currentToken = tokenRef.current
    const currentChannel = currentChannelRef.current
    
    if (!currentChannel || !currentUser) return

    // Ensure manualCloseRef is cleared when initiating a new connect
    manualCloseRef.current = false

    // Close existing connection before opening new one
    if (wsRef.current) {
      wsRef.current.close()
      wsRef.current = null
    }

    // Force WebSocket URL from VITE_API_URL (do not use window.location)
    const apiBase = import.meta.env.VITE_API_URL || 'http://localhost:18002'
    if (!import.meta.env.VITE_API_URL) {
      console.warn('VITE_API_URL is not set; falling back to http://localhost:18002')
    }

    const wsBase = apiBase.replace(/^http/, 'ws')
    // Prefer token auth for chat WebSocket (token required)
    const token = currentToken
    if (!token) {
      throw new Error('WebSocket requires an auth token')
    }

    const wsUrl = `${wsBase}/ws/chat/${currentChannel}?token=${encodeURIComponent(token)}`

    console.log(`[WS ${connectionId.current}] connect -> ${wsUrl}`)
    setWsStatus('connecting')
    const ws = new WebSocket(wsUrl)
    wsRef.current = ws

    ws.onopen = () => {
      console.log(`[WS ${connectionId.current}] onopen for channel ${currentChannel}`)
      setIsConnected(true)
      setWsStatus('connected')
      // reset backoff attempts after successful connect
      reconnectAttemptsRef.current = 0

      // Start heartbeat to keep connection alive (every 25s)
      const heartbeatInterval = setInterval(() => {
        if (ws.readyState === WebSocket.OPEN) {
          try {
            ws.send(JSON.stringify({ type: 'heartbeat' }))
          } catch (err) {
            console.warn('Failed to send heartbeat:', err)
          }
        }
      }, 25000)

      // Ensure heartbeat is cleared on close
      const existingOnClose = ws.onclose
      ws.onclose = (evt) => {
        clearInterval(heartbeatInterval)
        if (existingOnClose) existingOnClose.call(ws, evt as CloseEvent)
      }
    }

    ws.onmessage = (event) => {
      try {
        const data: WebSocketMessage = JSON.parse(event.data)
        const callbacks = callbacksRef.current

        // Diagnostic: log heartbeat_ack if received
        if ((data as any).type === 'heartbeat_ack') {
          console.log(`[WS ${connectionId.current}] heartbeat_ack received`)
        }
        
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

    ws.onclose = (evt) => {
      console.log(`[WS ${connectionId.current}] onclose code=${(evt as CloseEvent).code} reason=${(evt as CloseEvent).reason} wasClean=${(evt as CloseEvent).wasClean}`)
      setIsConnected(false)
      setWsStatus('disconnected')

      // Do not schedule reconnect if this close was manual (intentional)
      if (manualCloseRef.current) {
        console.log(`[WS ${connectionId.current}] manual close, not scheduling reconnect`)
        return
      }

      // Only attempt reconnection if this is still the current channel
      if (currentChannelRef.current === currentChannel && userRef.current) {
        const attempts = reconnectAttemptsRef.current || 0
        const base = 3000
        const maxDelay = 60000
        const delay = Math.min(base * (2 ** attempts), maxDelay) + Math.floor(Math.random() * 1000)
        console.log(`[WS ${connectionId.current}] Scheduling reconnect in ${delay}ms (attempt ${attempts + 1})`)
        reconnectAttemptsRef.current = attempts + 1
        reconnectTimeoutRef.current = setTimeout(() => {
          connect()
        }, delay)
      }
    }

    ws.onerror = (error) => {
      console.error('WebSocket error:', error)
      setWsStatus('error')
    }
  }, []) // No dependencies - uses refs instead

  // Connect/disconnect when channelId or user changes
  useEffect(() => {
    // Do not auto-initialize WebSocket connections unless explicitly enabled at runtime
    if (!websocketsEnabled()) {
      if (currentChannelRef.current) {
        // ensure we disconnect any existing connection
        disconnect()
      }
      return
    }

    currentChannelRef.current = channelId
    
    if (!channelId || !token) {
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
  }, [channelId, token])

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
    wsStatus,
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
  const startedRef = useRef<boolean>(false)
  const [isConnected, setIsConnected] = useState(false)
  // store online user ids
  const [onlineUsersSet, setOnlineUsersSet] = useState<Set<string>>(new Set())
  // optional map for usernames/status if provided by server
  const userInfoRef = useRef<Map<string, { username?: string; status?: string; last_seen?: string; origin?: string; appliedAt?: number }>>(new Map())
  const reconnectAttemptsRef = useRef<number>(0)
  const reconnectTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const eventHandlersRef = useRef<Set<(data: any) => void>>(new Set())
  
  const user = useAuthStore((state) => state.user)

  useEffect(() => {
    // Respect runtime opt-in flag: do not start Presence unless explicitly enabled
    if (!websocketsEnabled()) {
      // ensure any existing presence ws is closed and cleanup scheduled reconnects
      startedRef.current = false
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current)
        reconnectTimeoutRef.current = null
      }
      wsRef.current?.close()
      return
    }

    if (!user) return
    if (startedRef.current) return // already started

    const start = () => {
      const apiBase = import.meta.env.VITE_API_URL || 'http://localhost:18002'
      if (!import.meta.env.VITE_API_URL) {
        console.warn('VITE_API_URL is not set; falling back to http://localhost:18002')
      }

      const wsBase = apiBase.replace(/^http/, 'ws')
      const wsUrl = `${wsBase}/ws/presence?user_id=${user.id}&username=${encodeURIComponent(
        user.username || user.display_name || ''
      )}`

      console.log('WS presence URL (FORCED):', wsUrl)
      const ws = new WebSocket(wsUrl)
      wsRef.current = ws

      ws.onopen = () => {
        setIsConnected(true)
        startedRef.current = true
        // reset reconnection attempts
        reconnectAttemptsRef.current = 0
        console.log('[PRESENCE] connected')

        // Send heartbeat every 30 seconds
        const heartbeatInterval = setInterval(() => {
          if (ws.readyState === WebSocket.OPEN) {
            ws.send(JSON.stringify({ type: 'heartbeat' }))
          }
        }, 30000)

        ws.onclose = () => {
          clearInterval(heartbeatInterval)
          setIsConnected(false)
          console.log('[PRESENCE] disconnected')
        }
      }

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data)
          console.log('[PRESENCE] update received', data)

          if (data.type === 'presence_list') {
            // data.users can be either array of ids or array of user objects
            const users = data.users || []
            const ids: string[] = users.map((u: any) => (typeof u === 'object' ? String(u.user_id) : String(u)))
            // populate userInfo map if available
            users.forEach((u: any) => {
              if (u && typeof u === 'object' && u.user_id) {
                userInfoRef.current.set(String(u.user_id), { username: u.username, status: u.status })
              }
            })
            setOnlineUsersSet(new Set(ids))
          } else if (data.type === 'presence_update') {
            const uid = String(data.user_id)
            // Incoming presence info may include last_seen and origin. Use those plus status to avoid
            // flipping state on duplicate or out-of-order messages. If nothing changed, ignore.
            const incoming = {
              username: data.username,
              status: data.status,
              last_seen: (data as any).last_seen,
              origin: (data as any).origin,
            }

            const prev = userInfoRef.current.get(uid) as any

            // Exact duplicate -> ignore
            const unchanged = prev && prev.status === incoming.status && prev.last_seen === incoming.last_seen && prev.origin === incoming.origin && prev.username === incoming.username
            if (unchanged) return

            const now = Date.now()
            // If we've applied a change recently, avoid flipping state too quickly (debounce transient updates)
            if (prev && prev.status !== incoming.status && (now - (prev.appliedAt || 0) < 2000)) {
              console.log('[PRESENCE] ignoring transient flip', uid, prev.status, '->', incoming.status)
              return
            }

            // Apply update with appliedAt timestamp
            userInfoRef.current.set(uid, { ...incoming, appliedAt: now })
            setOnlineUsersSet((prevSet) => {
              const next = new Set(prevSet)
              if (incoming.status === 'online') next.add(uid)
              else next.delete(uid)
              return next
            })
          }

          // Notify general event handlers (channel_created, etc.)
          try {
            for (const h of Array.from(eventHandlersRef.current)) {
              try { h(data) } catch (e) { console.error('presence event handler error', e) }
            }
          } catch (e) {
            console.error('Error dispatching presence event handlers', e)
          }
        } catch (err) {
          console.error('Failed to parse presence message:', err)
        }
      }

      // attach a closure handler for the most recent ws
      const onCloseHandler = () => {
        if (reconnectTimeoutRef.current) {
          clearTimeout(reconnectTimeoutRef.current)
          reconnectTimeoutRef.current = null
        }
        const attempts = reconnectAttemptsRef.current || 0
        const base = 3000
        const maxDelay = 60000
        const delay = Math.min(base * (2 ** attempts), maxDelay) + Math.floor(Math.random() * 1000)
        console.log(`Presence reconnect scheduled in ${delay}ms (attempt ${attempts + 1})`)
        reconnectAttemptsRef.current = attempts + 1
        reconnectTimeoutRef.current = setTimeout(() => {
          start()
        }, delay)
      }

      if (wsRef.current) {
        wsRef.current.onclose = () => {
          setIsConnected(false)
          onCloseHandler()
        }
      }
    }

    start()

    return () => {
      // allow restart on next mount/user change
      startedRef.current = false
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current)
        reconnectTimeoutRef.current = null
      }
      wsRef.current?.close()
    }
  }, [user])

  const isUserOnline = useCallback((userId: number | string) => {
    return onlineUsersSet.has(String(userId))
  }, [onlineUsersSet])

  const onlineUsers = Array.from(onlineUsersSet).map((id) => ({
    user_id: id,
    username: userInfoRef.current.get(id)?.username,
    status: userInfoRef.current.get(id)?.status || 'online',
  }))

  return {
    isConnected,
    onlineUsers,
    isUserOnline,
    onEvent: (handler: (data: any) => void) => {
      eventHandlersRef.current.add(handler)
      return () => eventHandlersRef.current.delete(handler)
    }
  }
}
