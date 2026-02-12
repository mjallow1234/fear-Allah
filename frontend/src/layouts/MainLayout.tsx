import { Outlet, useParams } from 'react-router-dom'
import { useState, useEffect, Suspense } from 'react'
import Sidebar from '../components/Sidebar'
import ErrorBoundary from '../components/ErrorBoundary'
import TopBar from '../components/TopBar'
import api from '../services/api'
import { requestNotificationPermission } from '../utils/notifications'
import { ChatSocketProvider } from '../contexts/ChatSocketContext'

export default function MainLayout() {
  const { channelId } = useParams<{ channelId: string }>()
  const [channelName, setChannelName] = useState('general')
  const [sidebarOpen, setSidebarOpen] = useState(false)

  // Request notification permission on mount
  useEffect(() => {
    requestNotificationPermission()
  }, [])

  // Lock body scroll when sidebar is open on mobile
  useEffect(() => {
    if (sidebarOpen) {
      document.body.classList.add('sidebar-open')
    } else {
      document.body.classList.remove('sidebar-open')
    }
    return () => {
      document.body.classList.remove('sidebar-open')
    }
  }, [sidebarOpen])

  useEffect(() => {
    if (channelId) {
      // Handle string channel slugs like 'general' in dev by mapping to numeric id 1
      const idToFetch = channelId === 'general' ? '1' : channelId
      const channelNum = parseInt(idToFetch, 10)
      if (Number.isNaN(channelNum)) {
        setChannelName('Channel')
        return
      }

      // Fetch channel info
      api.get(`/api/channels/${channelNum}`)
        .then(response => {
          setChannelName(response.data.display_name || response.data.name)
        })
        .catch(() => {
          setChannelName('Channel')
        })
    }
  }, [channelId])

  return (
    <div className="flex h-full">
      {/* Mobile Sidebar Backdrop */}
      <div 
        className={`sidebar-backdrop ${sidebarOpen ? 'visible' : ''} md:hidden`}
        onClick={() => setSidebarOpen(false)}
      />
      <ErrorBoundary>
        <Sidebar isOpen={sidebarOpen} onClose={() => setSidebarOpen(false)} />
      </ErrorBoundary>
      <div className="flex flex-col flex-1 h-full min-h-0">
        <TopBar 
          channelName={channelName} 
          channelId={channelId ? parseInt(channelId) : undefined}
          onMenuClick={() => setSidebarOpen(true)}
        />
        <main className="flex-1 min-h-0 overflow-hidden">
          {/* ChatSocketProvider mounted here once after login; it will manage the chat WebSocket lifecycle */}
          {/*
            ChatSocketProvider is intentionally NOT mounted by default in desktop-first App Shell.
            To enable real-time sockets for local testing, set `window.__ENABLE_WEBSOCKETS__ = true` before app bootstrap.
            This prevents automatic /ws/chat/* and /ws/presence connections after login.
          */}
          {typeof window !== 'undefined' && (window as any).__ENABLE_WEBSOCKETS__ ? (
            <ChatSocketProvider>
              <ErrorBoundary>
                <Suspense fallback={<Outlet />}>
                  <Outlet />
                </Suspense>
              </ErrorBoundary>
            </ChatSocketProvider>
          ) : (
            <ErrorBoundary>
              <Suspense fallback={<Outlet />}>
                <Outlet />
              </Suspense>
            </ErrorBoundary>
          )}
        </main>
      </div>
    </div>
  )
}
