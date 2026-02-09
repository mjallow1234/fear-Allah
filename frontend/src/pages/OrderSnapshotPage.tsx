/**
 * Order Snapshot Page
 * Read-only view of an order for role-based visibility.
 * 
 * Accessed via: /orders/snapshot/:orderId
 * 
 * Features:
 * - Order summary (type, priority, customer info)
 * - Progress timeline (completed/pending/locked roles)
 * - Status hint (dynamic message)
 * - Navigation only (no mutations)
 * - Auto-refresh every 15s + on focus/notification
 */
import { useEffect, useState, useCallback } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { 
  ArrowLeft, 
  Package,
  ShoppingCart,
  Warehouse,
  Tag,
  Loader2,
  AlertCircle,
  CheckCircle,
  Clock,
  Lock,
  User,
  Phone,
  MapPin,
  Calendar,
  FileText,
  Bell,
  ClipboardList
} from 'lucide-react'
import clsx from 'clsx'
import api from '../services/api'
import { onSocketEvent } from '../realtime'

// Types
interface Assignment {
  user_id: number | null
  status: string
  assigned_at: string | null
  completed_at: string | null
}

interface SnapshotTask {
  id: number
  title: string
  required_role: string
  status: string
  assignments: Assignment[]
}

interface SnapshotOrder {
  id: number
  order_type: string
  status: string
  priority: string
  delivery_location: string | null
  customer_name: string | null
  customer_phone: string | null
  reference: string | null
  payment_method: string | null
  internal_comment: string | null
  meta: Record<string, unknown>
  created_at: string | null
  created_by_id: number | null
}

interface SnapshotProgress {
  completed_roles: string[]
  pending_roles: string[]
  locked_roles: string[]
}

interface OrderSnapshot {
  order: SnapshotOrder
  tasks: SnapshotTask[]
  progress: SnapshotProgress
}

// Order type display config
const orderTypeConfig: Record<string, { icon: typeof Package; color: string; label: string }> = {
  'agent_restock': { icon: Warehouse, color: 'bg-blue-600', label: 'Agent Restock' },
  'agent_retail': { icon: ShoppingCart, color: 'bg-green-600', label: 'Agent Retail' },
  'store_keeper_restock': { icon: Warehouse, color: 'bg-purple-600', label: 'Store Restock' },
  'customer_wholesale': { icon: Tag, color: 'bg-orange-600', label: 'Wholesale' },
}

// Priority colors
const priorityColors: Record<string, string> = {
  'low': 'text-gray-400 bg-gray-400/10',
  'normal': 'text-blue-400 bg-blue-400/10',
  'high': 'text-orange-400 bg-orange-400/10',
  'urgent': 'text-red-400 bg-red-400/10',
}

// Role display names
const roleDisplayNames: Record<string, string> = {
  'foreman': 'Foreman',
  'delivery': 'Delivery',
  'storekeeper': 'Storekeeper',
  'agent': 'Agent',
}

