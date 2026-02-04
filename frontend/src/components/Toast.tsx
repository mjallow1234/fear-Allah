import { useState, useEffect, useCallback } from 'react'
import { X, Bell, CheckCircle, AlertTriangle, ShoppingCart } from 'lucide-react'
import clsx from 'clsx'

export interface ToastNotification {
  id: string
  type: string
  title: string
  body?: string
  orderId?: number | null
  onClick?: () => void
}

interface ToastProps {
  notification: ToastNotification
  onDismiss: (id: string) => void
  duration?: number
}

function Toast({ notification, onDismiss, duration = 5000 }: ToastProps) {
  useEffect(() => {
    const timer = setTimeout(() => {
      onDismiss(notification.id)
    }, duration)

    return () => clearTimeout(timer)
  }, [notification.id, onDismiss, duration])

  const getIcon = () => {
    switch (notification.type) {
      case 'task_step_completed':
      case 'task_completed':
        return <CheckCircle className="w-5 h-5 text-green-400" />
      case 'task_assigned':
      case 'task_overdue':
        return <AlertTriangle className="w-5 h-5 text-yellow-400" />
      case 'order_created':
      case 'order_completed':
        return <ShoppingCart className="w-5 h-5 text-blue-400" />
      case 'low_stock':
        return <AlertTriangle className="w-5 h-5 text-red-400" />
      default:
        return <Bell className="w-5 h-5 text-gray-400" />
    }
  }

  const handleClick = () => {
    if (notification.onClick) {
      notification.onClick()
    }
    onDismiss(notification.id)
  }

  return (
    <div
      onClick={handleClick}
      className={clsx(
        'flex items-start gap-3 p-4 rounded-lg shadow-lg border cursor-pointer',
        'bg-gray-800 border-gray-700 text-white',
        'animate-slide-in-right hover:bg-gray-750',
        'min-w-[300px] max-w-[400px]'
      )}
    >
      <div className="flex-shrink-0 mt-0.5">
        {getIcon()}
      </div>
      <div className="flex-1 min-w-0">
        <p className="font-medium text-sm">{notification.title}</p>
        {notification.body && (
          <p className="text-sm text-gray-400 mt-1 line-clamp-2">{notification.body}</p>
        )}
      </div>
      <button
        onClick={(e) => {
          e.stopPropagation()
          onDismiss(notification.id)
        }}
        className="flex-shrink-0 text-gray-500 hover:text-gray-300 transition-colors"
      >
        <X className="w-4 h-4" />
      </button>
    </div>
  )
}

// Toast container component
interface ToastContainerProps {
  toasts: ToastNotification[]
  onDismiss: (id: string) => void
}

export function ToastContainer({ toasts, onDismiss }: ToastContainerProps) {
  if (toasts.length === 0) return null

  return (
    <div className="fixed top-4 right-4 z-50 flex flex-col gap-2">
      {toasts.map((toast) => (
        <Toast key={toast.id} notification={toast} onDismiss={onDismiss} />
      ))}
    </div>
  )
}

// Hook to manage toasts
export function useToasts() {
  const [toasts, setToasts] = useState<ToastNotification[]>([])

  const addToast = useCallback((toast: Omit<ToastNotification, 'id'>) => {
    const id = `toast-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`
    setToasts((prev) => [...prev, { ...toast, id }].slice(-5)) // Max 5 toasts
  }, [])

  const dismissToast = useCallback((id: string) => {
    setToasts((prev) => prev.filter((t) => t.id !== id))
  }, [])

  const dismissAll = useCallback(() => {
    setToasts([])
  }, [])

  return { toasts, addToast, dismissToast, dismissAll }
}

export default Toast
