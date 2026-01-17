import { useState, useEffect, useLayoutEffect, useRef, useCallback } from 'react'
import { useParams } from 'react-router-dom'
import api from '../services/api'
import { fetchChannelMessages } from '../services/channels'
import Message from '../components/Chat/Message'
import ThreadPanel from '../components/ThreadPanel'
import { Send, Users } from 'lucide-react'
import { joinChannel, leaveChannel, onSocketEvent } from '../realtime'
import { useAuthStore } from '../stores/authStore'
import { usePresenceStore } from '../stores/presenceStore'
import { useTypingStore, formatTypingIndicator } from '../stores/typingStore'
import { useReadReceiptStore, formatSeenBy } from '../stores/readReceiptStore'
import { emitTypingStart, emitTypingStop, subscribeToTyping } from '../realtime/typing'
import { fetchChannelReads, markChannelRead, clearPendingMarkRead } from '../realtime/readReceipts'

export default function ChannelView() {
  const { channelId } = useParams<{ channelId: string }>()
  const currentUser = useAuthStore((state) => state.user)
  const onlineUserIds = usePresenceStore((state) => state.onlineUserIds)
  const { addTypingUser, removeTypingUser, getTypingUsers, clearChannel } = useTypingStore()
  const { getUsersWhoReadMessage } = useReadReceiptStore()
  const [channelName, setChannelName] = useState<string | null>(null)
  const [channelMembers, setChannelMembers] = useState<{ id: number; user_id?: number; username?: string }[]>([])
  const [memberUsernames, setMemberUsernames] = useState<Record<number, string>>({})
  const [loading, setLoading] = useState(false)

  const [messages, setMessages] = useState<any[] | null>(null)
  const [loadingMessages, setLoadingMessages] = useState(false)
  const [messagesError, setMessagesError] = useState<string | null>(null)
  const [hasMore, setHasMore] = useState<boolean>(false)
  const [loadingOlder, setLoadingOlder] = useState(false)
  // Track seen message IDs to prevent duplicates when simultaneous socket handlers fire
  const seenMessageIdsRef = useRef<Set<number>>(new Set())

  // Message input state
  const [newMessage, setNewMessage] = useState('')
  const [sending, setSending] = useState(false)
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const messagesContainerRef = useRef<HTMLDivElement>(null)
  
  // Track if we should scroll to bottom (only for new messages, not older)
  const shouldScrollToBottom = useRef(true)
  
  // Store scroll position before loading older messages
  const scrollRestoreInfo = useRef<{ scrollHeight: number; scrollTop: number } | null>(null)
  
  // Thread panel state
  const [selectedThread, setSelectedThread] = useState<any | null>(null)

  // Mark channel as read when at bottom with messages
  const markAsReadIfAtBottom = useCallback(() => {
    if (!channelId || !messages || messages.length === 0) return
    
    const container = messagesContainerRef.current
    if (!container) return
    
    // Check if scrolled to bottom (within 100px threshold)
    const isAtBottom = container.scrollHeight - container.scrollTop - container.clientHeight < 100
    
    if (isAtBottom) {
      // Find the last message ID
      const topLevelMessages = messages.filter(m => !m.parent_id)
      if (topLevelMessages.length > 0) {
        const lastMessage = topLevelMessages[topLevelMessages.length - 1]
        markChannelRead(Number(channelId), lastMessage.id)
      }
    }
  }, [channelId, messages])

  useEffect(() => {
    if (!channelId) return
    setLoading(true)
    api.get(`/channels/${channelId}`)
      .then((res) => {
        setChannelName(res.data.display_name || res.data.name || `Channel ${channelId}`)
      })
      .catch(() => setChannelName(`Channel ${channelId}`))
      .finally(() => setLoading(false))
    
    // Fetch channel members for presence count and usernames
    api.get(`/channels/${channelId}/members`)
      .then((res) => {
        const members = Array.isArray(res.data) ? res.data : []
        setChannelMembers(members)
        
        // Build username map for read receipts
        const usernameMap: Record<number, string> = {}
        for (const m of members) {
          const userId = m.user_id || m.id
          if (userId && m.username) {
            usernameMap[userId] = m.username
          }
        }
        setMemberUsernames(usernameMap)
      })
      .catch(() => setChannelMembers([]))
    
    // Fetch initial read receipts for this channel
    fetchChannelReads(Number(channelId))
  }, [channelId])

  useEffect(() => {
    if (!channelId) {
      setMessages(null)
      setHasMore(false)
      return
    }
    let cancelled = false
    setLoadingMessages(true)
    setMessagesError(null)
    fetchChannelMessages(Number(channelId))
      .then(({ messages: list, has_more }) => {
        if (cancelled) return
        setMessages(list)
        setHasMore(has_more)
        // Initialize seenMessageIdsRef with existing messages to avoid duplicates
        seenMessageIdsRef.current = new Set((list || []).map((m: any) => m.id))
      })
      .catch((err) => {
        if (cancelled) return
        console.error('Failed to load messages', err)
        setMessagesError('Failed to load messages')
      })
      .finally(() => {
        if (cancelled) return
        setLoadingMessages(false)
      })
    return () => { cancelled = true }
  }, [channelId])

  // Scroll to bottom only when shouldScrollToBottom is true (new messages, not older)
  useEffect(() => {
    if (shouldScrollToBottom.current) {
      messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
      // Mark as read when scrolling to bottom with new messages
      markAsReadIfAtBottom()
    }
  }, [messages, markAsReadIfAtBottom])

  // Mark as read on scroll
  useEffect(() => {
    const container = messagesContainerRef.current
    if (!container) return
    
    const handleScroll = () => {
      markAsReadIfAtBottom()
    }
    
    container.addEventListener('scroll', handleScroll, { passive: true })
    return () => container.removeEventListener('scroll', handleScroll)
  }, [markAsReadIfAtBottom])

  // Mark as read when channel gains focus
  useEffect(() => {
    const handleFocus = () => {
      markAsReadIfAtBottom()
    }
    
    window.addEventListener('focus', handleFocus)
    return () => window.removeEventListener('focus', handleFocus)
  }, [markAsReadIfAtBottom])

  // Cleanup pending mark-read when leaving channel
  useEffect(() => {
    return () => {
      clearPendingMarkRead()
    }
  }, [channelId])

  // Socket.IO: Join channel room and subscribe to real-time events
  useEffect(() => {
    if (!channelId) return
    
    const numChannelId = Number(channelId)
    const currentUserId = currentUser?.id
    
    // Join the channel room for real-time updates
    joinChannel(numChannelId)
    
    // Subscribe to new messages
    const unsubscribeMessage = onSocketEvent<{
      id: number
      content: string
      channel_id: number
      author_id: number
      author_username: string
      parent_id: number | null
      created_at: string
      is_edited: boolean
      reactions: any[]
    }>('message:new', (data) => {
      // Only handle messages for this channel (top-level only, not thread replies)
      if (data.channel_id !== numChannelId) return
      if (data.parent_id) return  // Thread replies are handled separately
      
      // Skip messages from current user - they're added via REST response
      if (data.author_id === currentUserId) {
        console.log('[Socket.IO] Skipping own message (added via REST):', data.id)
        return
      }
      
      // Prevent duplicates using seenMessageIdsRef (guards against concurrent handlers)
      if (seenMessageIdsRef.current.has(data.id)) {
        console.log('[Socket.IO] Duplicate message ignored by seen set:', data.id)
        return
      }
      seenMessageIdsRef.current.add(data.id)

      // Add message from other users
      setMessages(prev => {
        if (!prev) return [data]
        // Double-check for duplicates
        if (prev.some(m => m.id === data.id)) return prev
        // Scroll to bottom for new real-time messages
        shouldScrollToBottom.current = true
        console.log('[Socket.IO] Adding message from other user:', data.id)
        return [...prev, data]
      })
    })

    // Subscribe to thread replies (update reply count)
    const unsubscribeThread = onSocketEvent<{
      id: number
      parent_id: number
      channel_id: number
    }>('thread:reply', (data) => {
      console.log('[ChannelView] Received thread:reply', data)
      if (data.channel_id !== numChannelId) return

      // Update parent message's thread count
      setMessages(prev => {
        if (!prev) return prev
        return prev.map(m => {
          if (m.id === data.parent_id) {
            return { ...m, thread_count: (m.thread_count || 0) + 1 }
          }
          return m
        })
      })
    })
    
    return () => {
      // Leave channel and unsubscribe on cleanup
      leaveChannel(numChannelId)
      unsubscribeMessage()
      unsubscribeThread()
    }
  }, [channelId, currentUser?.id])

  // Subscribe to typing events
  useEffect(() => {
    if (!channelId) return
    
    const numChannelId = Number(channelId)
    
    // Clear any stale typing state for this channel
    clearChannel(numChannelId)
    
    // Subscribe to typing events
    const unsubscribe = subscribeToTyping(
      numChannelId,
      (userId, username) => addTypingUser(numChannelId, userId, username),
      (userId, _username) => removeTypingUser(numChannelId, userId)
    )
    
    return () => {
      unsubscribe()
      clearChannel(numChannelId)
      // Stop typing if we were typing in this channel
      emitTypingStop(numChannelId)
    }
  }, [channelId, addTypingUser, removeTypingUser, clearChannel])

  // Restore scroll position synchronously after DOM updates when loading older messages
  useLayoutEffect(() => {
    if (scrollRestoreInfo.current && messagesContainerRef.current) {
      const container = messagesContainerRef.current
      const { scrollHeight: oldScrollHeight, scrollTop: oldScrollTop } = scrollRestoreInfo.current
      const newScrollHeight = container.scrollHeight
      // Restore position: new content added at top pushes everything down
      container.scrollTop = newScrollHeight - oldScrollHeight + oldScrollTop
      // Clear the restore info
      scrollRestoreInfo.current = null
      // NOTE: Do NOT re-enable shouldScrollToBottom here - 
      // the useEffect above runs AFTER this and would scroll to bottom!
      // shouldScrollToBottom stays false until user sends a new message
    }
  }, [messages])

  async function loadOlder() {
    if (!messages || messages.length === 0) return
    
    // Capture scroll position before loading
    const container = messagesContainerRef.current
    if (container) {
      scrollRestoreInfo.current = {
        scrollHeight: container.scrollHeight,
        scrollTop: container.scrollTop
      }
    }
    
    // Don't scroll to bottom when loading older messages
    shouldScrollToBottom.current = false
    
    setLoadingOlder(true)
    setMessagesError(null)
    try {
      const oldest = messages[0]
      const beforeId = oldest.id
      const res = await fetchChannelMessages(Number(channelId), beforeId)
      setMessages(prev => (prev ? [...res.messages, ...prev] : res.messages))
      setHasMore(res.has_more)
      // Scroll restoration happens in useLayoutEffect above
    } catch (err) {
      console.error('Failed to load older messages', err)
      setMessagesError('Failed to load messages')
      scrollRestoreInfo.current = null
      shouldScrollToBottom.current = true
    } finally {
      setLoadingOlder(false)
    }
  }

  async function handleSendMessage(e: React.FormEvent) {
    e.preventDefault()
    if (!newMessage.trim() || !channelId || sending) return

    // Enable scroll to bottom for new messages
    shouldScrollToBottom.current = true
    
    // Stop typing indicator when sending
    emitTypingStop(Number(channelId))
    
    setSending(true)
    try {
      const response = await api.post('/messages/', {
        content: newMessage.trim(),
        channel_id: Number(channelId)
      })
      // Optimistically append the new message
      const sentMessage = response.data
      setMessages(prev => prev ? [...prev, sentMessage] : [sentMessage])
      // Mark as seen to avoid duplicate from socket emit
      if (sentMessage?.id) seenMessageIdsRef.current.add(sentMessage.id)
      setNewMessage('')
    } catch (err) {
      console.error('Failed to send message', err)
      // Optionally show error to user
    } finally {
      setSending(false)
    }
  }

  if (!channelId) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="text-center text-gray-400">
          <h2 className="text-xl font-semibold">Select a channel to start chatting</h2>
          <p className="mt-2 text-sm">Choose a channel from the sidebar to begin.</p>
        </div>
      </div>
    )
  }

  return (
    <div className="flex h-full">
      {/* Main channel content */}
      <div className="flex flex-col flex-1">
        {/* Header */}
        <div className="p-4 border-b border-gray-700 flex items-center justify-between">
          <h1 className="text-xl font-semibold">{loading ? 'Loading…' : (channelName || 'Channel')}</h1>
          {channelMembers.length > 0 && (
            <div className="flex items-center gap-2 text-sm text-gray-400">
              <Users size={16} />
              <span>
                {channelMembers.filter(m => onlineUserIds.has(m.id)).length} online / {channelMembers.length} members
              </span>
            </div>
          )}
        </div>

        {/* Messages area */}
        <div ref={messagesContainerRef} className="flex-1 overflow-y-auto p-4">
          {loadingMessages && <div className="text-gray-400">Loading messages…</div>}
          {messagesError && <div className="text-red-500">{messagesError}</div>}

          {!loadingMessages && !messagesError && messages && messages.length === 0 && (
            <div className="text-gray-500 text-center py-8">No messages yet. Start the conversation!</div>
          )}

          {!loadingMessages && !messagesError && messages && messages.length > 0 && (
            <div>
              {hasMore && (
                <div className="mb-4 text-center">
                  <button 
                    className="px-4 py-2 bg-gray-700 hover:bg-gray-600 rounded text-sm transition-colors" 
                    onClick={loadOlder} 
                    disabled={loadingOlder}
                  >
                    {loadingOlder ? 'Loading…' : 'Load older messages'}
                  </button>
                </div>
              )}
              <div className="messages space-y-3">
                {messages.filter(m => !m.parent_id).map((m: any) => (
                  <Message 
                    key={m.id} 
                    message={{ ...m, author_username: m.author_username }} 
                    onClick={setSelectedThread}
                  />
                ))}
              </div>
              
              {/* Seen by indicator - only show on messages sent by current user */}
              {(() => {
                const topLevelMessages = messages.filter(m => !m.parent_id)
                if (topLevelMessages.length === 0) return null
                
                const lastMessage = topLevelMessages[topLevelMessages.length - 1]
                
                // Only show "Seen by" on messages the current user sent
                if (lastMessage.author_id !== currentUser?.id) return null
                
                const readByUserIds = getUsersWhoReadMessage(
                  Number(channelId),
                  lastMessage.id,
                  currentUser?.id
                )
                
                if (readByUserIds.length === 0) return null
                
                // Convert user IDs to usernames
                const usernames = readByUserIds
                  .map(uid => memberUsernames[uid])
                  .filter(Boolean)
                
                const seenText = formatSeenBy(usernames)
                if (!seenText) return null
                
                return (
                  <div className="text-xs text-gray-500 text-right mt-1 pr-2">
                    {seenText}
                  </div>
                )
              })()}
              
              <div ref={messagesEndRef} />
            </div>
          )}
        </div>

        {/* Message input */}
        <div className="p-4 border-t border-gray-700">
          {/* Typing indicator */}
          {(() => {
            const typingUsers = getTypingUsers(Number(channelId))
            const text = formatTypingIndicator(typingUsers)
            if (!text) return null
            return (
              <div className="text-sm text-gray-400 mb-2 animate-pulse">
                {text}
              </div>
            )
          })()}
          <form onSubmit={handleSendMessage} className="flex gap-2">
            <input
              type="text"
              value={newMessage}
              onChange={(e) => {
                setNewMessage(e.target.value)
                // Emit typing if there's content
                if (e.target.value.trim() && channelId) {
                  emitTypingStart(Number(channelId))
                } else if (channelId) {
                  emitTypingStop(Number(channelId))
                }
              }}
              placeholder="Type a message..."
              className="flex-1 px-4 py-2 bg-gray-700 rounded-lg text-white placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500"
              disabled={sending}
            />
            <button
              type="submit"
              disabled={!newMessage.trim() || sending}
              className="px-4 py-2 bg-blue-600 hover:bg-blue-500 disabled:bg-gray-600 disabled:cursor-not-allowed rounded-lg transition-colors flex items-center gap-2"
            >
              <Send size={18} />
              {sending ? 'Sending…' : 'Send'}
            </button>
          </form>
        </div>
      </div>

      {/* Thread panel */}
      {selectedThread && (
        <ThreadPanel 
          parentMessage={selectedThread} 
          onClose={() => setSelectedThread(null)} 
        />
      )}
    </div>
  )
}



