import { useState, useEffect, useRef } from 'react'
import { X, Send } from 'lucide-react'
import api from '../services/api'
import Message from './Chat/Message'
import { onSocketEvent } from '../realtime'

interface ThreadPanelProps {
  parentMessage: any
  onClose: () => void
}

export default function ThreadPanel({ parentMessage, onClose }: ThreadPanelProps) {
  const [replies, setReplies] = useState<any[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [newReply, setNewReply] = useState('')
  const [sending, setSending] = useState(false)
  const repliesEndRef = useRef<HTMLDivElement>(null)

  // Fetch thread replies
  useEffect(() => {
    setLoading(true)
    setError(null)
    api.get(`/api/messages/${parentMessage.id}/replies`)
      .then(res => {
        setReplies(res.data || [])
      })
      .catch(err => {
        console.error('Failed to load thread', err)
        setError('Failed to load thread')
      })
      .finally(() => {
        setLoading(false)
      })
  }, [parentMessage.id])

  // Subscribe to real-time thread replies
  useEffect(() => {
    const unsubscribe = onSocketEvent<{
      id: number
      content: string
      parent_id: number
      channel_id: number
      author_id: number
      author_username: string
      created_at: string
      is_edited: boolean
      reactions: any[]
    }>('thread:reply', (data) => {
      // Only handle replies to this thread
      if (data.parent_id !== parentMessage.id) return
      
      // Don't add duplicate replies
      setReplies(prev => {
        if (prev.some(r => r.id === data.id)) return prev
        return [...prev, data]
      })
    })
    
    return () => unsubscribe()
  }, [parentMessage.id])

  // Scroll to bottom when new replies arrive
  useEffect(() => {
    repliesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [replies])

  async function handleSendReply(e: React.FormEvent) {
    e.preventDefault()
    if (!newReply.trim() || sending) return

    setSending(true)
    try {
      const response = await api.post(`/api/messages/${parentMessage.id}/reply`, {
        content: newReply.trim()
      })
      const sentReply = response.data
      setReplies(prev => [...prev, sentReply])
      setNewReply('')
    } catch (err) {
      console.error('Failed to send reply', err)
    } finally {
      setSending(false)
    }
  }

  function handleKeyDown(e: React.KeyboardEvent<HTMLInputElement>) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSendReply(e)
    }
  }

  return (
    <div className="w-80 border-l border-gray-700 flex flex-col h-full bg-gray-900">
      {/* Header */}
      <div className="p-3 border-b border-gray-700 flex items-center justify-between">
        <h3 className="font-semibold text-sm">Thread</h3>
        <button
          onClick={onClose}
          className="text-gray-400 hover:text-white transition-colors"
          title="Close thread"
        >
          <X size={18} />
        </button>
      </div>

      {/* Parent message */}
      <div className="p-3 border-b border-gray-700 bg-gray-800">
        <div className="text-xs text-gray-500 mb-1">Original message</div>
        <Message message={parentMessage} />
      </div>

      {/* Replies area */}
      <div className="flex-1 overflow-y-auto p-3">
        {loading && <div className="text-gray-400 text-sm">Loading replies…</div>}
        {error && <div className="text-red-500 text-sm">{error}</div>}

        {!loading && !error && replies.length === 0 && (
          <div className="text-gray-500 text-sm text-center py-4">
            No replies yet. Start the thread!
          </div>
        )}

        {!loading && !error && replies.length > 0 && (
          <div className="space-y-2">
            {replies.map((reply) => (
              <Message key={reply.id} message={reply} />
            ))}
          </div>
        )}
        <div ref={repliesEndRef} />
      </div>

      {/* Reply input */}
      <form onSubmit={handleSendReply} className="p-3 border-t border-gray-700">
        <div className="flex gap-2">
          <input
            type="text"
            value={newReply}
            onChange={(e) => setNewReply(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Reply to thread…"
            className="flex-1 bg-gray-800 text-white rounded px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-blue-500"
            disabled={sending}
          />
          <button
            type="submit"
            disabled={sending || !newReply.trim()}
            className="bg-blue-600 hover:bg-blue-700 disabled:bg-gray-600 disabled:cursor-not-allowed text-white rounded px-3 py-2 transition-colors"
            title="Send reply"
          >
            <Send size={16} />
          </button>
        </div>
      </form>
    </div>
  )
}
