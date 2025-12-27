import { useEffect } from 'react'
import { Routes, Route, Navigate } from 'react-router-dom'
import { useAuthStore } from './stores/authStore'
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

function PrivateRoute({ children }: { children: React.ReactNode }) {
  const isAuthenticated = useAuthStore((state) => state.isAuthenticated)
  return isAuthenticated ? <>{children}</> : <Navigate to="/login" />
}

function App() {
  const isAuthenticated = useAuthStore((state) => state.isAuthenticated)
  const token = useAuthStore((state) => state.token)

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
        <Route path="tasks" element={<TaskInboxPage />} />
        <Route path="orders" element={<OrdersPage />} />
        <Route path="orders/:id" element={<OrderDetailsPage />} />
      </Route>
      <Route path="*" element={<h1 style={{ padding: 40 }}>404 — Page not found</h1>} />
    </Routes>
  )
}

export default App
