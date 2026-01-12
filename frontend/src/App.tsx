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
  // Logic: setupCompleted is tri-state:
  //  - undefined => unresolved (show splash)
  //  - true/false => explicit value
  //  - null => unknown (treat as 'unknown' and avoid redirecting to /setup)
  const [setupCompleted, setSetupCompleted] = useState<boolean | null | undefined>(undefined)
  const isAuthenticated = useAuthStore((state) => state.isAuthenticated)

  useEffect(() => {
    let cancelled = false
    import('./services/system').then(({ fetchSystemStatus }) => {
      fetchSystemStatus()
        .then((data) => {
          if (cancelled) return
          // If server returned null (unknown), pass through as null
          const sc = data.setup_completed
          setSetupCompleted(sc === null ? null : Boolean(sc))
        })
        .catch((err) => {
          // On error treat as unknown (null) so unauthenticated users don't get redirected to /setup
          if (!cancelled) setSetupCompleted(null)
          console.warn('Failed to resolve system status, treating as unknown', err)
        })
    })

    return () => {
      cancelled = true
    }
  }, [])

  // While the system status is unresolved, render a blank screen / splash to avoid any routing
  if (setupCompleted === undefined) return null


  return (
    <Routes>
      <Route
        path="/login"
        element={
          isAuthenticated ? <Navigate to="/" replace /> : setupCompleted === false ? <Navigate to="/setup" replace /> : <Login />
        }
      />
      <Route
        path="/setup"
        element={
          isAuthenticated ? (
            <Navigate to="/" replace />
          ) : setupCompleted === false ? (
            <SetupPage />
          ) : (
            <Navigate to="/login" replace />
          )
        }
      />
      <Route path="/register" element={<Register />} />      <Route path="setup" element={<SetupPage/>} />      <Route
        path="/"
        element={
          !isAuthenticated ? (
            setupCompleted === false ? (
              <Navigate to="/setup" replace />
            ) : (
              <Navigate to="/login" replace />
            )
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
