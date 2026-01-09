import { useEffect } from 'react'
import { Routes, Route, Navigate } from 'react-router-dom'
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
  const isAuthenticated = useAuthStore((state) => state.isAuthenticated)
  const token = useAuthStore((state) => state.token)
  const hasBootstrappedRef = useRef(false)

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

        // One-time checks for onboarding state
        const api = (await import('./services/api')).default
        const teamsResp = await api.get('/api/teams')
        const teams = Array.isArray(teamsResp.data) ? teamsResp.data : []
        if (teams.length === 0) {
          try {
            const key = 'onboarding_redirected'
            if (!sessionStorage.getItem(key)) {
              sessionStorage.setItem(key, '1')
              window.location.href = '/onboarding'
            }
          } catch (e) {
            window.location.href = '/onboarding'
          }
          return
        }

        const userTeamsResp = await api.get('/api/users/me/teams')
        const myTeams = Array.isArray(userTeamsResp.data) ? userTeamsResp.data : []
        if (myTeams.length === 0) {
          try {
            const key = 'onboarding_redirected'
            if (!sessionStorage.getItem(key)) {
              sessionStorage.setItem(key, '1')
              window.location.href = '/onboarding'
            }
          } catch (e) {
            window.location.href = '/onboarding'
          }
          return
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
