import { Outlet, useParams, NavLink } from 'react-router-dom'
import { useState, useEffect, Suspense } from 'react'
import Sidebar from '../components/Sidebar'
import ErrorBoundary from '../components/ErrorBoundary'
import TopBar from '../components/TopBar'
import api from '../services/api'
import { requestNotificationPermission } from '../utils/notifications'
import { ChatSocketProvider } from '../contexts/ChatSocketContext'
import { useAuthStore } from '../stores/authStore'
import useOperationalPermissions from '../permissions/useOperationalPermissions'

export default function MainLayout() {
  const { channelId } = useParams<{ channelId: string }>()
  const [channelName, setChannelName] = useState('general')

  // Resolve authoritative user for permissions: prefer hydrated currentUser, fall back to session user
  const authUser = useAuthStore((s) => s.user)
  const currentUser = useAuthStore((s) => s.currentUser)
  const userForPerms = currentUser ?? authUser ?? undefined
  const perms = useOperationalPermissions(userForPerms)

  // Request notification permission on mount
  useEffect(() => {
    requestNotificationPermission()
  }, [])

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
    <div className="flex h-screen">
      <ErrorBoundary>
        <Sidebar />
      </ErrorBoundary>
      <div className="flex flex-col flex-1">
        <TopBar channelName={channelName} channelId={channelId ? parseInt(channelId) : undefined} />
        <main className="flex-1 overflow-hidden">
          {/* ChatSocketProvider mounted here once after login; it will manage the chat WebSocket lifecycle */}
          {/*
            ChatSocketProvider is intentionally NOT mounted by default in desktop-first App Shell.
            To enable real-time sockets for local testing, set `window.__ENABLE_WEBSOCKETS__ = true` before app bootstrap.
            This prevents automatic /ws/chat/* and /ws/presence connections after login.
          */}
          {/* Operational tabs (Orders / Sales / Tasks) — rendered globally above routed content when user has any operational tabs */}
          {perms.tabs && perms.tabs.length > 0 && (
            <div className="h-12 bg-[#232428] border-b border-[#1f2023] flex items-center px-4 gap-3">
              {perms.tabs.includes('Orders') && (
                <NavLink to="/orders" className={({ isActive }) => isActive ? 'text-white px-3 py-1 bg-[#35373c] rounded' : 'text-[#949ba4] px-3 py-1 hover:text-white'}>Orders</NavLink>
              )}
              {perms.tabs.includes('Sales') && (
                <NavLink to="/sales" className={({ isActive }) => isActive ? 'text-white px-3 py-1 bg-[#35373c] rounded' : 'text-[#949ba4] px-3 py-1 hover:text-white'}>Sales</NavLink>
              )}
              {perms.tabs.includes('Tasks') && (
                <NavLink to="/tasks" className={({ isActive }) => isActive ? 'text-white px-3 py-1 bg-[#35373c] rounded' : 'text-[#949ba4] px-3 py-1 hover:text-white'}>Tasks</NavLink>
              )}
            </div>
          )}

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
