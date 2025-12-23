import { useState, useEffect, useRef } from 'react'
import { useParams } from 'react-router-dom'
import api from '../services/api'
import { fetchChannelMessages } from '../services/channels'
import Message from '../components/Chat/Message'
import { Send } from 'lucide-react'

export default function ChannelView() {
  const { channelId } = useParams<{ channelId: string }>()
  const [channelName, setChannelName] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  const [messages, setMessages] = useState<any[] | null>(null)
  const [loadingMessages, setLoadingMessages] = useState(false)
  const [messagesError, setMessagesError] = useState<string | null>(null)
  const [hasMore, setHasMore] = useState<boolean>(false)
  const [loadingOlder, setLoadingOlder] = useState(false)

  // Message input state
  const [newMessage, setNewMessage] = useState('')
  const [sending, setSending] = useState(false)
  const messagesEndRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!channelId) return
    setLoading(true)
    api.get(`/api/channels/${channelId}`)
      .then((res) => setChannelName(res.data.display_name || res.data.name || `Channel ${channelId}`))
      .catch(() => setChannelName(`Channel ${channelId}`))
      .finally(() => setLoading(false))
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

  // Scroll to bottom when new messages arrive
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  async function loadOlder() {
    if (!messages || messages.length === 0) return
    setLoadingOlder(true)
    setMessagesError(null)
    try {
      const oldest = messages[0]
      const beforeId = oldest.id
      const res = await fetchChannelMessages(Number(channelId), beforeId)
      setMessages(prev => (prev ? [...res.messages, ...prev] : res.messages))
      setHasMore(res.has_more)
    } catch (err) {
      console.error('Failed to load older messages', err)
      setMessagesError('Failed to load messages')
    } finally {
      setLoadingOlder(false)
    }
  }

  async function handleSendMessage(e: React.FormEvent) {
    e.preventDefault()
    if (!newMessage.trim() || !channelId || sending) return

    setSending(true)
    try {
      const response = await api.post('/api/messages/', {
        content: newMessage.trim(),
        channel_id: Number(channelId)
      })
      // Optimistically append the new message
      const sentMessage = response.data
      setMessages(prev => prev ? [...prev, sentMessage] : [sentMessage])
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
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="p-4 border-b border-gray-700">
        <h1 className="text-xl font-semibold">{loading ? 'Loading…' : (channelName || 'Channel')}</h1>
      </div>

      {/* Messages area */}
      <div className="flex-1 overflow-y-auto p-4">
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
              {messages.map((m:any) => (
                <Message key={m.id} message={{ author: m.author_username, content: m.content, created_at: m.created_at }} />
              ))}
            </div>
            <div ref={messagesEndRef} />
          </div>
        )}
      </div>

      {/* Message input */}
      <div className="p-4 border-t border-gray-700">
        <form onSubmit={handleSendMessage} className="flex gap-2">
          <input
            type="text"
            value={newMessage}
            onChange={(e) => setNewMessage(e.target.value)}
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
  )
}



