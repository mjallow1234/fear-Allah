import { createContext, useContext, useEffect, useRef, useState, useCallback, type ReactNode, type FC } from 'react'
import { useAuthStore } from '../stores/authStore'

type WSStatus = 'connecting' | 'connected' | 'disconnected' | 'error'

type MessageHandler = (data: any) => void

interface ChatSocketContextValue {
  currentChannel: number | null
  connectChannel: (channelId: number | null) => void
  sendMessage: (content: string) => void
  sendTyping: (isTyping: boolean) => void
  sendReaction: (messageId: number, emoji: string, action: 'add' | 'remove') => void
  wsStatus: WSStatus
  typingUsers: Array<{ id: number; name: string }>
  onMessage: (handler: MessageHandler) => () => void
  reconnect: () => void
}

const ChatSocketContext = createContext<ChatSocketContextValue | undefined>(undefined)

export function useChatSocket() {
  const ctx = useContext(ChatSocketContext)
  if (!ctx) throw new Error('useChatSocket must be used within ChatSocketProvider')
  return ctx
}

export const ChatSocketProvider: FC<{ children: ReactNode; channelId?: number | null }> = ({ children, channelId }) => {
  const token = useAuthStore((s) => s.token)
  const user = useAuthStore((s) => s.user)
  const wsRef = useRef<WebSocket | null>(null)
  const channelRef = useRef<number | null>(null)
  const listenersRef = useRef<Set<MessageHandler>>(new Set())
  const heartbeatRef = useRef<number | null>(null)
  const reconnectTimeoutRef = useRef<number | null>(null)
  const reconnectAttemptsRef = useRef<number>(0)
  const [wsStatus, setWsStatus] = useState<WSStatus>('disconnected')
  const [typingUsers, setTypingUsers] = useState<Array<{ id: number; name: string }>>([])
  const typingTimeoutRef = useRef<Map<number, number>>(new Map())

  const connect = useCallback((channelId: number) => {
    const currentUser = user
    const currentToken = token
    if (!channelId || !currentUser || !currentToken) return

    // Guard: if ws exists and channel unchanged, do nothing
    if (wsRef.current && channelRef.current === channelId && wsRef.current.readyState === WebSocket.OPEN) {
      console.log('[ChatSocket] existing ws open and channel unchanged; not reconnecting')
      return
    }

    // Close existing if channel changes
    if (wsRef.current) {
      try {
        wsRef.current.close()
      } catch (e) {}
      wsRef.current = null
    }

    channelRef.current = channelId

    const wsUrl = `/ws/chat/${channelId}?token=${encodeURIComponent(currentToken)}`

    console.log('[ChatSocket] connect ->', wsUrl)
    setWsStatus('connecting')

    const ws = new WebSocket(wsUrl)
    wsRef.current = ws

    ws.onopen = () => {
      console.log('[ChatSocket] onopen for channel', channelId)
      setWsStatus('connected')
      reconnectAttemptsRef.current = 0

      // heartbeat every 25s
      heartbeatRef.current = window.setInterval(() => {
        if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
          try { wsRef.current.send(JSON.stringify({ type: 'heartbeat' })) } catch (e) {}
        }
      }, 25000)
    }

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data)

        // Internal handling for typing users (so consumers can read typingUsers from context)
        if (data.type === 'typing_start' && data.user_id && data.username) {
          setTypingUsers((prev) => {
            if (prev.some((u) => u.id === data.user_id)) return prev
            return [...prev, { id: data.user_id, name: data.username }]
          })

          // clear existing timeout and set new one
          const existing = typingTimeoutRef.current.get(data.user_id)
          if (existing) clearTimeout(existing)
          const t = window.setTimeout(() => {
            setTypingUsers((prev) => prev.filter((u) => u.id !== data.user_id))
            typingTimeoutRef.current.delete(data.user_id)
          }, 3000) as unknown as number
          typingTimeoutRef.current.set(data.user_id, t)
        }

        if (data.type === 'typing_stop' && data.user_id) {
          setTypingUsers((prev) => prev.filter((u) => u.id !== data.user_id))
          const existing = typingTimeoutRef.current.get(data.user_id)
          if (existing) {
            clearTimeout(existing)
            typingTimeoutRef.current.delete(data.user_id)
          }
        }

        // Dispatch to listeners
        listenersRef.current.forEach((h) => {
          try { h(data) } catch (e) { console.error('Chat listener error', e) }
        })
      } catch (e) {
        console.error('Failed to parse ws message', e)
      }
    }

    ws.onclose = (evt) => {
      console.log('[ChatSocket] onclose code=', (evt as CloseEvent).code)
      setWsStatus('disconnected')

      if (heartbeatRef.current) {
        clearInterval(heartbeatRef.current)
        heartbeatRef.current = null
      }

      // schedule reconnect unless channel changed or token missing
      if (channelRef.current === channelId && token) {
        const attempts = reconnectAttemptsRef.current
        const base = 3000
        const maxDelay = 60000
        const delay = Math.min(base * (2 ** attempts), maxDelay) + Math.floor(Math.random() * 1000)
        reconnectAttemptsRef.current = attempts + 1
        reconnectTimeoutRef.current = window.setTimeout(() => {
          connect(channelId)
        }, delay) as unknown as number
      }
    }

    ws.onerror = (err) => {
      console.error('[ChatSocket] ws error', err)
      setWsStatus('error')
    }
  }, [token, user])

  const disconnect = useCallback((reason?: string) => {
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current)
      reconnectTimeoutRef.current = null
    }
    if (heartbeatRef.current) {
      clearInterval(heartbeatRef.current)
      heartbeatRef.current = null
    }
    if (wsRef.current) {
      try { wsRef.current.close() } catch (e) {}
      wsRef.current = null
    }
    channelRef.current = null
    setWsStatus('disconnected')
    if (reason) console.log('[ChatSocket] disconnected:', reason)
  }, [])

  // connect/disconnect on logout
  useEffect(() => {
    if (!token) {
      disconnect('logout or token removed')
    }
  }, [token, disconnect])

  // API
  const connectChannel = useCallback((channelId: number | null) => {
    if (!channelId) {
      // no-op
      return
    }
    // If same channel and ws open -> nothing
    if (wsRef.current && channelRef.current === channelId && wsRef.current.readyState === WebSocket.OPEN) return
    connect(channelId)
  }, [connect])

  // optional prop-driven channel auto-connect. Only runs when WS runtime flag is enabled.
  useEffect(() => {
    try {
      const enabled = typeof window !== 'undefined' && !!(window as any).__ENABLE_WEBSOCKETS__
      if (!enabled) return
    } catch (e) {
      return
    }

    if (channelId) {
      connectChannel(channelId)
      return () => {
        disconnect('channel prop removed or provider unmounted')
      }
    }
  }, [channelId, connectChannel, disconnect])

  const reconnect = useCallback(() => {
    if (!channelRef.current) return
    // Force immediate reconnect by closing and calling connect()
    if (wsRef.current) {
      try { wsRef.current.close() } catch (e) {}
      wsRef.current = null
    }
    connect(channelRef.current)
  }, [connect])

  const sendMessage = useCallback((content: string) => {
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ type: 'message', content, timestamp: new Date().toISOString() }))
    }
  }, [])

  const sendTyping = useCallback((isTyping: boolean) => {
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ type: isTyping ? 'typing_start' : 'typing_stop' }))
    }
  }, [])

  const sendReaction = useCallback((messageId: number, emoji: string, action: 'add' | 'remove') => {
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ type: action === 'add' ? 'reaction_add' : 'reaction_remove', message_id: messageId, emoji }))
    }
  }, [])

  const onMessage = useCallback((handler: MessageHandler) => {
    listenersRef.current.add(handler)
    return () => { listenersRef.current.delete(handler) }
  }, [])

  // clean up on unmount
  useEffect(() => {
    return () => {
      disconnect('provider unmount')
    }
  }, [disconnect])

  const value: ChatSocketContextValue = {
    currentChannel: channelRef.current,
    connectChannel,
    sendMessage,
    sendTyping,
    sendReaction,
    wsStatus,
    typingUsers,
    onMessage,
    reconnect,
  }

  return (
    <ChatSocketContext.Provider value={value}>
      {children}
    </ChatSocketContext.Provider>
  )
}
