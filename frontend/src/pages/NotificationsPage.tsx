/**
 * Notifications Page - Full page view of all notifications.
 * Phase 7.1 - Notifications UI
 */
import { useState, useEffect, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { Bell, Check, CheckCheck, Trash2, ArrowLeft, Package, ShoppingCart, ClipboardList, AlertTriangle, RefreshCw } from 'lucide-react'
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
  sender_id: number | null
  sender_username: string | null
  task_id: number | null
  order_id: number | null
  inventory_id: number | null
  sale_id: number | null
  extra_data: Record<string, unknown> | null
  is_read: boolean
  created_at: string
}

export default function NotificationsPage() {
  const [notifications, setNotifications] = useState<Notification[]>([])
  const [unreadCount, setUnreadCount] = useState(0)
  const [loading, setLoading] = useState(true)
  const [filter, setFilter] = useState<'all' | 'unread' | 'automation'>('all')
  const navigate = useNavigate()

  const fetchNotifications = useCallback(async () => {
    try {
      setLoading(true)
      const [notifResponse, countResponse] = await Promise.all([
        api.get('/api/notifications/?limit=50'),
        api.get('/api/notifications/count')
      ])
      setNotifications(notifResponse.data)
      setUnreadCount(countResponse.data.unread)
    } catch (error) {
      console.error('Failed to fetch notifications:', error)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchNotifications()
  }, [fetchNotifications])

  // Listen for real-time notifications via Socket.IO
  useEffect(() => {
    const unsubscribe = onSocketEvent<Notification>('notification:new', (notification) => {
      setNotifications(prev => [notification, ...prev])
      setUnreadCount(prev => prev + 1)
    })
    
    return () => unsubscribe()
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
    // Navigate based on notification type
    if (notif.channel_id) {
      navigate(`/channels/${notif.channel_id}`)
    } else if (notif.task_id) {
      // Navigate to tasks page when we have one
      console.log('Task notification clicked:', notif.task_id)
    } else if (notif.order_id) {
      // Navigate to orders page when we have one
      console.log('Order notification clicked:', notif.order_id)
    } else if (notif.inventory_id) {
      // Navigate to inventory page when we have one
      console.log('Inventory notification clicked:', notif.inventory_id)
    }
    
    // Mark as read if unread
    if (!notif.is_read) {
      handleMarkRead(notif.id, { stopPropagation: () => {} } as React.MouseEvent)
    }
  }

  const getNotificationIcon = (type: string) => {
    switch (type) {
      // Chat notifications
      case 'mention':
        return <span className="text-lg">@</span>
      case 'reply':
        return <span className="text-lg">↩</span>
      case 'dm':
        return <span className="text-lg">💬</span>
      case 'reaction':
        return <span className="text-lg">👍</span>
      
      // Automation notifications
      case 'task_assigned':
        return <ClipboardList size={18} />
      case 'task_completed':
        return <Check size={18} className="text-green-400" />
      case 'task_auto_closed':
        return <ClipboardList size={18} className="text-orange-400" />
      case 'order_created':
        return <ShoppingCart size={18} className="text-blue-400" />
      case 'order_completed':
        return <ShoppingCart size={18} className="text-green-400" />
      case 'low_stock':
        return <AlertTriangle size={18} className="text-yellow-400" />
      case 'inventory_restocked':
        return <RefreshCw size={18} className="text-green-400" />
      case 'sale_recorded':
        return <Package size={18} className="text-purple-400" />
      case 'system':
        return <Bell size={18} />
      
      default:
        return <span className="text-lg">📢</span>
    }
  }

  const getNotificationColor = (type: string): string => {
    switch (type) {
      case 'low_stock':
        return 'bg-yellow-600'
      case 'task_assigned':
      case 'order_created':
        return 'bg-blue-600'
      case 'task_completed':
      case 'order_completed':
      case 'inventory_restocked':
        return 'bg-green-600'
      case 'sale_recorded':
        return 'bg-purple-600'
      case 'task_auto_closed':
        return 'bg-orange-600'
      default:
        return 'bg-[#5865f2]'
    }
  }

  const isAutomationType = (type: string): boolean => {
    return ['task_assigned', 'task_completed', 'task_auto_closed', 
            'order_created', 'order_completed', 'low_stock', 
            'inventory_restocked', 'sale_recorded', 'system'].includes(type)
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

  // Filter notifications
  const filteredNotifications = notifications.filter(notif => {
    if (filter === 'unread') return !notif.is_read
    if (filter === 'automation') return isAutomationType(notif.type)
    return true
  })

  return (
    <div className="h-full bg-[#313338]">
      {/* Header */}
      <div className="bg-[#2b2d31] border-b border-[#1f2023] px-6 py-4">
        <div className="max-w-3xl mx-auto flex items-center justify-between">
          <div className="flex items-center gap-4">
            <button
              onClick={() => navigate(-1)}
              className="p-2 text-[#949ba4] hover:text-white transition-colors"
            >
              <ArrowLeft size={20} />
            </button>
            <div>
              <h1 className="text-xl font-semibold text-white flex items-center gap-2">
                <Bell size={24} />
                Notifications
              </h1>
              <p className="text-sm text-[#949ba4]">
                {unreadCount} unread notification{unreadCount !== 1 ? 's' : ''}
              </p>
            </div>
          </div>
          {unreadCount > 0 && (
            <button
              onClick={handleMarkAllRead}
              className="flex items-center gap-2 px-3 py-2 bg-[#5865f2] hover:bg-[#4752c4] text-white rounded transition-colors"
            >
              <CheckCheck size={16} />
              Mark all as read
            </button>
          )}
        </div>
      </div>

      {/* Filter Tabs */}
      <div className="bg-[#2b2d31] border-b border-[#1f2023] px-6">
        <div className="max-w-3xl mx-auto flex gap-1">
          {(['all', 'unread', 'automation'] as const).map(tab => (
            <button
              key={tab}
              onClick={() => setFilter(tab)}
              className={clsx(
                'px-4 py-3 text-sm font-medium transition-colors border-b-2',
                filter === tab
                  ? 'text-white border-[#5865f2]'
                  : 'text-[#949ba4] border-transparent hover:text-white'
              )}
            >
              {tab.charAt(0).toUpperCase() + tab.slice(1)}
              {tab === 'unread' && unreadCount > 0 && (
                <span className="ml-2 px-1.5 py-0.5 bg-red-500 text-white text-xs rounded-full">
                  {unreadCount}
                </span>
              )}
            </button>
          ))}
        </div>
      </div>

      {/* Notifications List */}
      <div className="max-w-3xl mx-auto py-4 px-6">
        {loading ? (
          <div className="py-12 text-center">
            <div className="animate-spin w-8 h-8 border-2 border-[#5865f2] border-t-transparent rounded-full mx-auto mb-4" />
            <p className="text-[#949ba4]">Loading notifications...</p>
          </div>
        ) : filteredNotifications.length === 0 ? (
          <div className="py-12 text-center">
            <Bell size={48} className="mx-auto mb-4 text-[#949ba4] opacity-50" />
            <p className="text-[#949ba4]">
              {filter === 'all' && 'No notifications yet'}
              {filter === 'unread' && 'All caught up!'}
              {filter === 'automation' && 'No automation notifications'}
            </p>
          </div>
        ) : (
          <div className="space-y-2">
            {filteredNotifications.map(notif => (
              <div
                key={notif.id}
                onClick={() => handleNotificationClick(notif)}
                className={clsx(
                  'p-4 rounded-lg cursor-pointer transition-colors',
                  notif.is_read
                    ? 'bg-[#2b2d31] hover:bg-[#35373c]'
                    : 'bg-[#35373c] hover:bg-[#3e4046]'
                )}
              >
                <div className="flex items-start gap-4">
                  <div className={clsx(
                    'w-10 h-10 rounded-full flex items-center justify-center text-white',
                    getNotificationColor(notif.type)
                  )}>
                    {getNotificationIcon(notif.type)}
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <span className={clsx(
                        'text-sm',
                        notif.is_read ? 'text-[#949ba4]' : 'text-white font-medium'
                      )}>
                        {notif.title}
                      </span>
                      {!notif.is_read && (
                        <span className="w-2 h-2 rounded-full bg-[#00a8fc] flex-shrink-0" />
                      )}
                      <span className="text-xs text-[#72767d] ml-auto">
                        {formatTime(notif.created_at)}
                      </span>
                    </div>
                    {notif.content && (
                      <p className="text-sm text-[#949ba4] mt-1">
                        {notif.content}
                      </p>
                    )}
                    {/* Show extra context for automation notifications */}
                    {notif.extra_data && Object.keys(notif.extra_data).length > 0 && (
                      <div className="mt-2 text-xs text-[#72767d]">
                        {notif.task_id && <span className="mr-3">Task #{notif.task_id}</span>}
                        {notif.order_id && <span className="mr-3">Order #{notif.order_id}</span>}
                        {notif.inventory_id && <span className="mr-3">Item #{notif.inventory_id}</span>}
                      </div>
                    )}
                  </div>
                  <div className="flex gap-1">
                    {!notif.is_read && (
                      <button
                        onClick={(e) => handleMarkRead(notif.id, e)}
                        className="p-2 text-[#949ba4] hover:text-[#00a8fc] hover:bg-[#2b2d31] rounded transition-colors"
                        title="Mark as read"
                      >
                        <Check size={16} />
                      </button>
                    )}
                    <button
                      onClick={(e) => handleDelete(notif.id, e)}
                      className="p-2 text-[#949ba4] hover:text-red-500 hover:bg-[#2b2d31] rounded transition-colors"
                      title="Delete"
                    >
                      <Trash2 size={16} />
                    </button>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
