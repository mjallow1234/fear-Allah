import { useState, useEffect, useRef } from 'react'
import { X, Send } from 'lucide-react'
import api from '../services/api'
import Message from './Chat/Message'
import { onSocketEvent } from '../realtime'
import { useAuthStore } from '../stores/authStore'
import { useReadReceiptStore, formatSeenBy } from '../stores/readReceiptStore'

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
  const [memberUsernames, setMemberUsernames] = useState<Record<number, string>>({})
  const repliesEndRef = useRef<HTMLDivElement>(null)
  const currentUser = useAuthStore((s) => s.user)
  const seenReplyIdsRef = useRef<Set<number>>(new Set())
  const { getUsersWhoReadMessage } = useReadReceiptStore()

  // Fetch thread replies
  useEffect(() => {
    if (!parentMessage?.id) return
    
    setLoading(true)
    setError(null)
    api.get(`/api/messages/${parentMessage.id}/replies`)
      .then(res => {
        setReplies(res.data || [])
        seenReplyIdsRef.current = new Set((res.data || []).map((r: any) => r.id))
      })
      .catch(err => {
        console.error('Failed to load thread', err)
        setError('Failed to load thread')
      })
      .finally(() => {
        setLoading(false)
      })
  }, [parentMessage.id])

  // Fetch channel members for usernames (for "Seen by" display)
  useEffect(() => {
    if (!parentMessage.channel_id) return
    
    api.get(`/api/channels/${parentMessage.channel_id}/members`)
      .then(res => {
        const members = Array.isArray(res.data) ? res.data : []
        const usernameMap: Record<number, string> = {}
        for (const m of members) {
          const userId = m.user_id || m.id
          if (userId && m.username) {
            usernameMap[userId] = m.username
          }
        }
        setMemberUsernames(usernameMap)
      })
      .catch(() => {})
  }, [parentMessage.channel_id])

  // Subscribe to real-time thread replies
  useEffect(() => {
    if (!parentMessage?.id) return
    
    const currentUserId = currentUser?.id
    console.log('[ThreadPanel] Setting up thread:reply listener for parent:', parentMessage.id, 'currentUserId:', currentUserId)
    
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
      console.log('[ThreadPanel] Received thread:reply event:', data)

      // Only handle replies to this thread
      if (data.parent_id !== parentMessage.id) {
        console.log('[ThreadPanel] Ignoring reply for different thread:', data.parent_id, '!==', parentMessage.id)
        return
      }

      // Skip own replies (sender already added via REST)
      if (data.author_id === currentUserId) {
        console.log('[Socket.IO] Skipping own thread reply', data.id)
        return
      }

      // Prevent duplicates using seenReplyIdsRef
      if (seenReplyIdsRef.current.has(data.id)) {
        console.log('[ThreadPanel] Duplicate reply ignored by seen set:', data.id)
        return
      }
      seenReplyIdsRef.current.add(data.id)

      // Add reply from other user
      setReplies(prev => {
        if (prev.some(r => r.id === data.id)) return prev
        return [...prev, data]
      })
    })

    return () => unsubscribe()
  }, [parentMessage.id, currentUser?.id])

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
      // Mark as seen to avoid duplicate when socket emits
      if (sentReply?.id) seenReplyIdsRef.current.add(sentReply.id)
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
            
            {/* Seen by indicator for thread - only show on last reply if sent by current user */}
            {(() => {
              // Only show "Seen by" if the last reply was sent by current user
              const lastReply = replies[replies.length - 1]
              if (!lastReply || lastReply.author_id !== currentUser?.id) return null
              
              // Get users who have read at least the parent message
              const readByUserIds = getUsersWhoReadMessage(
                parentMessage.channel_id,
                parentMessage.id,
                currentUser?.id
              )
              
              if (readByUserIds.length === 0) return null
              
              const usernames = readByUserIds
                .map(uid => memberUsernames[uid])
                .filter(Boolean)
              
              const seenText = formatSeenBy(usernames)
              if (!seenText) return null
              
              return (
                <div className="text-xs text-gray-500 text-right mt-2">
                  {seenText}
                </div>
              )
            })()}
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
