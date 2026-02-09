import { useEffect } from 'react'
import { Routes, Route, Navigate } from 'react-router-dom'
import { useAuthStore } from './stores/authStore'
import { usePreferencesStore } from './stores/preferencesStore'
import { connectSocket, subscribeToPresence } from './realtime'
import { subscribeToReadReceipts } from './realtime/readReceipts'
import Login from './pages/Login'
import Register from './pages/Register'
import MainLayout from './layouts/MainLayout'
import ChannelView from './pages/ChannelView'
import Settings from './pages/Settings'
import Profile from './pages/Profile'
import NotificationsPage from './pages/NotificationsPage'
import TaskInboxPage from './pages/TaskInboxPage'
import OrdersPage from './pages/OrdersPage'
import OrderDetailsPage from './pages/OrderDetailsPage'
import OrderSnapshotPage from './pages/OrderSnapshotPage'
import SalesPage from './pages/SalesPage'
import AdminAuditPage from './pages/AdminAuditPage'
import SystemConsolePage from './pages/SystemConsolePage'
import AdminFormBuilderPage from './pages/AdminFormBuilderPage'
import AIInsightsPage from './pages/AIInsightsPage'
import OperationalGuard from './components/OperationalGuard'
import AdminOnlyGuard from './components/AdminOnlyGuard'
import Unauthorized from './pages/Unauthorized'
import ChangePassword from './pages/ChangePassword'
import Welcome from './pages/Welcome'

function PrivateRoute({ children }: { children: React.ReactNode }) {
  const isAuthenticated = useAuthStore((state) => state.isAuthenticated)
  const user = useAuthStore((state) => state.user)
  
  if (!isAuthenticated) {
    return <Navigate to="/login" />
  }
  
  // Force password change if required (but not on change-password route itself)
  if (user?.must_change_password && window.location.pathname !== '/change-password') {
    return <Navigate to="/change-password" replace />
  }
  
  // Redirect first-time users to welcome page (but not if already dismissed or on special routes)
  const welcomeDismissed = localStorage.getItem('welcome_dismissed') === 'true'
  if (user?.is_first_login && !welcomeDismissed && window.location.pathname !== '/welcome' && window.location.pathname !== '/change-password') {
    return <Navigate to="/welcome" replace />
  }
  
  return <>{children}</>
}

function App() {
  const isAuthenticated = useAuthStore((state) => state.isAuthenticated)
  const token = useAuthStore((state) => state.token)
  const darkMode = usePreferencesStore((state) => state.preferences.dark_mode)

  // Apply dark_mode preference to document root
  useEffect(() => {
    if (darkMode) {
      document.documentElement.classList.remove('light')
      document.documentElement.classList.add('dark')
    } else {
      document.documentElement.classList.remove('dark')
      document.documentElement.classList.add('light')
    }
  }, [darkMode])

  const compactMode = usePreferencesStore((state) => state.preferences.compact_mode)

  // Apply compact_mode preference to document root (Phase 2.6)
  useEffect(() => {
    if (compactMode) {
      document.documentElement.classList.add('compact')
    } else {
      document.documentElement.classList.remove('compact')
    }
  }, [compactMode])

  // Connect Socket.IO when authenticated
  useEffect(() => {
    if (isAuthenticated && token) {
      console.log('[App] User authenticated, connecting Socket.IO...')
      connectSocket()
      subscribeToPresence()
      
      // Subscribe to read receipts
      const unsubscribeReceipts = subscribeToReadReceipts()
      
      return () => {
        unsubscribeReceipts()
      }
    }
  }, [isAuthenticated, token])

  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route path="/register" element={<Register />} />
      {/* Welcome route - for first-time users */}
      <Route 
        path="/welcome" 
        element={
          useAuthStore.getState().isAuthenticated 
            ? <Welcome /> 
            : <Navigate to="/login" />
        } 
      />
      {/* Change password route - accessible when authenticated but not wrapped in PrivateRoute guard */}
      <Route 
        path="/change-password" 
        element={
          useAuthStore.getState().isAuthenticated 
            ? <ChangePassword /> 
            : <Navigate to="/login" />
        } 
      />
      <Route
        path="/"
        element={
          <PrivateRoute>
            <MainLayout />
          </PrivateRoute>
        }
      >
        <Route index element={<ChannelView />} />
        <Route path="channels/:channelId" element={<ChannelView />} />
        <Route path="settings" element={<Settings />} />
        <Route path="profile" element={<Profile />} />
        <Route path="notifications" element={<NotificationsPage />} />

        {/* Protected sections: use OperationalGuard to enforce tab-level access */}
        <Route path="tasks/*" element={<OperationalGuard tab="Tasks" />}>
          <Route index element={<TaskInboxPage />} />
        </Route>

        <Route path="orders/*" element={<OperationalGuard tab="Orders" />}>
          <Route index element={<OrdersPage />} />
          <Route path=":id" element={<OrderDetailsPage />} />
        </Route>

        {/* NOTE: OrderSnapshot is intentionally OUTSIDE /orders
            so non-admin operational roles (Foreman, Delivery, Storekeeper)
            can access it via notifications without needing Orders tab permission */}
        <Route path="order-snapshot/:orderId" element={<OrderSnapshotPage />} />

        <Route path="sales/*" element={<OperationalGuard tab="Sales" />}>
          <Route index element={<SalesPage />} />
        </Route>

        <Route path="system/audit" element={<AdminOnlyGuard><AdminAuditPage /></AdminOnlyGuard>} />
        <Route path="system/*" element={<SystemConsolePage />} />

        <Route path="unauthorized" element={<Unauthorized />} />
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
