import { useEffect, useState } from 'react'
import { Routes, Route, Navigate, useNavigate } from 'react-router-dom'
import { useAuthStore } from './stores/authStore'

import Login from './pages/Login'
import Register from './pages/Register'
import MainLayout from './layouts/MainLayout'
import SetupPage from './pages/SetupPage'

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
  const navigate = useNavigate()
  const [initialized, setInitialized] = useState<boolean | null>(null)

  // System initialization check (runs once per session on app load, does NOT rely on auth)
  useEffect(() => {
    const key = 'system_status_checked'
    const cached = sessionStorage.getItem(key)
    if (cached !== null) {
      setInitialized(cached === 'true')
      if (cached === 'false') navigate('/setup')
      return
    }

    let cancelled = false
    ;(async () => {
      try {
        const api = (await import('./services/api')).default
        const resp = await api.get('/api/system/status')
        const inited = !!resp.data?.initialized
        if (cancelled) return
        setInitialized(inited)
        sessionStorage.setItem(key, inited ? 'true' : 'false')
        if (!inited) navigate('/setup')
      } catch (e) {
        console.warn('[App] Failed to fetch system status, allowing normal flow', e)
        // Fail open: allow app to continue; set initialized to true to avoid blocking
        setInitialized(true)
        sessionStorage.setItem(key, 'true')
      }
    })()

    return () => {
      cancelled = true
    }
  }, [navigate])

  return (
    <Routes>
      <Route path="/login" element={initialized === false ? <Navigate to="/setup" replace /> : <Login />} />
      <Route path="/register" element={<Register />} />      <Route path="setup" element={<SetupPage/>} />      <Route
        path="/"
        element={
          initialized === false ? (
            <Navigate to="/setup" replace />
          ) : (
            <PrivateRoute>
              <MainLayout />
            </PrivateRoute>
          )
        }
      >
        <Route index element={<ChannelView />} />

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
