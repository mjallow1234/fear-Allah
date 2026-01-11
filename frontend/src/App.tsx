import { useEffect, useRef } from 'react'
import { Routes, Route, Navigate, useNavigate } from 'react-router-dom'
import { useAuthStore } from './stores/authStore'
import { connectSocket, subscribeToPresence } from './realtime'
import { subscribeToReadReceipts } from './realtime/readReceipts'
import Login from './pages/Login'
import Register from './pages/Register'
import MainLayout from './layouts/MainLayout'
import OnboardingPage from './pages/Onboarding'
import ChannelView from './pages/ChannelView'
import Settings from './pages/Settings'
import Profile from './pages/Profile'
import NotificationsPage from './pages/NotificationsPage'
import TaskInboxPage from './pages/TaskInboxPage'
import OrdersPage from './pages/OrdersPage'
import OrderDetailsPage from './pages/OrderDetailsPage'
import SalesPage from './pages/SalesPage'
import AdminAuditPage from './pages/AdminAuditPage'
import SystemConsolePage from './pages/SystemConsolePage'
import AdminFormBuilderPage from './pages/AdminFormBuilderPage'
import AIInsightsPage from './pages/AIInsightsPage'

function PrivateRoute({ children }: { children: React.ReactNode }) {
  const isAuthenticated = useAuthStore((state) => state.isAuthenticated)
  return isAuthenticated ? <>{children}</> : <Navigate to="/login" />
}

function App() {
  const hasBootstrappedRef = useRef(false)
  const navigate = useNavigate()

  // One-time bootstrap: subscribe to auth store and run bootstrap exactly once per session
  useEffect(() => {
    let unsubscribeReceipts: (() => void) | null = null
    let cancelled = false

    const runBootstrap = async () => {
      if (cancelled) return
      try {
        console.log('[App] Bootstrapping app...')
        // Connect and subscribe once
        connectSocket()
        subscribeToPresence()
        unsubscribeReceipts = subscribeToReadReceipts()

        // One-time check for onboarding state: call /api/users/me and use user.team_id
        const api = (await import('./services/api')).default
        try {
          const userResp = await api.get('/api/users/me')
          const user = userResp.data
          const key = 'onboarding_redirected'
          if (user && user.team_id === null) {
            // Ensure we redirect only once per session
            if (!sessionStorage.getItem(key)) {
              sessionStorage.setItem(key, '1')
              // Client-side navigation to avoid full page reloads
              navigate('/onboarding')
            }
          }
        } catch (e) {
          // Do not redirect based on errors — only act on a successful response
          console.warn('[App] Skipping onboarding redirect due to error fetching /api/users/me', e)
        }
      } catch (err) {
        console.error('Failed to bootstrap app', err)
      }
    }

    // Subscribe to auth store changes to trigger bootstrap when user logs in
    const unsub = useAuthStore.subscribe((state) => {
      if (state.isAuthenticated && state.token && !hasBootstrappedRef.current) {
        hasBootstrappedRef.current = true
        runBootstrap()
      }
    })

    // If already authenticated when component mounts, run bootstrap immediately
    const state = useAuthStore.getState()
    if (state.isAuthenticated && state.token && !hasBootstrappedRef.current) {
      hasBootstrappedRef.current = true
      runBootstrap()
    }

    return () => {
      cancelled = true
      if (unsubscribeReceipts) unsubscribeReceipts()
      unsub()
    }
  }, [])

  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route path="/register" element={<Register />} />
      <Route
        path="/"
        element={
          <PrivateRoute>
            <MainLayout />
          </PrivateRoute>
        }
      >
        <Route index element={<ChannelView />} />
        <Route path="onboarding" element={<OnboardingPage/>} />
        <Route path="channels/:channelId" element={<ChannelView />} />
        <Route path="settings" element={<Settings />} />
        <Route path="profile" element={<Profile />} />
        <Route path="notifications" element={<NotificationsPage />} />
        <Route path="tasks" element={<TaskInboxPage />} />
        <Route path="orders" element={<OrdersPage />} />
        <Route path="orders/:id" element={<OrderDetailsPage />} />
        <Route path="sales" element={<SalesPage />} />
        <Route path="system/audit" element={<AdminAuditPage />} />
        <Route path="system/*" element={<SystemConsolePage />} />
        {/* Admin Form Builder routes */}
        <Route path="admin/forms" element={<AdminFormBuilderPage />} />
        <Route path="admin/forms/:formId" element={<AdminFormBuilderPage />} />
        {/* AI Insights (Admin only) */}
        <Route path="admin/ai" element={<AIInsightsPage />} />
        {/* Legacy route redirect */}
        <Route path="admin/audit" element={<Navigate to="/system/audit" replace />} />
      </Route>
      <Route path="*" element={<h1 style={{ padding: 40 }}>404 — Page not found</h1>} />
    </Routes>
  )
}

export default App