export default function OrderSnapshotPage() {
  const { orderId } = useParams<{ orderId: string }>()
  const navigate = useNavigate()
  const orderIdNum = parseInt(orderId || '0', 10)
  
  const [snapshot, setSnapshot] = useState<OrderSnapshot | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  // Fetch snapshot data
  const fetchSnapshot = useCallback(async () => {
    if (!orderIdNum || orderIdNum <= 0) {
      setError('Invalid order ID')
      setLoading(false)
      return
    }
    
    try {
      const response = await api.get(`/api/orders/${orderIdNum}/snapshot`)
      setSnapshot(response.data)
      setError(null)
    } catch (err: unknown) {
      const errorMsg = err instanceof Error ? err.message : 'Failed to load order snapshot'
      if ((err as { response?: { status?: number } })?.response?.status === 403) {
        setError('You do not have permission to view this order')
      } else if ((err as { response?: { status?: number } })?.response?.status === 404) {
        setError('Order not found')
      } else {
        setError(errorMsg)
      }
    } finally {
      setLoading(false)
    }
  }, [orderIdNum])

  // Initial fetch
  useEffect(() => {
    fetchSnapshot()
  }, [fetchSnapshot])

  // Auto-refresh every 15 seconds
  useEffect(() => {
    const interval = setInterval(fetchSnapshot, 15000)
    return () => clearInterval(interval)
  }, [fetchSnapshot])

  // Refetch on page focus
  useEffect(() => {
    const handleFocus = () => {
      fetchSnapshot()
    }
    window.addEventListener('focus', handleFocus)
    return () => window.removeEventListener('focus', handleFocus)
  }, [fetchSnapshot])

  // Refetch on notification received for this order
  useEffect(() => {
    const unsubscribe = onSocketEvent<{ order_id?: number }>('notification:new', (notification) => {
      if (notification.order_id === orderIdNum) {
        fetchSnapshot()
      }
    })
    return () => unsubscribe()
  }, [orderIdNum, fetchSnapshot])

  // Generate status hint based on progress
  const getStatusHint = (): string => {
    if (!snapshot) return ''
    
    const { progress, order } = snapshot
    
    if (order.status === 'completed') {
      return 'Order fully completed'
    }
    
    if (progress.pending_roles.length > 0) {
      const pendingRole = progress.pending_roles[0]
      const roleName = roleDisplayNames[pendingRole] || pendingRole
      
      // Check if any task for this role has an assignment
      const hasAssignment = snapshot.tasks.some(
        t => t.required_role === pendingRole && t.assignments.length > 0
      )
      
      if (hasAssignment) {
        return `Waiting for ${roleName} to complete their assignment`
      } else {
        return `${roleName} can now claim their task`
      }
    }
    
    if (progress.locked_roles.length > 0) {
      const lockedRole = progress.locked_roles[0]
      const roleName = roleDisplayNames[lockedRole] || lockedRole
      return `Waiting for previous steps to complete before ${roleName}`
    }
    
    return 'Processing order...'
  }

  // Render loading state
  if (loading) {
    return (
      <div className="h-full flex items-center justify-center" style={{ backgroundColor: 'var(--main-bg)' }}>
        <Loader2 className="w-8 h-8 animate-spin" style={{ color: 'var(--accent)' }} />
      </div>
    )
  }

  // Render error state
  if (error) {
    return (
      <div className="h-full flex flex-col items-center justify-center gap-4 p-6" style={{ backgroundColor: 'var(--main-bg)' }}>
        <AlertCircle className="w-12 h-12" style={{ color: 'var(--text-danger, red)' }} />
        <p className="text-lg" style={{ color: 'var(--text-primary)' }}>{error}</p>
        <button
          onClick={() => navigate(-1)}
          className="px-4 py-2 rounded-md transition-colors"
          style={{ backgroundColor: 'var(--accent)', color: 'var(--text-primary)' }}
        >
          Go Back
        </button>
      </div>
    )
  }

  if (!snapshot) {
    return null
  }

  const { order, progress } = snapshot
  const typeConfig = orderTypeConfig[order.order_type] || orderTypeConfig['agent_restock']
  const TypeIcon = typeConfig?.icon || Package

  return (
    <div className="h-full" style={{ backgroundColor: 'var(--main-bg)' }}>
      {/* Header */}
      <div style={{ backgroundColor: 'var(--panel-bg)', borderBottom: '1px solid var(--sidebar-border)' }} className="px-6 py-4">
        <div className="max-w-3xl mx-auto flex items-center justify-between">
          <div className="flex items-center gap-4">
            <button
              onClick={() => navigate(-1)}
              className="p-2 transition-colors"
              style={{ color: 'var(--text-secondary)' }}
            >
              <ArrowLeft size={20} />
            </button>
            <div className="flex items-center gap-3">
              <div className={clsx('p-2 rounded-lg', typeConfig.color)}>
                <TypeIcon size={20} className="text-white" />
              </div>
              <div>
                <h1 className="text-xl font-semibold" style={{ color: 'var(--text-primary)' }}>
                  Order #{order.reference || order.id}
                </h1>
                <p className="text-sm" style={{ color: 'var(--text-secondary)' }}>{typeConfig.label}</p>
              </div>
            </div>
          </div>
          
          <span className={clsx(
            'px-3 py-1 rounded-full text-sm font-medium',
            priorityColors[order.priority] || priorityColors['normal']
          )}>
            {order.priority?.charAt(0).toUpperCase() + order.priority?.slice(1) || 'Normal'}
          </span>
        </div>
      </div>

      {/* Content */}
      <div className="max-w-3xl mx-auto p-6 space-y-6">
        
        {/* Status Hint Banner */}
        <div className="rounded-lg p-4" style={{ backgroundColor: 'var(--panel-bg)', border: '1px solid var(--sidebar-border)' }}>
          <div className="flex items-center gap-3">
            <Clock className="w-5 h-5" style={{ color: 'var(--accent)' }} />
            <p style={{ color: 'var(--text-primary)' }}>{getStatusHint()}</p>
          </div>
        </div>

        {/* Order Summary */}
        <div className="bg-[#2b2d31] border border-[#1f2023] rounded-lg p-6">
          <h2 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
            <FileText size={18} />
            Order Summary
          </h2>
          
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {order.customer_name && (
              <div className="flex items-center gap-3">
                <User className="w-4 h-4" style={{ color: 'var(--text-secondary)' }} />
                <div>
                  <p className="text-xs" style={{ color: 'var(--text-secondary)' }}>Customer</p>
                  <p style={{ color: 'var(--text-primary)' }}>{order.customer_name}</p>
                </div>
              </div>
            )}
            
            {order.customer_phone && (
              <div className="flex items-center gap-3">
                <Phone className="w-4 h-4" style={{ color: 'var(--text-secondary)' }} />
                <div>
                  <p className="text-xs" style={{ color: 'var(--text-secondary)' }}>Phone</p>
                  <p style={{ color: 'var(--text-primary)' }}>{order.customer_phone}</p>
                </div>
              </div>
            )}
            
            {order.delivery_location && (
              <div className="flex items-center gap-3">
                <MapPin className="w-4 h-4" style={{ color: 'var(--text-secondary)' }} />
                <div>
                  <p className="text-xs" style={{ color: 'var(--text-secondary)' }}>Delivery Location</p>
                  <p style={{ color: 'var(--text-primary)' }}>{order.delivery_location}</p>
                </div>
              </div>
            )}
            
            {order.created_at && (
              <div className="flex items-center gap-3">
                <Calendar className="w-4 h-4 text-[#949ba4]" />
                <div>
                  <p className="text-xs text-[#949ba4]">Created</p>
                  <p className="text-[#dbdee1]">
                    {new Date(order.created_at).toLocaleString()}
                  </p>
                </div>
              </div>
            )}
            
            {order.payment_method && (
              <div className="flex items-center gap-3">
                <Package className="w-4 h-4 text-[#949ba4]" />
                <div>
                  <p className="text-xs text-[#949ba4]">Payment</p>
                  <p className="text-[#dbdee1] capitalize">{order.payment_method}</p>
                </div>
              </div>
            )}
          </div>
          
          {order.internal_comment && (
            <div className="mt-4 pt-4" style={{ borderTop: '1px solid var(--sidebar-border)' }}>
              <p className="text-xs mb-1" style={{ color: 'var(--text-secondary)' }}>Notes</p>
              <p style={{ color: 'var(--text-primary)', fontSize: '0.875rem' }}>{order.internal_comment}</p>
            </div>
          )}
        </div>

        {/* Progress Timeline */}
        <div className="bg-[#2b2d31] border border-[#1f2023] rounded-lg p-6">
          <h2 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
            <ClipboardList size={18} />
            Order Progress
          </h2>
          
          <div className="space-y-3">
            {/* Completed roles */}
            {progress.completed_roles.map(role => (
              <div key={`completed-${role}`} className="flex items-center gap-3 p-3 bg-green-500/10 rounded-lg border border-green-500/20">
                <CheckCircle className="w-5 h-5 text-green-400" />
                <span className="text-green-400 font-medium">
                  {roleDisplayNames[role] || role}
                </span>
                <span className="text-green-400/70 text-sm ml-auto">Completed</span>
              </div>
            ))}
            
            {/* Pending roles */}
            {progress.pending_roles.map(role => (
              <div key={`pending-${role}`} className="flex items-center gap-3 p-3 bg-yellow-500/10 rounded-lg border border-yellow-500/20">
                <Clock className="w-5 h-5 text-yellow-400" />
                <span className="text-yellow-400 font-medium">
                  {roleDisplayNames[role] || role}
                </span>
                <span className="text-yellow-400/70 text-sm ml-auto">Waiting</span>
              </div>
            ))}
            
            {/* Locked roles */}
            {progress.locked_roles.map(role => (
              <div key={`locked-${role}`} className="flex items-center gap-3 p-3 bg-gray-500/10 rounded-lg border border-gray-500/20">
                <Lock className="w-5 h-5 text-gray-400" />
                <span className="text-gray-400 font-medium">
                  {roleDisplayNames[role] || role}
                </span>
                <span className="text-gray-400/70 text-sm ml-auto">Locked</span>
              </div>
            ))}
            
            {/* Empty state */}
            {progress.completed_roles.length === 0 && 
             progress.pending_roles.length === 0 && 
             progress.locked_roles.length === 0 && (
              <p className="text-[#949ba4] text-center py-4">
                No workflow tasks for this order
              </p>
            )}
          </div>
        </div>

        {/* Navigation Buttons */}
        <div className="flex gap-4">
          <button
            onClick={() => navigate('/tasks')}
            className="flex-1 flex items-center justify-center gap-2 px-4 py-3 bg-[#5865f2] text-white rounded-lg hover:bg-[#4752c4] transition-colors"
          >
            <ClipboardList size={18} />
            Go to My Tasks
          </button>
          <button
            onClick={() => navigate('/notifications')}
            className="flex-1 flex items-center justify-center gap-2 px-4 py-3 bg-[#2b2d31] text-[#dbdee1] rounded-lg border border-[#1f2023] hover:bg-[#35373c] transition-colors"
          >
            <Bell size={18} />
            Back to Notifications
          </button>
        </div>
      </div>
    </div>
  )
}
