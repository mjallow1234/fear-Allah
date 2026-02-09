/**
 * Orders List Page
 * Phase 7.3 - Order UI
 * 
 * Displays orders with status and automation info.
 * Note: Backend doesn't have order list API yet, so orders come from
 * notifications, tasks, and realtime events.
 */
import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { 
  ArrowLeft, 
  ShoppingCart, 
  Package,
  Warehouse,
  Tag,
  Loader2,
  RefreshCw,
  AlertCircle,
  Clock,
  CheckCircle,
  XCircle,
  PlayCircle,
  PauseCircle,
  Plus
} from 'lucide-react'
import clsx from 'clsx'
import { useOrderStore, OrderWithDetails } from '../stores/orderStore'
import { subscribeToOrders } from '../realtime/orders'
import RecentAutomationEvents from '../components/RecentAutomationEvents'
import OrderForm from '../components/forms/OrderForm'
import DynamicFormModal from '../components/forms/DynamicFormModal'

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

function OrderCard({ order, onClick }: { order: OrderWithDetails; onClick: () => void }) {
  const typeConfig = orderTypeConfig[normalizeType(order.order_type)] || orderTypeConfig['AGENT_RESTOCK']
  const status = statusConfig[normalizeStatus(order.status)] || statusConfig['SUBMITTED']
  const TypeIcon = typeConfig.icon
  const StatusIcon = status.icon
  
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
    <div
      onClick={onClick}
      className={clsx('p-4 rounded-lg cursor-pointer transition-all border')}
      style={{
        backgroundColor: 'var(--panel-bg)',
        borderColor: 'var(--sidebar-border)',
        opacity: (order.status === 'COMPLETED' || order.status === 'CANCELLED') ? 0.75 : 1
      }}
      onMouseEnter={(e) => { if (!(order.status === 'COMPLETED' || order.status === 'CANCELLED')) { (e.currentTarget as HTMLDivElement).style.backgroundColor = 'var(--sidebar-hover)'; (e.currentTarget as HTMLDivElement).style.borderColor = 'var(--sidebar-hover)'; } }}
      onMouseLeave={(e) => { if (!(order.status === 'COMPLETED' || order.status === 'CANCELLED')) { (e.currentTarget as HTMLDivElement).style.backgroundColor = 'var(--panel-bg)'; (e.currentTarget as HTMLDivElement).style.borderColor = 'var(--sidebar-border)'; } }}
    >
      <div className="flex items-start gap-4">
        {/* Type Icon */}
        <div className={clsx(
          'w-10 h-10 rounded-lg flex items-center justify-center text-white',
          typeConfig.color
        )}>
          <TypeIcon size={20} />
        </div>
        
        {/* Content */}
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <span className="font-medium" style={{ color: 'var(--text-primary)' }}>Order #{order.id}</span>
            <span className={clsx(
              'text-xs px-2 py-0.5 rounded-full flex items-center gap-1',
              status.bgColor,
              status.color
            )}>
              <StatusIcon size={12} />
              {status.label}
            </span>
          </div>
          
          <div className="flex items-center gap-4 text-xs" style={{ color: 'var(--text-muted)' }}>
            <span className="flex items-center gap-1">
              <Clock size={12} />
              {formatTime(order.created_at)}
            </span>
            <span className={clsx('px-1.5 py-0.5 rounded', typeConfig.color + '/20')} style={{ color: 'var(--text-primary)' }}>
              {typeConfig.label}
            </span>
          </div>
          
          {/* Automation progress */}
          {order.automation?.has_automation && (
            <div className="mt-2 pt-2 border-t border-[#1f2023]">
              <div className="flex items-center gap-2 text-xs">
                <span className="text-[#72767d]">Automation:</span>
                <div className="flex-1 bg-[#1f2023] rounded-full h-1.5">
                  <div 
                    className="bg-[#5865f2] h-1.5 rounded-full transition-all"
                    style={{ width: `${order.automation.progress_percent || 0}%` }}
                  />
                </div>
                <span className="text-[#949ba4]">
                  {order.automation.completed_assignments || 0}/{order.automation.total_assignments || 0}
                </span>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

export default function OrdersPage() {
  const navigate = useNavigate()
  const [showOrderForm, setShowOrderForm] = useState(false)
  // Use dynamic forms when available (toggle _setUseDynamicForms to false for legacy forms)
  const [useDynamicForms, _setUseDynamicForms] = useState(true)
  const {
    orders,
    loading,
    error,
    fetchOrders,
    clearError,
  } = useOrderStore()
  
  // Subscribe to order events on mount
  useEffect(() => {
    const unsubscribe = subscribeToOrders()
    return () => unsubscribe()
  }, [])
  
  // Fetch orders on mount
  useEffect(() => {
    fetchOrders()
  }, [fetchOrders])
  
  const handleRefresh = () => {
    fetchOrders()
  }
  
  // Separate active and completed orders
  const activeOrders = orders.filter(o => o.status !== 'COMPLETED' && o.status !== 'CANCELLED')
  const completedOrders = orders.filter(o => o.status === 'COMPLETED' || o.status === 'CANCELLED')

  return (
    <div className="h-full" style={{ backgroundColor: 'var(--main-bg)' }}>
      {/* Header */}
      <div style={{ backgroundColor: 'var(--panel-bg)', borderBottom: '1px solid var(--sidebar-border)' }} className="px-6 py-4">
        <div className="max-w-4xl mx-auto flex items-center justify-between">
          <div className="flex items-center gap-4">
            <button
              onClick={() => navigate(-1)}
              className="p-2 transition-colors"
              style={{ color: 'var(--text-secondary)' }}
            >
              <ArrowLeft size={20} />
            </button>
            <div>
              <h1 className="text-xl font-semibold flex items-center gap-2" style={{ color: 'var(--text-primary)' }}>
                <ShoppingCart size={24} />
                Orders
              </h1>
              <p className="text-sm" style={{ color: 'var(--text-secondary)' }}>
                {activeOrders.length} active order{activeOrders.length !== 1 ? 's' : ''}
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={() => setShowOrderForm(true)}
              className="flex items-center gap-2 px-3 py-2 rounded-lg bg-green-600 hover:bg-green-700 text-white transition-colors"
            >
              <Plus size={16} />
              New Order
            </button>
            <button
              onClick={handleRefresh}
              disabled={loading}
              className={clsx(
                'flex items-center gap-2 px-3 py-2 rounded-lg transition-colors',
                loading
                  ? 'bg-[#1f2023] text-[#72767d] cursor-not-allowed'
                  : 'bg-[#5865f2] hover:bg-[#4752c4] text-white'
              )}
            >
              <RefreshCw size={16} className={loading ? 'animate-spin' : ''} />
              Refresh
            </button>
          </div>
        </div>
      </div>
      
      {/* Error Banner */}
      {error && (
        <div className="max-w-4xl mx-auto px-6 py-4">
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
      
      {/* Order List */}
      <div className="max-w-4xl mx-auto py-6 px-6">
        {/* Recent Automation Events Panel */}
        <div className="mb-6">
          <RecentAutomationEvents />
        </div>
        
        {loading ? (
          <div className="py-12 text-center">
            <Loader2 className="animate-spin mx-auto mb-4" size={32} style={{ color: 'var(--accent)' }} />
            <p style={{ color: 'var(--text-secondary)' }}>Loading orders...</p>
          </div>
        ) : orders.length === 0 ? (
          <div className="py-12 text-center">
            <ShoppingCart size={48} className="mx-auto mb-4" style={{ color: 'var(--text-secondary)', opacity: 0.5 }} />
            <p style={{ color: 'var(--text-secondary)' }}>No orders yet</p>
            <p style={{ color: 'var(--text-muted)', fontSize: '0.875rem', marginTop: '0.25rem' }}>
              Orders will appear here as they are created
            </p>
          </div>
        ) : (
          <div className="space-y-6">
            {/* Active Orders */}
            {activeOrders.length > 0 && (
              <div>
                <h2 className="text-sm font-semibold text-[#949ba4] uppercase tracking-wide mb-3">
                  Active Orders ({activeOrders.length})
                </h2>
                <div className="space-y-3">
                  {activeOrders.map((order) => (
                    <OrderCard
                      key={order.id}
                      order={order}
                      onClick={() => navigate(`/orders/${order.id}`)}
                    />
                  ))}
                </div>
              </div>
            )}
            
            {/* Completed Orders */}
            {completedOrders.length > 0 && (
              <div>
                <h2 className="text-sm font-semibold text-[#949ba4] uppercase tracking-wide mb-3">
                  Completed ({completedOrders.length})
                </h2>
                <div className="space-y-3">
                  {completedOrders.map((order) => (
                    <OrderCard
                      key={order.id}
                      order={order}
                      onClick={() => navigate(`/orders/${order.id}`)}
                    />
                  ))}
                </div>
              </div>
            )}
          </div>
        )}
      </div>
      
      {/* Order Form Modal - Use dynamic form if available */}
      {useDynamicForms ? (
        <DynamicFormModal
          isOpen={showOrderForm}
          onClose={() => setShowOrderForm(false)}
          formSlug="orders"
          title="Create Order"
          onSuccess={() => {
            fetchOrders()
          }}
          fallbackComponent={
            <OrderForm
              isOpen={true}
              onClose={() => setShowOrderForm(false)}
              onSuccess={() => {
                fetchOrders()
                setShowOrderForm(false)
              }}
            />
          }
        />
      ) : (
        <OrderForm
          isOpen={showOrderForm}
          onClose={() => setShowOrderForm(false)}
          onSuccess={() => {
            fetchOrders()
          }}
        />
      )}
    </div>
  )
}
