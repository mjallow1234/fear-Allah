import { Outlet, useParams } from 'react-router-dom'
import { useState, useEffect } from 'react'
import Sidebar from '../components/Sidebar'
import TopBar from '../components/TopBar'
import api from '../services/api'
import { requestNotificationPermission } from '../utils/notifications'

export default function MainLayout() {
  const { channelId } = useParams<{ channelId: string }>()
  const [channelName, setChannelName] = useState('general')

  // Request notification permission on mount
  useEffect(() => {
    requestNotificationPermission()
  }, [])

  useEffect(() => {
    if (channelId) {
      // Fetch channel info
      api.get(`/api/channels/${channelId}`)
        .then(response => {
          setChannelName(response.data.display_name || response.data.name)
        })
        .catch(() => {
          setChannelName('Channel')
        })
    }
  }, [channelId])

  return (
    <div className="flex h-screen">
      <Sidebar />
      <div className="flex flex-col flex-1">
        <TopBar channelName={channelName} channelId={channelId ? parseInt(channelId) : undefined} />
        <main className="flex-1 overflow-hidden">
          <Outlet />
        </main>
      </div>
    </div>
  )
}
