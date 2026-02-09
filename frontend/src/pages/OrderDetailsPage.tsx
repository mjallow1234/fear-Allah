/**
 * Order Details Page
 * Phase 7.3 - Order UI
 * 
 * Displays single order details with automation status.
 * Route: /orders/:id
 */
import { useEffect } from 'react'
import { useParams, useNavigate, Link } from 'react-router-dom'
import { 
  ArrowLeft, 
  ShoppingCart, 
  Package,
  Warehouse,
  Tag,
  Loader2,
  AlertCircle,
  Clock,
  CheckCircle,
  XCircle,
  PlayCircle,
  PauseCircle,
  ClipboardList,
  ExternalLink,
  User,
  FileText
} from 'lucide-react'
import clsx from 'clsx'
import { useOrderStore } from '../stores/orderStore'
import { subscribeToOrders } from '../realtime/orders'

// Helper to normalize to uppercase for config lookup
const normalizeType = (type: string): string => type?.toUpperCase() || 'AGENT_RESTOCK'
const normalizeStatus = (status: string): string => status?.toUpperCase() || 'SUBMITTED'

// Order type icons and colors
const orderTypeConfig: Record<string, { icon: typeof Package; color: string; label: string }> = {
  'AGENT_RESTOCK': { icon: Warehouse, color: 'bg-blue-600', label: 'Agent Restock' },
  'AGENT_RETAIL': { icon: ShoppingCart, color: 'bg-green-600', label: 'Agent Retail' },
  'STORE_KEEPER_RESTOCK': { icon: Warehouse, color: 'bg-purple-600', label: 'Store Restock' },
  'CUSTOMER_WHOLESALE': { icon: Tag, color: 'bg-orange-600', label: 'Wholesale' },
}

// Status badge config
const statusConfig: Record<string, { color: string; bgColor: string; icon: typeof CheckCircle; label: string }> = {
  'DRAFT': { color: 'text-gray-400', bgColor: 'bg-gray-400/10', icon: PauseCircle, label: 'Draft' },
  'SUBMITTED': { color: 'text-yellow-400', bgColor: 'bg-yellow-400/10', icon: Clock, label: 'Submitted' },
  'IN_PROGRESS': { color: 'text-blue-400', bgColor: 'bg-blue-400/10', icon: PlayCircle, label: 'In Progress' },
  'AWAITING_CONFIRMATION': { color: 'text-orange-400', bgColor: 'bg-orange-400/10', icon: PauseCircle, label: 'Awaiting Confirmation' },
  'COMPLETED': { color: 'text-green-400', bgColor: 'bg-green-400/10', icon: CheckCircle, label: 'Completed' },
  'CANCELLED': { color: 'text-red-400', bgColor: 'bg-red-400/10', icon: XCircle, label: 'Cancelled' },
}

