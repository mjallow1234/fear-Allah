import { createContext, useContext, useCallback, useEffect, ReactNode } from 'react'
import { useNavigate } from 'react-router-dom'
import { ToastContainer, useToasts, ToastNotification } from '../components/Toast'
import { shouldPlaySound, shouldShowToast, isBusinessNotificationType } from '../utils/notificationConfig'
import { playNotificationSound } from '../hooks/useNotificationSound'
import { onSocketEvent } from '../realtime'
import { useAuthStore } from '../stores/authStore'
import { usePreferencesStore } from '../stores/preferencesStore'

interface Notification {
  id: number
  type: string
  title: string
  content: string | null
  channel_id: number | null
  message_id: number | null
  task_id: number | null
  order_id: number | null
  extra_data?: string | null
  sender_id: number | null
  sender_username: string | null
  is_read: boolean
  created_at: string
}

interface NotificationContextType {
  showNotification: (notification: Notification) => void
}

const NotificationContext = createContext<NotificationContextType | null>(null)

export function useNotificationContext() {
  const context = useContext(NotificationContext)
  if (!context) {
    throw new Error('useNotificationContext must be used within NotificationProvider')
  }
  return context
}

interface NotificationProviderProps {
  children: ReactNode
}

export function NotificationProvider({ children }: NotificationProviderProps) {
  const { toasts, addToast, dismissToast } = useToasts()
  const navigate = useNavigate()
  const currentUserId = useAuthStore((state) => state.user?.id)
  // Respect user preference for notifications (Phase 2.7)
  const notificationsEnabled = usePreferencesStore((state) => state.preferences.notifications)

  const handleNotificationClick = useCallback((notification: Notification) => {
    // Parse extra_data if present
    let extra: any = null
    try {
      if (notification.extra_data) extra = JSON.parse(notification.extra_data as string)
    } catch (e) {
      // ignore
    }

    // Special-case chat notifications
    if (notification.type === 'channel_reply') {
      const channelId = notification.channel_id || (extra && extra.channel_id)
      const parentId = (extra && extra.parent_id) || null
      if (channelId && parentId) {
        navigate(`/channels/${channelId}?message=${parentId}`)
        return
      }
    }

    if (notification.type === 'dm_reply') {
      const convId = (extra && extra.direct_conversation_id) || null
      const parentId = (extra && extra.parent_id) || null
      if (convId && parentId) {
        navigate(`/direct/${convId}?message=${parentId}`)
        return
      }
    }

    if (notification.type === 'dm_message') {
      const convId = (extra && extra.direct_conversation_id) || null
      if (convId) {
        navigate(`/direct/${convId}`)
        return
      }
    }

    // Fallbacks for legacy fields
    if (notification.order_id) {
      navigate(`/order-snapshot/${notification.order_id}`)
    } else if (notification.task_id) {
      navigate(`/tasks?task=${notification.task_id}`)
    } else if (notification.channel_id) {
      if (notification.message_id) {
        navigate(`/channels/${notification.channel_id}?message=${notification.message_id}`)
      } else {
        navigate(`/channels/${notification.channel_id}`)
      }
    }
  }, [navigate])

  const showNotification = useCallback((notification: Notification) => {
    // Don't notify for own actions
    if (notification.sender_id && notification.sender_id === currentUserId) {
      return
    }

    const notificationType = notification.type

    // Play sound for critical notifications
    if (shouldPlaySound(notificationType)) {
      playNotificationSound()
    }

    // Respect local view context: suppress toasts when user is already viewing the relevant DM/channel/thread
    try {
      const path = window.location.pathname || ''
      const search = window.location.search || ''
      const params = new URLSearchParams(search)
      const openThreadId = params.get('message') ? Number(params.get('message')) : null

      // Parse extra_data for server-created notifications (if present)
      let extra: any = null
      try {
        if (notification.extra_data) extra = JSON.parse(notification.extra_data as string)
      } catch (e) {
        // ignore parse errors
      }

      // Suppress when user is viewing same channel
      if (notification.channel_id && path.startsWith(`/channels/${notification.channel_id}`)) {
        return
      }

      // Suppress when user is viewing same direct conversation
      if (extra && extra.direct_conversation_id && path.startsWith(`/direct/${extra.direct_conversation_id}`)) {
        return
      }

      // Suppress reply notifications when viewing the thread for the same parent
      const parentIdFromExtra = extra && extra.parent_id ? Number(extra.parent_id) : null
      if (parentIdFromExtra && openThreadId && parentIdFromExtra === openThreadId) {
        return
      }
    } catch (e) {
      // Ignore any errors during suppression checks and continue to show/handle notification
    }

    // Show toast for critical and important notifications.
    // For business-critical notifications, bypass the user preference gating temporarily (emergency mode).
    if (shouldShowToast(notificationType) && (notificationsEnabled || isBusinessNotificationType(notificationType))) {
      const toast: Omit<ToastNotification, 'id'> = {
        type: notificationType,
        title: notification.title,
        body: notification.content || undefined,
        orderId: notification.order_id,
        onClick: () => handleNotificationClick(notification),
      }
      addToast(toast)
    } else if (shouldShowToast(notificationType) && !notificationsEnabled) {
      // Log that a business notification would have been suppressed but we're in emergency bypass mode
      if (isBusinessNotificationType(notificationType)) {
        console.info('[Notifications] Business notification bypassing user setting (emergency):', notificationType)
      }
    }
  }, [currentUserId, addToast, handleNotificationClick, notificationsEnabled])

  // Listen for real-time notifications
  useEffect(() => {
    const unsubscribe = onSocketEvent<Notification>('notification:new', (notification) => {
      showNotification(notification)
    })
    
    return () => unsubscribe()
  }, [showNotification])

  // Subscribe to chat messages globally and emit toasts for them when appropriate
  useEffect(() => {
    const unsubscribe = onSocketEvent<any>('message:new', (message) => {
      try {
        console.log('[Notifications] Received message:new', message)
        const currentUserId = useAuthStore.getState().user?.id

        // Ignore messages sent by self
        if (message.author_id && currentUserId && message.author_id === currentUserId) return

        // Ignore if user is actively viewing this channel or DM or its thread
        const path = window.location.pathname || ''
        const search = window.location.search || ''
        const params = new URLSearchParams(search)
        const openThreadId = params.get('message') ? Number(params.get('message')) : null

        // Suppress if viewing the same channel
        if (message.channel_id && path.startsWith(`/channels/${message.channel_id}`)) return

        // Suppress if viewing the same direct conversation
        if (message.direct_conversation_id && path.startsWith(`/direct/${message.direct_conversation_id}`)) return

        // When viewing a thread (via ?message=parent_id), suppress reply notifications for that parent
        if (message.parent_id && openThreadId && openThreadId === Number(message.parent_id)) return

        // Build a friendly title (use channel name if provided, otherwise author)
        const title = message.channel_name ? `#${message.channel_name}` : (message.author_username || 'Message')

        // Delegate to showNotification which will respect user preferences
        const notificationPayload: Notification = {
          id: message.id || -Date.now(),
          type: 'message',
          title,
          content: message.content ?? null,
          channel_id: message.channel_id,
          message_id: null,
          task_id: null,
          order_id: null,
          sender_id: message.author_id ?? null,
          sender_username: message.author_username ?? null,
          is_read: false,
          created_at: message.created_at ?? new Date().toISOString(),
        }

        showNotification(notificationPayload)
      } catch (err) {
        console.error('[Notifications] Failed to handle message:new', err)
      }
    })

    return () => unsubscribe()
  }, [showNotification])

  return (
    <NotificationContext.Provider value={{ showNotification }}>
      {children}
      <ToastContainer toasts={toasts} onDismiss={dismissToast} />
    </NotificationContext.Provider>
  )
}


export default NotificationProvider
