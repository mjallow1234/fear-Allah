/**
 * Order Form Component
 * Role-aware order creation with dry-run preview support.
 * Extended with Forms Extension fields: reference, priority, delivery date, customer info, payment, notes.
 */
import { useState, useEffect } from 'react'
import { useAuthStore } from '../../stores/authStore'
import { X, ShoppingCart, AlertCircle, CheckCircle, Loader2, Eye, ChevronDown, ChevronUp } from 'lucide-react'
import api from '../../services/api'

interface OrderFormProps {
  isOpen: boolean
  onClose: () => void
  onSuccess?: (orderId: number) => void
}

type OrderType = 'AGENT_RESTOCK' | 'AGENT_RETAIL' | 'STORE_KEEPER_RESTOCK' | 'CUSTOMER_WHOLESALE'
type Priority = 'low' | 'normal' | 'high' | 'urgent'
type PaymentMethod = 'cash' | 'card' | 'transfer' | 'credit'

interface OrderTypeConfig {
  value: OrderType
  label: string
  description: string
  allowedRoles: string[]
}

const ORDER_TYPES: OrderTypeConfig[] = [
  {
    value: 'AGENT_RESTOCK',
    label: 'Agent Restock',
    description: 'Agent requests inventory restock from warehouse',
    allowedRoles: ['agent', 'admin', 'system_admin', 'team_admin', 'member'],
  },
  {
    value: 'AGENT_RETAIL',
    label: 'Agent Retail Delivery',
    description: 'Agent orders retail delivery to customer location',
    allowedRoles: ['agent', 'admin', 'system_admin', 'team_admin', 'member'],
  },
  {
    value: 'STORE_KEEPER_RESTOCK',
    label: 'Store Keeper Restock',
    description: 'Store keeper requests warehouse restock',
    allowedRoles: ['storekeeper', 'admin', 'system_admin', 'team_admin'],
  },
  {
    value: 'CUSTOMER_WHOLESALE',
    label: 'Customer Wholesale',
    description: 'Customer places wholesale order for delivery',
    allowedRoles: ['customer', 'agent', 'storekeeper', 'admin', 'system_admin', 'team_admin', 'member'],
  },
]

interface DryRunResult {
  order_type: string
  items: string
  workflow_steps: string[]
  task_count: number
}