export default function OrderDetailsPage() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const orderId = parseInt(id || '0', 10)
  
  const {
    selectedOrder,
    automationStatus,
    loadingOrder,
    loadingAutomation,
    error,
    fetchOrderById,
    clearError,
  } = useOrderStore()
  
  // Subscribe to order events on mount
  useEffect(() => {
    const unsubscribe = subscribeToOrders()
    return () => unsubscribe()
  }, [])
  
  // Fetch order on mount
  useEffect(() => {
    if (orderId > 0) {
      fetchOrderById(orderId)
    }
  }, [orderId, fetchOrderById])
  
  const formatDate = (dateStr: string) => {
    return new Date(dateStr).toLocaleString()
  }
  
  const order = selectedOrder
  const typeConfig = order ? (orderTypeConfig[normalizeType(order.order_type)] || orderTypeConfig['AGENT_RESTOCK']) : null
  const status = order ? (statusConfig[normalizeStatus(order.status)] || statusConfig['SUBMITTED']) : null
  const TypeIcon = typeConfig?.icon || Package
  const StatusIcon = status?.icon || Clock

  return (
    <div className="h-full bg-[#313338]">
      {/* Header */}
      <div className="bg-[#2b2d31] border-b border-[#1f2023] px-6 py-4">
        <div className="max-w-3xl mx-auto flex items-center justify-between">
          <div className="flex items-center gap-4">
            <button
              onClick={() => navigate('/orders')}
              className="p-2 text-[#949ba4] hover:text-white transition-colors"
            >
              <ArrowLeft size={20} />
            </button>
            <div className="flex items-center gap-3">
              {typeConfig && (
                <div className={clsx(
                  'w-10 h-10 rounded-lg flex items-center justify-center text-white',
                  typeConfig.color
                )}>
                  <TypeIcon size={20} />
                </div>
              )}
              <div>
                <h1 className="text-xl font-semibold text-white">
                  Order #{orderId}
                </h1>
                {status && (
                  <span className={clsx(
                    'text-xs px-2 py-0.5 rounded-full inline-flex items-center gap-1',
                    status.bgColor,
                    status.color
                  )}>
                    <StatusIcon size={12} />
                    {status.label}
                  </span>
                )}
              </div>
            </div>
          </div>
        </div>
      </div>
      
      {/* Error Banner */}
      {error && (
        <div className="max-w-3xl mx-auto px-6 py-4">
          <div className="bg-red-500/10 border border-red-500/20 rounded-lg p-4 flex items-center gap-3">
            <AlertCircle className="text-red-400" size={20} />
            <span className="text-red-400 flex-1">{error}</span>
            <button
              onClick={clearError}
              className="text-red-400 hover:text-red-300 text-sm"
            >
              Dismiss
            </button>
          </div>
        </div>
      )}
      
      {/* Content */}
      <div className="max-w-3xl mx-auto py-6 px-6">
        {loadingOrder ? (
          <div className="py-12 text-center">
            <Loader2 className="animate-spin mx-auto mb-4" size={32} style={{ color: 'var(--accent)' }} />
            <p style={{ color: 'var(--text-secondary)' }}>Loading order details...</p>
          </div>
        ) : !order ? (
          <div className="py-12 text-center">
            <ShoppingCart size={48} className="mx-auto mb-4 text-[#949ba4] opacity-50" />
            <p className="text-[#949ba4]">Order not found</p>
            <button
              onClick={() => navigate('/orders')}
              className="mt-4 text-[#00a8fc] hover:underline"
            >
              Back to Orders
            </button>
          </div>
        ) : (
          <div className="space-y-6">
            {/* Order Info */}
            <div className="bg-[#2b2d31] rounded-lg p-6">
              <h2 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
                <FileText size={20} />
                Order Information
              </h2>
              
              <div className="grid grid-cols-2 gap-4">
                <div className="bg-[#1f2023] rounded-lg p-3">
                  <span className="text-xs text-[#72767d] block mb-1">Order ID</span>
                  <span className="text-white font-medium">#{order.id}</span>
                </div>
                <div className="bg-[#1f2023] rounded-lg p-3">
                  <span className="text-xs text-[#72767d] block mb-1">Type</span>
                  <span className="text-white font-medium">{typeConfig?.label || order.order_type}</span>
                </div>
                <div className="bg-[#1f2023] rounded-lg p-3">
                  <span className="text-xs text-[#72767d] block mb-1">Status</span>
                  <span className={clsx('font-medium', status?.color || 'text-white')}>
                    {status?.label || order.status}
                  </span>
                </div>
                <div className="bg-[#1f2023] rounded-lg p-3">
                  <span className="text-xs text-[#72767d] block mb-1">Created</span>
                  <span className="text-white text-sm">{formatDate(order.created_at)}</span>
                </div>
                {order.updated_at && (
                  <div className="bg-[#1f2023] rounded-lg p-3">
                    <span className="text-xs text-[#72767d] block mb-1">Updated</span>
                    <span className="text-white text-sm">{formatDate(order.updated_at)}</span>
                  </div>
                )}
              </div>
              
              {/* Items (if available) */}
              {order.items && (
                <div className="mt-4">
                  <h3 className="text-sm font-semibold text-white mb-2">Items</h3>
                  <div className="bg-[#1f2023] rounded-lg p-3">
                    <pre className="text-xs text-[#949ba4] whitespace-pre-wrap overflow-x-auto">
                      {order.items}
                    </pre>
                  </div>
                </div>
              )}
              
              {/* Metadata (if available) */}
              {order.meta && (
                <div className="mt-4">
                  <h3 className="text-sm font-semibold text-white mb-2">Additional Info</h3>
                  <div className="bg-[#1f2023] rounded-lg p-3">
                    <pre className="text-xs text-[#949ba4] whitespace-pre-wrap overflow-x-auto">
                      {order.meta}
                    </pre>
                  </div>
                </div>
              )}
            </div>
            
            {/* Automation Section */}
            <div className="bg-[#2b2d31] rounded-lg p-6">
              <h2 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
                <ClipboardList size={20} />
                Automation Status
              </h2>
              
              {loadingAutomation ? (
                <div className="py-8 text-center">
                  <Loader2 className="animate-spin mx-auto mb-2 text-[#5865f2]" size={24} />
                  <p className="text-[#949ba4] text-sm">Loading automation status...</p>
                </div>
              ) : !automationStatus?.has_automation ? (
                <div className="py-8 text-center bg-[#1f2023] rounded-lg">
                  <ClipboardList size={32} className="mx-auto mb-2 text-[#949ba4] opacity-50" />
                  <p className="text-[#949ba4]">No automation linked to this order</p>
                </div>
              ) : (
                <div className="space-y-4">
                  {/* Task Info */}
                  <div className="bg-[#1f2023] rounded-lg p-4">
                    <div className="flex items-center justify-between mb-3">
                      <div>
                        <span className="text-white font-medium">{automationStatus.title}</span>
                        <div className="flex items-center gap-2 mt-1">
                          <span className={clsx(
                            'text-xs px-2 py-0.5 rounded-full',
                            automationStatus.task_status === 'COMPLETED' 
                              ? 'bg-green-400/10 text-green-400'
                              : automationStatus.task_status === 'IN_PROGRESS'
                                ? 'bg-blue-400/10 text-blue-400'
                                : 'bg-yellow-400/10 text-yellow-400'
                          )}>
                            {automationStatus.task_status}
                          </span>
                        </div>
                      </div>
                      <Link
                        to="/tasks"
                        className="flex items-center gap-1 text-[#00a8fc] hover:underline text-sm"
                      >
                        View Task
                        <ExternalLink size={14} />
                      </Link>
                    </div>
                    
                    {/* Progress */}
                    <div className="mt-4">
                      <div className="flex items-center justify-between text-sm mb-2">
                        <span className="text-[#949ba4] flex items-center gap-1">
                          <User size={14} />
                          Assignments Progress
                        </span>
                        <span className="text-white">
                          {automationStatus.completed_assignments}/{automationStatus.total_assignments} completed
                        </span>
                      </div>
                      <div className="bg-[#313338] rounded-full h-2">
                        <div 
                          className={clsx(
                            'h-2 rounded-full transition-all',
                            automationStatus.progress_percent === 100 ? 'bg-green-500' : 'bg-[#5865f2]'
                          )}
                          style={{ width: `${automationStatus.progress_percent || 0}%` }}
                        />
                      </div>
                      <p className="text-xs text-[#72767d] mt-1 text-right">
                        {automationStatus.progress_percent}% complete
                      </p>
                    </div>
                  </div>
                  
                  {/* Task ID */}
                  <div className="text-xs text-[#72767d] flex items-center gap-2">
                    <span>Task ID: #{automationStatus.task_id}</span>
                  </div>
                </div>
              )}
            </div>
            
            {/* Status Timeline Placeholder */}
            <div className="bg-[#2b2d31] rounded-lg p-6">
              <h2 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
                <Clock size={20} />
                Status Timeline
              </h2>
              
              <div className="relative">
                {/* Timeline line */}
                <div className="absolute left-3 top-0 bottom-0 w-0.5 bg-[#1f2023]" />
                
                <div className="space-y-4">
                  {/* Created */}
                  <div className="relative pl-8">
                    <div className={clsx(
                      'absolute left-1.5 top-1.5 w-3 h-3 rounded-full',
                      'bg-[#5865f2]'
                    )} />
                    <div className="bg-[#1f2023] rounded-lg p-3">
                      <div className="flex items-center justify-between">
                        <span className="text-white font-medium text-sm">Order Created</span>
                        <span className="text-xs text-[#72767d]">{formatDate(order.created_at)}</span>
                      </div>
                      <span className="text-xs text-[#949ba4]">Order #{order.id} was created</span>
                    </div>
                  </div>
                  
                  {/* Current Status */}
                  {order.status !== 'SUBMITTED' && (
                    <div className="relative pl-8">
                      <div className={clsx(
                        'absolute left-1.5 top-1.5 w-3 h-3 rounded-full',
                        order.status === 'COMPLETED' ? 'bg-green-500' :
                        order.status === 'CANCELLED' ? 'bg-red-500' : 'bg-blue-500'
                      )} />
                      <div className="bg-[#1f2023] rounded-lg p-3">
                        <div className="flex items-center justify-between">
                          <span className="text-white font-medium text-sm">
                            Status: {status?.label || order.status}
                          </span>
                          {order.updated_at && (
                            <span className="text-xs text-[#72767d]">{formatDate(order.updated_at)}</span>
                          )}
                        </div>
                      </div>
                    </div>
                  )}
                </div>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
