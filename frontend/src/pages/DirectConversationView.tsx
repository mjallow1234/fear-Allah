import { useState, useEffect, useRef } from 'react'
import { useParams } from 'react-router-dom'
import Message from '../components/Chat/Message'
import { useAuthStore } from '../stores/authStore'
import { fetchDirectConversationMessages, postDirectConversationMessage } from '../services/directConversations'
import { onSocketEvent, joinRoom, leaveRoom } from '../realtime'

export default function DirectConversationView() {
  const { convId } = useParams<{ convId: string }>()
  const currentUser = useAuthStore((s) => s.user)
  const [messages, setMessages] = useState<any[] | null>(null)
  const [loadingMessages, setLoadingMessages] = useState(false)
  const [newMessage, setNewMessage] = useState('')
  const [sending, setSending] = useState(false)
  const seenMessageIdsRef = useRef<Set<number>>(new Set())
  const shouldScrollToBottom = useRef(true)
  const messagesEndRef = useRef<HTMLDivElement | null>(null)

  // Fetch messages
  useEffect(() => {
    if (!convId) return
    const id = Number(convId)
    let cancelled = false
    setLoadingMessages(true)
    fetchDirectConversationMessages(id)
      .then(({ messages: list }) => {
        if (cancelled) return
        setMessages(list)
        seenMessageIdsRef.current = new Set((list || []).map((m: any) => m.id))
      })
      .catch((err) => console.error('Failed to fetch DM messages:', err))
      .finally(() => setLoadingMessages(false))

    // Join socket room for DMs
    const room = `dm:${id}`
    joinRoom(room)

    // Subscribe to socket events
    const unsubscribeMessage = onSocketEvent('message:new', (data: any) => {
      if (!data) return
      if (data.direct_conversation_id !== id) return
      if (data.author_id === currentUser?.id) return
      if (seenMessageIdsRef.current.has(data.id)) return
      seenMessageIdsRef.current.add(data.id)
      setMessages((prev) => {
        if (!prev) return [data]
        if (prev.some((m) => m.id === data.id)) return prev
        shouldScrollToBottom.current = true
        return [...prev, data]
      })
    })

    return () => {
      cancelled = true
      unsubscribeMessage()
      leaveRoom(room)
    }
  }, [convId, currentUser])

  // Send message
  const sendMessage = async () => {
    if (!convId || !newMessage.trim()) return
    const id = Number(convId)
    setSending(true)
    try {
      const msg = await postDirectConversationMessage(id, newMessage.trim())
      // Append message returned by server
      setMessages((prev) => {
        if (!prev) return [msg]
        if (prev.some((m) => m.id === msg.id)) return prev
        shouldScrollToBottom.current = true
        return [...prev, msg]
      })
      setNewMessage('')
    } catch (err) {
      console.error('Failed to send DM:', err)
    } finally {
      setSending(false)
    }
  }

  return (
    <div className="flex-1 flex flex-col h-full">
      <div className="flex-1 overflow-y-auto p-4" style={{ backgroundColor: 'var(--main-bg)' }}>
        {loadingMessages ? (
          <div className="text-[#949ba4]">Loading messages...</div>
        ) : messages && messages.length === 0 ? (
          <div className="text-[#949ba4]">No messages yet</div>
        ) : (
          messages?.map((m) => <Message key={m.id} message={m} />)
        )}
        <div ref={messagesEndRef} />
      </div>

      <div className="p-4 border-t" style={{ borderTop: '1px solid var(--sidebar-border)' }}>
        <div className="flex gap-2">
          <input
            type="text"
            value={newMessage}
            onChange={(e) => setNewMessage(e.target.value)}
            onKeyDown={(e) => { if (e.key === 'Enter') sendMessage() }}
            placeholder="Write a message..."
            className="flex-1 bg-transparent border border-[#3f4147] rounded px-3 py-2 text-white focus:outline-none"
          />
          <button
            onClick={sendMessage}
            disabled={sending || !newMessage.trim()}
            className="bg-[#5865f2] hover:bg-[#4752c4] disabled:opacity-50 text-white px-4 rounded"
          >
            Send
          </button>
        </div>
      </div>
    </div>
  )
}