export default function OrderForm({ isOpen, onClose, onSuccess }: OrderFormProps) {
  const user = useAuthStore((state) => state.user)
  
  // Form state - Basic
  const [orderType, setOrderType] = useState<OrderType | ''>('')
  const [product, setProduct] = useState('')
  const [amount, setAmount] = useState('')
  const [location, setLocation] = useState('')
  const [notes, setNotes] = useState('')
  
  // Form state - Forms Extension fields
  const [reference, setReference] = useState('')
  const [priority, setPriority] = useState<Priority>('normal')
  const [requestedDeliveryDate, setRequestedDeliveryDate] = useState('')
  const [customerName, setCustomerName] = useState('')
  const [customerPhone, setCustomerPhone] = useState('')
  const [paymentMethod, setPaymentMethod] = useState<PaymentMethod | ''>('')
  const [internalComment, setInternalComment] = useState('')
  const [showAdvanced, setShowAdvanced] = useState(false)
  
  // UI state
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState<string | null>(null)
  const [dryRunResult, setDryRunResult] = useState<DryRunResult | null>(null)
  
  const isAdmin = user?.is_system_admin === true || (user?.operational_roles?.includes('admin') ?? false)
  // Get effective role from operational_roles array (source of truth)
  const effectiveRole = isAdmin
    ? 'admin'
    : user?.operational_roles?.length
      ? user.operational_roles.join(', ')
      : 'member'
  
  // Filter order types based on role
  const availableOrderTypes = ORDER_TYPES.filter(ot => 
    ot.allowedRoles.includes(effectiveRole) || 
    (ot.allowedRoles.includes('admin') && isAdmin)
  )
  
  // Reset form when closed
  useEffect(() => {
    if (!isOpen) {
      setOrderType('')
      setProduct('')
      setAmount('')
      setLocation('')
      setNotes('')
      // Reset Forms Extension fields
      setReference('')
      setPriority('normal')
      setRequestedDeliveryDate('')
      setCustomerName('')
      setCustomerPhone('')
      setPaymentMethod('')
      setInternalComment('')
      setShowAdvanced(false)
      setError(null)
      setSuccess(null)
      setDryRunResult(null)
    }
  }, [isOpen])
  
  const handleDryRun = async () => {
    if (!orderType || !product || !amount) {
      setError('Please fill in order type, product, and amount')
      return
    }
    
    setLoading(true)
    setError(null)
    setDryRunResult(null)
    
    try {
      // Simulate dry-run by showing what would happen
      const selectedType = ORDER_TYPES.find(ot => ot.value === orderType)
      
      // Build workflow steps based on order type
      const workflowSteps: string[] = []
      let taskCount = 0
      
      switch (orderType) {
        case 'AGENT_RESTOCK':
          workflowSteps.push(
            '1. Assemble Items (Foreman)',
            '2. Hand Over to Delivery (Foreman)',
            '3. Receive from Foreman (Delivery)',
            '4. Deliver to Agent (Delivery)',
            '5. Confirm Receipt (Agent)'
          )
          taskCount = 5
          break
        case 'AGENT_RETAIL':
          workflowSteps.push(
            '1. Acknowledge Order (Delivery)',
            '2. Deliver Items (Delivery)'
          )
          taskCount = 2
          break
        case 'STORE_KEEPER_RESTOCK':
          workflowSteps.push(
            '1. Assemble Items (Foreman)',
            '2. Acknowledge Handover (Delivery)',
            '3. Deliver Items (Delivery)',
            '4. Confirm Received (Store Keeper)'
          )
          taskCount = 4
          break
        case 'CUSTOMER_WHOLESALE':
          workflowSteps.push(
            '1. Assemble Items (Foreman)',
            '2. Acknowledge Handover (Delivery)',
            '3. Deliver Items (Delivery)'
          )
          taskCount = 3
          break
      }
      
      setDryRunResult({
        order_type: selectedType?.label || orderType,
        items: `${product} x ${amount}`,
        workflow_steps: workflowSteps,
        task_count: taskCount,
      })
    } catch (err) {
      setError('Failed to preview order')
    } finally {
      setLoading(false)
    }
  }
  
  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    
    if (!orderType || !product || !amount) {
      setError('Please fill in order type, product, and amount')
      return
    }
    
    setLoading(true)
    setError(null)
    setSuccess(null)
    
    try {
      const items = [{
        product_name: product,
        quantity: parseInt(amount, 10),
      }]
      
      const metadata: Record<string, string> = {}
      if (location) metadata.location = location
      if (notes) metadata.notes = notes
      
      // Build request payload with Forms Extension fields
      const payload: Record<string, unknown> = {
        order_type: orderType,
        items,
        metadata,
      }
      
      // Add Forms Extension fields (only if provided)
      if (reference) payload.reference = reference
      if (priority && priority !== 'normal') payload.priority = priority
      if (requestedDeliveryDate) payload.requested_delivery_date = new Date(requestedDeliveryDate).toISOString()
      if (customerName) payload.customer_name = customerName
      if (customerPhone) payload.customer_phone = customerPhone
      if (paymentMethod) payload.payment_method = paymentMethod
      if (internalComment) payload.internal_comment = internalComment
      
      const response = await api.post('/api/orders/', payload)
      
      setSuccess(`Order #${response.data.order_id} created successfully!`)
      setDryRunResult(null)
      
      if (onSuccess) {
        onSuccess(response.data.order_id)
      }
      
      // Auto-close after success
      setTimeout(() => {
        onClose()
      }, 2000)
    } catch (err: unknown) {
      const errorMessage = err instanceof Error ? err.message : 'Failed to create order'
      if (typeof err === 'object' && err !== null && 'response' in err) {
        const axiosError = err as { response?: { data?: { detail?: string } } }
        setError(axiosError.response?.data?.detail || errorMessage)
      } else {
        setError(errorMessage)
      }
    } finally {
      setLoading(false)
    }
  }
  
  if (!isOpen) return null
  
  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
      <div className="bg-[#313338] rounded-lg w-full max-w-lg mx-4 max-h-[90vh] overflow-y-auto">
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b border-[#3f4147]">
          <div className="flex items-center gap-2">
            <ShoppingCart className="text-orange-400" size={20} />
            <h2 className="text-lg font-semibold text-white">Create Order</h2>
          </div>
          <button
            onClick={onClose}
            className="text-[#949ba4] hover:text-white transition-colors"
          >
            <X size={20} />
          </button>
        </div>
        
        {/* Role Badge */}
        <div className="px-4 pt-3">
          <span className="text-xs bg-[#5865f2] text-white px-2 py-1 rounded">
            Role: {effectiveRole}
          </span>
        </div>
        
        {/* Form */}
        <form onSubmit={handleSubmit} className="p-4 space-y-4">
          {/* Order Type */}
          <div>
            <label className="block text-sm font-medium text-[#b5bac1] mb-1">
              Order Type *
            </label>
            <select
              value={orderType}
              onChange={(e) => {
                setOrderType(e.target.value as OrderType)
                setDryRunResult(null)
              }}
              className="w-full bg-[#1e1f22] border border-[#3f4147] rounded px-3 py-2 text-white focus:outline-none focus:border-[#5865f2]"
              required
            >
              <option value="">Select order type...</option>
              {availableOrderTypes.map((ot) => (
                <option key={ot.value} value={ot.value}>
                  {ot.label}
                </option>
              ))}
            </select>
            {orderType && (
              <p className="text-xs text-[#949ba4] mt-1">
                {ORDER_TYPES.find(ot => ot.value === orderType)?.description}
              </p>
            )}
          </div>
          
          {/* Product */}
          <div>
            <label className="block text-sm font-medium text-[#b5bac1] mb-1">
              Product *
            </label>
            <input
              type="text"
              value={product}
              onChange={(e) => setProduct(e.target.value)}
              placeholder="e.g., Cement Bag 25kg"
              className="w-full bg-[#1e1f22] border border-[#3f4147] rounded px-3 py-2 text-white placeholder-[#72767d] focus:outline-none focus:border-[#5865f2]"
              required
            />
          </div>
          
          {/* Amount */}
          <div>
            <label className="block text-sm font-medium text-[#b5bac1] mb-1">
              Amount *
            </label>
            <input
              type="number"
              value={amount}
              onChange={(e) => setAmount(e.target.value)}
              placeholder="Quantity"
              min="1"
              className="w-full bg-[#1e1f22] border border-[#3f4147] rounded px-3 py-2 text-white placeholder-[#72767d] focus:outline-none focus:border-[#5865f2]"
              required
            />
          </div>
          
          {/* Location (optional) */}
          {(orderType === 'AGENT_RETAIL' || orderType === 'CUSTOMER_WHOLESALE') && (
            <div>
              <label className="block text-sm font-medium text-[#b5bac1] mb-1">
                Delivery Location
              </label>
              <input
                type="text"
                value={location}
                onChange={(e) => setLocation(e.target.value)}
                placeholder="e.g., 123 Main St, City"
                className="w-full bg-[#1e1f22] border border-[#3f4147] rounded px-3 py-2 text-white placeholder-[#72767d] focus:outline-none focus:border-[#5865f2]"
              />
            </div>
          )}
          
          {/* Priority */}
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-sm font-medium text-[#b5bac1] mb-1">
                Priority
              </label>
              <select
                value={priority}
                onChange={(e) => setPriority(e.target.value as Priority)}
                className="w-full bg-[#1e1f22] border border-[#3f4147] rounded px-3 py-2 text-white focus:outline-none focus:border-[#5865f2]"
              >
                <option value="low">🟢 Low</option>
                <option value="normal">🔵 Normal</option>
                <option value="high">🟠 High</option>
                <option value="urgent">🔴 Urgent</option>
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium text-[#b5bac1] mb-1">
                Payment Method
              </label>
              <select
                value={paymentMethod}
                onChange={(e) => setPaymentMethod(e.target.value as PaymentMethod)}
                className="w-full bg-[#1e1f22] border border-[#3f4147] rounded px-3 py-2 text-white focus:outline-none focus:border-[#5865f2]"
              >
                <option value="">Not specified</option>
                <option value="cash">💵 Cash</option>
                <option value="card">💳 Card</option>
                <option value="transfer">🏦 Transfer</option>
                <option value="credit">📝 Credit</option>
              </select>
            </div>
          </div>
          
          {/* Delivery Date */}
          <div>
            <label className="block text-sm font-medium text-[#b5bac1] mb-1">
              Requested Delivery Date
            </label>
            <input
              type="datetime-local"
              value={requestedDeliveryDate}
              onChange={(e) => setRequestedDeliveryDate(e.target.value)}
              className="w-full bg-[#1e1f22] border border-[#3f4147] rounded px-3 py-2 text-white focus:outline-none focus:border-[#5865f2]"
            />
          </div>
          
          {/* Advanced Fields Toggle */}
          <button
            type="button"
            onClick={() => setShowAdvanced(!showAdvanced)}
            className="flex items-center gap-2 text-sm text-[#949ba4] hover:text-white transition-colors w-full"
          >
            {showAdvanced ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
            {showAdvanced ? 'Hide' : 'Show'} Advanced Options
          </button>
          
          {/* Advanced Fields */}
          {showAdvanced && (
            <div className="space-y-4 p-3 bg-[#1e1f22] rounded-lg border border-[#3f4147]">
              {/* Reference */}
              <div>
                <label className="block text-sm font-medium text-[#b5bac1] mb-1">
                  Reference / PO Number
                </label>
                <input
                  type="text"
                  value={reference}
                  onChange={(e) => setReference(e.target.value)}
                  placeholder="e.g., PO-2025-001"
                  className="w-full bg-[#2b2d31] border border-[#3f4147] rounded px-3 py-2 text-white placeholder-[#72767d] focus:outline-none focus:border-[#5865f2]"
                />
              </div>
              
              {/* Customer Info */}
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-sm font-medium text-[#b5bac1] mb-1">
                    Customer Name
                  </label>
                  <input
                    type="text"
                    value={customerName}
                    onChange={(e) => setCustomerName(e.target.value)}
                    placeholder="Customer name"
                    className="w-full bg-[#2b2d31] border border-[#3f4147] rounded px-3 py-2 text-white placeholder-[#72767d] focus:outline-none focus:border-[#5865f2]"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-[#b5bac1] mb-1">
                    Customer Phone
                  </label>
                  <input
                    type="tel"
                    value={customerPhone}
                    onChange={(e) => setCustomerPhone(e.target.value)}
                    placeholder="+1234567890"
                    className="w-full bg-[#2b2d31] border border-[#3f4147] rounded px-3 py-2 text-white placeholder-[#72767d] focus:outline-none focus:border-[#5865f2]"
                  />
                </div>
              </div>
              
              {/* Internal Comment */}
              <div>
                <label className="block text-sm font-medium text-[#b5bac1] mb-1">
                  Internal Comment
                </label>
                <textarea
                  value={internalComment}
                  onChange={(e) => setInternalComment(e.target.value)}
                  placeholder="Internal notes (not visible to customer)"
                  rows={2}
                  className="w-full bg-[#2b2d31] border border-[#3f4147] rounded px-3 py-2 text-white placeholder-[#72767d] focus:outline-none focus:border-[#5865f2] resize-none"
                />
              </div>
            </div>
          )}
          
          {/* Notes */}
          <div>
            <label className="block text-sm font-medium text-[#b5bac1] mb-1">
              Notes (optional)
            </label>
            <textarea
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              placeholder="Any additional notes..."
              rows={2}
              className="w-full bg-[#1e1f22] border border-[#3f4147] rounded px-3 py-2 text-white placeholder-[#72767d] focus:outline-none focus:border-[#5865f2] resize-none"
            />
          </div>
          
          {/* Dry Run Result */}
          {dryRunResult && (
            <div className="bg-[#1e1f22] rounded-lg p-4 border border-[#3f4147]">
              <div className="flex items-center gap-2 mb-3">
                <Eye className="text-blue-400" size={16} />
                <span className="text-sm font-medium text-blue-400">Preview</span>
              </div>
              <div className="space-y-2 text-sm">
                <p className="text-[#b5bac1]">
                  <span className="text-[#949ba4]">Type:</span> {dryRunResult.order_type}
                </p>
                <p className="text-[#b5bac1]">
                  <span className="text-[#949ba4]">Items:</span> {dryRunResult.items}
                </p>
                <div>
                  <p className="text-[#949ba4] mb-1">Workflow ({dryRunResult.task_count} tasks):</p>
                  <ul className="space-y-1 text-[#b5bac1]">
                    {dryRunResult.workflow_steps.map((step, i) => (
                      <li key={i} className="text-xs">• {step}</li>
                    ))}
                  </ul>
                </div>
              </div>
            </div>
          )}
          
          {/* Error */}
          {error && (
            <div className="flex items-center gap-2 text-red-400 bg-red-400/10 rounded p-3">
              <AlertCircle size={16} />
              <span className="text-sm">{error}</span>
            </div>
          )}
          
          {/* Success */}
          {success && (
            <div className="flex items-center gap-2 text-green-400 bg-green-400/10 rounded p-3">
              <CheckCircle size={16} />
              <span className="text-sm">{success}</span>
            </div>
          )}
          
          {/* Actions */}
          <div className="flex gap-3 pt-2">
            <button
              type="button"
              onClick={handleDryRun}
              disabled={loading || !orderType || !product || !amount}
              className="flex-1 flex items-center justify-center gap-2 bg-[#4f545c] hover:bg-[#5d6269] disabled:opacity-50 disabled:cursor-not-allowed text-white py-2 px-4 rounded transition-colors"
            >
              <Eye size={16} />
              Preview
            </button>
            <button
              type="submit"
              disabled={loading}
              className="flex-1 flex items-center justify-center gap-2 bg-[#5865f2] hover:bg-[#4752c4] disabled:opacity-50 disabled:cursor-not-allowed text-white py-2 px-4 rounded transition-colors"
            >
              {loading ? (
                <Loader2 size={16} className="animate-spin" />
              ) : (
                <ShoppingCart size={16} />
              )}
              {loading ? 'Creating...' : 'Create Order'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}
