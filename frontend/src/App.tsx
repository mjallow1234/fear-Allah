import { useEffect, useState } from 'react'
import { Routes, Route, Navigate } from 'react-router-dom'
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

  // System gate: ensure system status is resolved BEFORE any route/PrivateRoute runs.
  const [initialized, setInitialized] = useState<boolean | null>(null)

  useEffect(() => {
    let cancelled = false
    import('./services/system').then(({ fetchSystemStatus }) => {
      fetchSystemStatus()
        .then((data) => {
          if (!cancelled) setInitialized(Boolean(data.initialized))
        })
        .catch((err) => {
          // Fail open on transient fetch errors so app still functions.
          if (!cancelled) setInitialized(true)
          console.warn('Failed to resolve system status, allowing normal flow', err)
        })
    })

    return () => {
      cancelled = true
    }
  }, [])

  // While the system status is unresolved, render a blank screen / splash to avoid any routing
  if (initialized === null) return null


  return (
    <Routes>
      <Route path="/login" element={initialized === false ? <Navigate to="/setup" replace /> : <Login />} />
      <Route path="/setup" element={!initialized ? <SetupPage /> : <Navigate to="/login" replace />} />
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
