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

  // Connect Socket.IO when authenticated
  useEffect(() => {
    let cancelled = false
    if (isAuthenticated && token) {
      console.log('[App] User authenticated, connecting Socket.IO...')
      connectSocket()
      subscribeToPresence()
      
      // Subscribe to read receipts
      const unsubscribeReceipts = subscribeToReadReceipts()

      // Check onboarding state: if no teams exist or user not a member of any team -> redirect to onboarding
      ;(async () => {
        try {
          const teamsResp = await (await import('./services/api')).default.get('/api/teams/')
          const teams = Array.isArray(teamsResp.data) ? teamsResp.data : []
              if (teams.length === 0) {
            // No teams at all -> onboarding
            if (!cancelled) {
              // Only redirect once per session to avoid refresh loops caused by retries
              try {
                const key = 'onboarding_redirected'
                if (!sessionStorage.getItem(key)) {
                  sessionStorage.setItem(key, '1')
                  window.location.href = '/onboarding'
                }
              } catch (e) {
                // sessionStorage can throw in some restricted environments - fail safe to redirect
                window.location.href = '/onboarding'
              }
            }
            return
          }

          // Check current user's teams
          const userTeamsResp = await (await import('./services/api')).default.get('/api/users/me/teams')
          const myTeams = Array.isArray(userTeamsResp.data) ? userTeamsResp.data : []
          if (myTeams.length === 0) {
            // User has no team membership -> onboarding (create or join flow)
            if (!cancelled) {
              try {
                const key = 'onboarding_redirected'
                if (!sessionStorage.getItem(key)) {
                  sessionStorage.setItem(key, '1')
                  window.location.href = '/onboarding'
                }
              } catch (e) {
                window.location.href = '/onboarding'
              }
            }
            return
          }
        } catch (err) {
          // Ignore: leave as-is and let normal flow continue
          console.error('Failed to check onboarding state', err)
        }
      })()
      
      return () => {
        unsubscribeReceipts()
        cancelled = true
      }
    }
  }, [isAuthenticated, token])

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
