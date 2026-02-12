import { useState, useEffect } from 'react'
import { useParams } from 'react-router-dom'
import api from '../services/api'
import { Users } from 'lucide-react'
import ConversationMessageView from '../components/ConversationMessageView'
import { usePresenceStore } from '../stores/presenceStore'

export default function ChannelView() {
  const { channelId } = useParams<{ channelId: string }>()
  const onlineUserIds = usePresenceStore((state) => state.onlineUserIds)
  const [channelName, setChannelName] = useState<string | null>(null)
  const [channelMembers, setChannelMembers] = useState<{ id: number; user_id?: number; username?: string }[]>([])
  const [memberUsernames, setMemberUsernames] = useState<Record<number, string>>({})
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    if (!channelId) return
    setLoading(true)
    api.get(`/api/channels/${channelId}`)
      .then((res) => {
        setChannelName(res.data.display_name || res.data.name || `Channel ${channelId}`)
      })
      .catch(() => setChannelName(`Channel ${channelId}`))
      .finally(() => setLoading(false))

    api.get(`/api/channels/${channelId}/members`)
      .then((res) => {
        const members = Array.isArray(res.data) ? res.data : []
        setChannelMembers(members)
        const usernameMap: Record<number, string> = {}
        for (const m of members) {
          const userId = m.user_id || m.id
          if (userId && m.username) usernameMap[userId] = m.username
        }
        setMemberUsernames(usernameMap)
      })
      .catch(() => setChannelMembers([]))
  }, [channelId])

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
    <div className="flex h-full relative">
      <div className="flex flex-col flex-1 h-full">
        {/* Header */}
        <div className="p-4 border-b border-gray-700 flex items-center justify-between">
          <h1 className="text-xl font-semibold">{loading ? 'Loading…' : (channelName || 'Channel')}</h1>
          {channelMembers.length > 0 && (
            <div className="flex items-center gap-2 text-sm text-gray-400">
              <Users size={16} />
              <span>
                {channelMembers.filter(m => onlineUserIds.has(Number(m.user_id || m.id))).length} online / {channelMembers.length} members
              </span>
            </div>
          )}
        </div>

        {/* Conversation message engine */}
        <ConversationMessageView mode="channel" channelId={Number(channelId)} memberUsernames={memberUsernames} />
      </div>
    </div>
  )
}



