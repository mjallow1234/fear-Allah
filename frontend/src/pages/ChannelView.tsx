import { useState, useEffect } from 'react'
import { useParams } from 'react-router-dom'
import api from '../services/api'
import { fetchChannelMessages } from '../services/channels'
import Message from '../components/Chat/Message'

export default function ChannelView() {
  const { channelId } = useParams<{ channelId: string }>()
  const [channelName, setChannelName] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  const [messages, setMessages] = useState<any[] | null>(null)
  const [loadingMessages, setLoadingMessages] = useState(false)
  const [messagesError, setMessagesError] = useState<string | null>(null)
  const [hasMore, setHasMore] = useState<boolean>(false)
  const [loadingOlder, setLoadingOlder] = useState(false)

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
    <div className="p-6">
      <div className="mb-4">
        <h1 className="text-2xl font-semibold">{loading ? 'Loading…' : (channelName || 'Channel')}</h1>
      </div>

      <div className="mt-4">
        <h3 className="font-semibold mb-2">Messages</h3>

        {loadingMessages && <div>Loading messages…</div>}
        {messagesError && <div className="text-red-500">{messagesError}</div>}

        {!loadingMessages && !messagesError && messages && messages.length === 0 && (
          <div className="text-gray-500">No messages yet</div>
        )}

        {!loadingMessages && !messagesError && messages && messages.length > 0 && (
          <div>
            {hasMore && (
              <div className="mb-2 text-center">
                <button className="px-3 py-1 bg-gray-200 rounded" onClick={loadOlder} disabled={loadingOlder}>
                  {loadingOlder ? 'Loading…' : 'Load older messages'}
                </button>
              </div>
            )}
            <div className="messages space-y-2">
              {messages.map((m:any) => (
                <Message key={m.id} message={{ author: m.author_username, content: m.content, created_at: m.created_at }} />
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}











