import { createContext, useContext, useEffect, useRef, useState, useCallback, type ReactNode, type FC } from 'react'
import { useAuthStore } from '../stores/authStore'
import { connectSocket, getSocket, onSocketEvent, joinChannel as socketJoinChannel, leaveChannel as socketLeaveChannel, isSocketConnected } from '../realtime'

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

export const ChatSocketProvider: FC<{ children: ReactNode }> = ({ children }) => {
  const token = useAuthStore((s) => s.token)
  const channelRef = useRef<number | null>(null)
  const listenersRef = useRef<Set<MessageHandler>>(new Set())
  const [wsStatus, setWsStatus] = useState<WSStatus>('disconnected')
  const [typingUsers, setTypingUsers] = useState<Array<{ id: number; name: string }>>([])
  const typingTimeoutRef = useRef<Map<number, number>>(new Map())

  // Ensure Socket.IO is connected and mirror connection status
  useEffect(() => {
    if (!token) {
      setWsStatus('disconnected')
      return
    }

    const sock = connectSocket()
    if (sock && isSocketConnected()) setWsStatus('connected')
    else setWsStatus('connecting')

    // Log the socket id for runtime verification
    try {
      const realSock = getSocket()
      console.log('[ChatSocketContext] using socket id', realSock?.id)
    } catch (err) { /* ignore */ }

    const onConnect = () => setWsStatus('connected')
    const onDisconnect = () => setWsStatus('disconnected')
    const onError = () => setWsStatus('error')

    try {
      const realSock = getSocket()
      realSock?.on('connect', onConnect)
      realSock?.on('disconnect', onDisconnect)
      realSock?.on('connect_error', onError)
    } catch (err) {
      /* ignore */
    }

    return () => {
      try {
        const realSock = getSocket()
        realSock?.off('connect', onConnect)
        realSock?.off('disconnect', onDisconnect)
        realSock?.off('connect_error', onError)
      } catch (err) {
        /* ignore */
      }
    }
  }, [token])

  // Subscribe to global Socket.IO events and dispatch into local listeners
  useEffect(() => {
    // message:new -> normalize to WS-like { type: 'message', ...payload } for onMessage handlers
    const unsubMsgNew = onSocketEvent<any>('message:new', (data) => {
      // deliver to listeners only if it matches current channel
      if (channelRef.current && data.channel_id === channelRef.current) {
        listenersRef.current.forEach(h => {
          try { h({ type: 'message', ...data }) } catch (e) { console.error('Chat listener error', e) }
        })
      }
    })

    // typing events update typingUsers (global)
    const unsubTypingStart = onSocketEvent<any>('typing_start', (data) => {
      if (!data?.user_id) return
      setTypingUsers((prev) => {
        if (prev.some((u) => u.id === data.user_id)) return prev
        return [...prev, { id: data.user_id, name: data.username || '' }]
      })
      const existing = typingTimeoutRef.current.get(data.user_id)
      if (existing) clearTimeout(existing)
      const t = window.setTimeout(() => {
        setTypingUsers((prev) => prev.filter((u) => u.id !== data.user_id))
        typingTimeoutRef.current.delete(data.user_id)
      }, 3000) as unknown as number
      typingTimeoutRef.current.set(data.user_id, t)
    })

    const unsubTypingStop = onSocketEvent<any>('typing_stop', (data) => {
      if (!data?.user_id) return
      setTypingUsers((prev) => prev.filter((u) => u.id !== data.user_id))
      const existing = typingTimeoutRef.current.get(data.user_id)
      if (existing) {
        clearTimeout(existing)
        typingTimeoutRef.current.delete(data.user_id)
      }
    })

    // Dispatch other Socket.IO message events into listeners so components using onMessage get a uniform stream
    const unsubMsgUpdated = onSocketEvent<any>('message:updated', (data) => {
      listenersRef.current.forEach(h => { try { h({ type: 'message:updated', ...data }) } catch (e) { console.error(e) } })
    })
    const unsubMsgDeleted = onSocketEvent<any>('message:deleted', (data) => {
      listenersRef.current.forEach(h => { try { h({ type: 'message:deleted', ...data }) } catch (e) { console.error(e) } })
    })

    return () => {
      try { unsubMsgNew() } catch (e) { /* ignore */ }
      try { unsubTypingStart() } catch (e) { /* ignore */ }
      try { unsubTypingStop() } catch (e) { /* ignore */ }
      try { unsubMsgUpdated() } catch (e) { /* ignore */ }
      try { unsubMsgDeleted() } catch (e) { /* ignore */ }
    }
  }, [])

  const connectChannel = useCallback((channelId: number | null) => {
    if (!channelId) return
    channelRef.current = channelId
    // Ensure Socket.IO connected
    connectSocket()
    // Join the channel room on Socket.IO server
    socketJoinChannel(channelId)
    // reflect status
    if (isSocketConnected()) setWsStatus('connected')
    else setWsStatus('connecting')
  }, [])

  const reconnect = useCallback(() => {
    // Force reconnect of Socket.IO
    const sock = getSocket()
    if (!sock) return
    try { sock.disconnect(); } catch (e) {}
    connectSocket()
  }, [])

  const sendMessage = useCallback((content: string) => {
    const sock = getSocket()
    if (!sock || !channelRef.current) return
    try {
      sock.emit('message', { channel_id: channelRef.current, content, timestamp: new Date().toISOString() })
    } catch (err) {
      console.warn('Failed to emit message via socket:', err)
    }
  }, [])

  const sendTyping = useCallback((isTyping: boolean) => {
    const sock = getSocket()
    if (!sock || !channelRef.current) return
    try {
      sock.emit(isTyping ? 'typing_start' : 'typing_stop', { channel_id: channelRef.current })
    } catch (err) {
      console.warn('Failed to emit typing via socket:', err)
    }
  }, [])

  const sendReaction = useCallback((messageId: number, emoji: string, action: 'add' | 'remove') => {
    const sock = getSocket()
    if (!sock || !channelRef.current) return
    try {
      sock.emit(action === 'add' ? 'reaction_add' : 'reaction_remove', { channel_id: channelRef.current, message_id: messageId, emoji })
    } catch (err) {
      console.warn('Failed to emit reaction via socket:', err)
    }
  }, [])

  const onMessage = useCallback((handler: MessageHandler) => {
    listenersRef.current.add(handler)
    return () => { listenersRef.current.delete(handler) }
  }, [])

  // cleanup: leave joined channel when provider unmounts
  useEffect(() => {
    return () => {
      if (channelRef.current) {
        try { socketLeaveChannel(channelRef.current) } catch (e) { /* ignore */ }
      }
    }
  }, [])

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
