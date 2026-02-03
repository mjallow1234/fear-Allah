import { useState, useEffect, useCallback } from 'react'
import { Bell, Check, CheckCheck, Trash2, Package, ShoppingCart, ClipboardList, AlertTriangle, RefreshCw } from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import api from '../services/api'
import clsx from 'clsx'
import { onSocketEvent } from '../realtime'

interface Notification {
  id: number
  type: string
  title: string
  content: string | null
  channel_id: number | null
  message_id: number | null
  task_id: number | null
  order_id: number | null
  sender_id: number | null
  sender_username: string | null
  is_read: boolean
  created_at: string
}

// Custom event for real-time notifications (keep for backward compatibility)
const NOTIFICATION_EVENT = 'new-notification'

// Types that should show toast notifications (interrupting)
const TOAST_NOTIFICATION_TYPES = new Set([
  'task_assigned',
  'task_overdue',
  'low_stock',
  'system',
])

// Function to dispatch new notification event (called from WebSocket handlers)
export function pushNotification(notification: Notification) {
  window.dispatchEvent(new CustomEvent(NOTIFICATION_EVENT, { detail: notification }))
}

export default function NotificationBell() {
  const [showDropdown, setShowDropdown] = useState(false)
  const [notifications, setNotifications] = useState<Notification[]>([])
  const [unreadCount, setUnreadCount] = useState(0)
  const navigate = useNavigate()

  const fetchNotifications = useCallback(async () => {
    try {
      const [notifResponse, countResponse] = await Promise.all([
        api.get('/api/notifications/?limit=10'),
        api.get('/api/notifications/count')
      ])
      setNotifications(notifResponse.data)
      setUnreadCount(countResponse.data.unread)
    } catch (error) {
      console.error('Failed to fetch notifications:', error)
    }
  }, [])

  useEffect(() => {
    fetchNotifications()
    // Poll for new notifications every 30 seconds (fallback when socket disconnected)
    const interval = setInterval(fetchNotifications, 30000)
    return () => clearInterval(interval)
  }, [fetchNotifications])

  // Listen for real-time notifications via Socket.IO
  useEffect(() => {
    const unsubscribe = onSocketEvent<Notification>('notification:new', (notification) => {
      setNotifications(prev => [notification, ...prev.slice(0, 9)]) // Keep max 10
      setUnreadCount(prev => prev + 1)
      
      // Show toast for interrupting notification types only
      if (TOAST_NOTIFICATION_TYPES.has(notification.type)) {
        // Import dynamically to avoid circular dependency
        import('../utils/notifications').then(({ showBrowserNotification }) => {
          showBrowserNotification(notification.title, {
            body: notification.content || undefined,
            tag: `notif-${notification.id}`,
          })
        }).catch(() => {
          // Fallback: log to console if browser notifications unavailable
          console.log('[Notification Toast]', notification.title, notification.content)
        })
      }
    })
    
    return () => unsubscribe()
  }, [])

  // Listen for legacy custom event notifications (backward compatibility)
  useEffect(() => {
    const handleNewNotification = (event: CustomEvent<Notification>) => {
      const notification = event.detail
      setNotifications(prev => [notification, ...prev.slice(0, 9)]) // Keep max 10
      setUnreadCount(prev => prev + 1)
    }

    window.addEventListener(NOTIFICATION_EVENT, handleNewNotification as EventListener)
    return () => {
      window.removeEventListener(NOTIFICATION_EVENT, handleNewNotification as EventListener)
    }
  }, [])

  const handleMarkRead = async (id: number, e: React.MouseEvent) => {
    e.stopPropagation()
    try {
      await api.post(`/api/notifications/${id}/read`)
      setNotifications(prev =>
        prev.map(n => n.id === id ? { ...n, is_read: true } : n)
      )
      setUnreadCount(prev => Math.max(0, prev - 1))
    } catch (error) {
      console.error('Failed to mark notification as read:', error)
    }
  }

  const handleMarkAllRead = async () => {
    try {
      await api.post('/api/notifications/read-all')
      setNotifications(prev => prev.map(n => ({ ...n, is_read: true })))
      setUnreadCount(0)
    } catch (error) {
      console.error('Failed to mark all as read:', error)
    }
  }

  const handleDelete = async (id: number, e: React.MouseEvent) => {
    e.stopPropagation()
    try {
      await api.delete(`/api/notifications/${id}`)
      const notif = notifications.find(n => n.id === id)
      setNotifications(prev => prev.filter(n => n.id !== id))
      if (notif && !notif.is_read) {
        setUnreadCount(prev => Math.max(0, prev - 1))
      }
    } catch (error) {
      console.error('Failed to delete notification:', error)
    }
  }

  const handleNotificationClick = (notif: Notification) => {
    // Mark as read first
    if (!notif.is_read) {
      handleMarkRead(notif.id, { stopPropagation: () => {} } as React.MouseEvent)
    }
    setShowDropdown(false)
    
    // PRIORITY 1: Order-related notifications → always go to snapshot (read-only, permission-safe)
    // This applies to: order_created, order_completed, task_assigned, task_completed, task_overdue
    // NOTE: /order-snapshot is intentionally OUTSIDE /orders so non-admin roles can access it
    if (notif.order_id) {
      navigate(`/order-snapshot/${notif.order_id}`)
      return
    }
    
    // PRIORITY 2: Standalone task notifications (no order) → task inbox
    if (notif.task_id) {
      navigate(`/tasks?task=${notif.task_id}`)
      return
    }
    
    // PRIORITY 3: Channel/message notifications
    if (notif.channel_id) {
      if (notif.message_id) {
        navigate(`/channels/${notif.channel_id}?message=${notif.message_id}`)
      } else {
        navigate(`/channels/${notif.channel_id}`)
      }
      return
    }
  }

  const getNotificationIcon = (type: string) => {
    switch (type) {
      // Chat notifications
      case 'mention':
        return '@'
      case 'reply':
        return '↩'
      case 'dm':
        return '💬'
      case 'reaction':
        return '👍'
      
      // Automation notifications
      case 'task_assigned':
        return <ClipboardList size={14} />
      case 'task_completed':
        return <Check size={14} className="text-green-400" />
      case 'task_auto_closed':
        return <ClipboardList size={14} className="text-orange-400" />
      case 'task_overdue':
        return <AlertTriangle size={14} className="text-red-400" />
      case 'order_created':
        return <ShoppingCart size={14} className="text-blue-400" />
      case 'order_completed':
        return <ShoppingCart size={14} className="text-green-400" />
      case 'low_stock':
        return <AlertTriangle size={14} className="text-yellow-400" />
      case 'inventory_restocked':
        return <RefreshCw size={14} className="text-green-400" />
      case 'sale_recorded':
        return <Package size={14} className="text-purple-400" />
      case 'system':
        return <Bell size={14} />
      
      default:
        return '📢'
    }
  }

  const formatTime = (dateStr: string) => {
    const date = new Date(dateStr)
    const now = new Date()
    const diff = now.getTime() - date.getTime()
    const minutes = Math.floor(diff / 60000)
    const hours = Math.floor(minutes / 60)
    const days = Math.floor(hours / 24)

    if (minutes < 1) return 'Just now'
    if (minutes < 60) return `${minutes}m ago`
    if (hours < 24) return `${hours}h ago`
    if (days < 7) return `${days}d ago`
    return date.toLocaleDateString()
  }

  return (
    <div className="relative">
      <button
        onClick={() => setShowDropdown(!showDropdown)}
        className="relative p-2 text-[#949ba4] hover:text-white transition-colors"
        title="Notifications"
      >
        <Bell size={20} />
        {unreadCount > 0 && (
          <span className="absolute -top-1 -right-1 w-5 h-5 bg-red-500 text-white text-xs font-bold rounded-full flex items-center justify-center">
            {unreadCount > 9 ? '9+' : unreadCount}
          </span>
        )}
      </button>

      {showDropdown && (
        <>
          <div
            className="fixed inset-0 z-40"
            onClick={() => setShowDropdown(false)}
          />
          <div className="absolute right-0 top-10 w-80 bg-[#2b2d31] border border-[#1f2023] rounded-lg shadow-xl z-50 overflow-hidden">
            <div className="flex items-center justify-between px-4 py-3 border-b border-[#1f2023]">
              <h3 className="font-semibold text-white">Notifications</h3>
              {unreadCount > 0 && (
                <button
                  onClick={handleMarkAllRead}
                  className="text-xs text-[#00a8fc] hover:underline flex items-center gap-1"
                >
                  <CheckCheck size={14} />
                  Mark all read
                </button>
              )}
            </div>

            <div className="max-h-96 overflow-y-auto">
              {notifications.length === 0 ? (
                <div className="px-4 py-8 text-center text-[#949ba4]">
                  <Bell size={32} className="mx-auto mb-2 opacity-50" />
                  <p>No notifications</p>
                </div>
              ) : (
                notifications.map(notif => (
                  <div
                    key={notif.id}
                    onClick={() => handleNotificationClick(notif)}
                    className={clsx(
                      'px-4 py-3 border-b border-[#1f2023] cursor-pointer hover:bg-[#35373c] transition-colors',
                      !notif.is_read && 'bg-[#35373c]/50'
                    )}
                  >
                    <div className="flex items-start gap-3">
                      <div className="w-8 h-8 rounded-full bg-[#5865f2] flex items-center justify-center text-white text-sm">
                        {getNotificationIcon(notif.type)}
                      </div>
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2">
                          <span className={clsx(
                            'text-sm truncate',
                            notif.is_read ? 'text-[#949ba4]' : 'text-white font-medium'
                          )}>
                            {notif.title}
                          </span>
                          {!notif.is_read && (
                            <span className="w-2 h-2 rounded-full bg-[#00a8fc] flex-shrink-0" />
                          )}
                        </div>
                        {notif.content && (
                          <p className="text-xs text-[#949ba4] truncate mt-0.5">
                            {notif.content}
                          </p>
                        )}
                        <span className="text-xs text-[#72767d] mt-1 block">
                          {formatTime(notif.created_at)}
                        </span>
                      </div>
                      <div className="flex gap-1">
                        {!notif.is_read && (
                          <button
                            onClick={(e) => handleMarkRead(notif.id, e)}
                            className="p-1 text-[#949ba4] hover:text-[#00a8fc] transition-colors"
                            title="Mark as read"
                          >
                            <Check size={14} />
                          </button>
                        )}
                        <button
                          onClick={(e) => handleDelete(notif.id, e)}
                          className="p-1 text-[#949ba4] hover:text-red-500 transition-colors"
                          title="Delete"
                        >
                          <Trash2 size={14} />
                        </button>
                      </div>
                    </div>
                  </div>
                ))
              )}
            </div>

            {notifications.length > 0 && (
              <div className="px-4 py-2 border-t border-[#1f2023] text-center">
                <button
                  onClick={() => {
                    navigate('/notifications')
                    setShowDropdown(false)
                  }}
                  className="text-sm text-[#00a8fc] hover:underline"
                >
                  View all notifications
                </button>
              </div>
            )}
          </div>
        </>
      )}
    </div>
  )
}
