import { useState, useEffect } from 'react'
import { useParams } from 'react-router-dom'
import api from '../services/api'

export default function ChannelView() {
  const { channelId } = useParams<{ channelId: string }>()
  const [channelName, setChannelName] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    if (!channelId) return
    setLoading(true)
    api.get(`/api/channels/${channelId}`)
      .then((res) => setChannelName(res.data.display_name || res.data.name || `Channel ${channelId}`))
      .catch(() => setChannelName(`Channel ${channelId}`))
      .finally(() => setLoading(false))
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
    <div className="p-6">
      <div className="mb-4">
        <h1 className="text-2xl font-semibold">{loading ? 'Loading…' : (channelName || 'Channel')}</h1>
      </div>

      <div className="mt-8 text-center text-gray-500">
        <p className="text-lg font-medium">Chat loading will appear here</p>
        <p className="mt-2 text-sm">Channel messages will load once chat is enabled.</p>
      </div>
    </div>
  )
}











