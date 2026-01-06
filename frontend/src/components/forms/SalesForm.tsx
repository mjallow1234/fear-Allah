/**
 * Sales Form Component
 * Record sales with inventory selector and stock validation.
 * Extended with Forms Extension fields: discount, payment method, sale date, affiliate tracking.
 */
import { useState, useEffect } from 'react'
import { useAuthStore } from '../../stores/authStore'
import { X, DollarSign, AlertCircle, CheckCircle, Loader2, Package, ChevronDown, ChevronUp, Users } from 'lucide-react'
import api from '../../services/api'

interface SalesFormProps {
  isOpen: boolean
  onClose: () => void
  onSuccess?: () => void
}

interface InventoryItem {
  id: number
  product_id: number
  product_name: string
  total_stock: number
  total_sold: number
  low_stock_threshold: number
  is_low_stock: boolean
}

type SalesChannel = 'field' | 'store' | 'delivery' | 'direct'
type PaymentMethod = 'cash' | 'card' | 'transfer' | 'credit'

const SALES_CHANNELS: { value: SalesChannel; label: string; description: string }[] = [
  { value: 'field', label: 'Field Sale', description: 'Agent sold in the field' },
  { value: 'store', label: 'Store Sale', description: 'Walk-in customer at store' },
  { value: 'delivery', label: 'Delivery Sale', description: 'Sale after delivery completion' },
  { value: 'direct', label: 'Direct Sale', description: 'Direct sale to customer' },
]

export default function SalesForm({ isOpen, onClose, onSuccess }: SalesFormProps) {
  const user = useAuthStore((state) => state.user)
  
  // Inventory data
  const [inventory, setInventory] = useState<InventoryItem[]>([])
  const [loadingInventory, setLoadingInventory] = useState(false)
  
  // Form state - Basic
  const [selectedProduct, setSelectedProduct] = useState<InventoryItem | null>(null)
  const [quantity, setQuantity] = useState('')
  const [unitPrice, setUnitPrice] = useState('')
  const [channel, setChannel] = useState<SalesChannel>('field')
  const [customerName, setCustomerName] = useState('')
  const [notes, setNotes] = useState('')
  
  // Form state - Forms Extension fields
  const [reference, setReference] = useState('')
  const [customerPhone, setCustomerPhone] = useState('')
  const [discount, setDiscount] = useState('')
  const [paymentMethod, setPaymentMethod] = useState<PaymentMethod | ''>('')
  const [saleDate, setSaleDate] = useState('')
  const [linkedOrderId, setLinkedOrderId] = useState('')
  const [affiliateCode, setAffiliateCode] = useState('')
  const [affiliateName, setAffiliateName] = useState('')
  const [affiliateSource, setAffiliateSource] = useState('')
  const [showAdvanced, setShowAdvanced] = useState(false)
  
  // UI state
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState<string | null>(null)
  
  // Get effective role
  const effectiveRole = user?.is_system_admin 
    ? 'admin' 
    : (user?.role || 'member')
  
  // Check if user can record sales
  const canRecordSales = !['delivery', 'customer'].includes(effectiveRole)
  
  // Fetch inventory on open
  useEffect(() => {
    if (isOpen) {
      fetchInventory()
    }
  }, [isOpen])
  
  // Reset form when closed
  useEffect(() => {
    if (!isOpen) {
      setSelectedProduct(null)
      setQuantity('')
      setUnitPrice('')
      setChannel('field')
      setCustomerName('')
      setNotes('')
      // Reset Forms Extension fields
      setReference('')
      setCustomerPhone('')
      setDiscount('')
      setPaymentMethod('')
      setSaleDate('')
      setLinkedOrderId('')
      setAffiliateCode('')
      setAffiliateName('')
      setAffiliateSource('')
      setShowAdvanced(false)
      setError(null)
      setSuccess(null)
    }
  }, [isOpen])
  
  const fetchInventory = async () => {
    setLoadingInventory(true)
    try {
      const response = await api.get('/api/inventory/')
      setInventory(response.data.items || [])
    } catch (err) {
      console.error('Failed to fetch inventory:', err)
      setError('Failed to load inventory')
    } finally {
      setLoadingInventory(false)
    }
  }
  
  const handleProductSelect = (productId: string) => {
    const product = inventory.find(i => i.id === parseInt(productId, 10))
    setSelectedProduct(product || null)
    setError(null)
  }
  
  const validateStock = (): boolean => {
    if (!selectedProduct) return false
    const qty = parseInt(quantity, 10)
    if (qty > selectedProduct.total_stock) {
      setError(`Insufficient stock. Available: ${selectedProduct.total_stock}`)
      return false
    }
    return true
  }
  
  const calculateTotal = (): number => {
    const qty = parseInt(quantity, 10) || 0
    const price = parseFloat(unitPrice) || 0
    const subtotal = qty * price
    const discountAmount = parseFloat(discount) || 0
    return Math.max(0, subtotal - discountAmount)
  }
  
  const calculateSubtotal = (): number => {
    const qty = parseInt(quantity, 10) || 0
    const price = parseFloat(unitPrice) || 0
    return qty * price
  }
  
  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    
    if (!selectedProduct || !quantity || !unitPrice) {
      setError('Please fill in all required fields')
      return
    }
    
    if (!validateStock()) {
      return
    }
    
    setLoading(true)
    setError(null)
    setSuccess(null)
    
    try {
      const payload: Record<string, unknown> = {
        product_id: selectedProduct.product_id,
        quantity: parseInt(quantity, 10),
        unit_price: parseFloat(unitPrice),
        sale_channel: channel,
        customer_name: customerName || undefined,
        notes: notes || undefined,
      }
      
      // Add Forms Extension fields (only if provided)
      if (reference) payload.reference = reference
      if (customerPhone) payload.customer_phone = customerPhone
      if (discount) payload.discount = parseFloat(discount)
      if (paymentMethod) payload.payment_method = paymentMethod
      if (saleDate) payload.sale_date = new Date(saleDate).toISOString()
      if (linkedOrderId) payload.linked_order_id = parseInt(linkedOrderId, 10)
      if (affiliateCode) payload.affiliate_code = affiliateCode
      if (affiliateName) payload.affiliate_name = affiliateName
      if (affiliateSource) payload.affiliate_source = affiliateSource
      
      const response = await api.post('/api/sales/', payload)
      
      const totalAmount = calculateTotal()
      setSuccess(`Sale #${response.data.sale_id} recorded! Total: ${totalAmount.toLocaleString()}`)
      
      // Refresh inventory to show updated stock
      fetchInventory()
      
      if (onSuccess) {
        onSuccess()
      }
      
      // Reset form for another entry
      setSelectedProduct(null)
      setQuantity('')
      setUnitPrice('')
      setCustomerName('')
      setNotes('')
      // Reset Forms Extension fields
      setReference('')
      setCustomerPhone('')
      setDiscount('')
      setPaymentMethod('')
      setSaleDate('')
      setLinkedOrderId('')
      setAffiliateCode('')
      setAffiliateName('')
      setAffiliateSource('')
      setShowAdvanced(false)
      
    } catch (err: unknown) {
      const errorMessage = err instanceof Error ? err.message : 'Failed to record sale'
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
  
  // Block restricted roles
  if (!canRecordSales) {
    return (
      <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
        <div className="bg-[#313338] rounded-lg w-full max-w-md mx-4 p-6">
          <div className="flex items-center gap-2 text-red-400 mb-4">
            <AlertCircle size={24} />
            <h2 className="text-lg font-semibold">Access Denied</h2>
          </div>
          <p className="text-[#b5bac1] mb-4">
            Your role ({effectiveRole}) does not have permission to record sales.
          </p>
          <button
            onClick={onClose}
            className="w-full bg-[#4f545c] hover:bg-[#5d6269] text-white py-2 px-4 rounded transition-colors"
          >
            Close
          </button>
        </div>
      </div>
    )
  }
  
  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
      <div className="bg-[#313338] rounded-lg w-full max-w-lg mx-4 max-h-[90vh] overflow-y-auto">
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b border-[#3f4147]">
          <div className="flex items-center gap-2">
            <DollarSign className="text-green-400" size={20} />
            <h2 className="text-lg font-semibold text-white">Record Sale</h2>
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
          <span className="text-xs bg-green-600 text-white px-2 py-1 rounded">
            Recording as: {effectiveRole}
          </span>
        </div>
        
        {/* Form */}
        <form onSubmit={handleSubmit} className="p-4 space-y-4">
          {/* Product Selector */}
          <div>
            <label className="block text-sm font-medium text-[#b5bac1] mb-1">
              Product *
            </label>
            {loadingInventory ? (
              <div className="flex items-center gap-2 text-[#949ba4] py-2">
                <Loader2 size={16} className="animate-spin" />
                Loading inventory...
              </div>
            ) : (
              <select
                value={selectedProduct?.id || ''}
                onChange={(e) => handleProductSelect(e.target.value)}
                className="w-full bg-[#1e1f22] border border-[#3f4147] rounded px-3 py-2 text-white focus:outline-none focus:border-[#5865f2]"
                required
              >
                <option value="">Select product...</option>
                {inventory.map((item) => (
                  <option key={item.id} value={item.id}>
                    {item.product_name} (Stock: {item.total_stock})
                  </option>
                ))}
              </select>
            )}
          </div>
          
          {/* Stock Info */}
          {selectedProduct && (
            <div className={`flex items-center gap-2 px-3 py-2 rounded text-sm ${
              selectedProduct.is_low_stock 
                ? 'bg-yellow-400/10 text-yellow-400' 
                : 'bg-green-400/10 text-green-400'
            }`}>
              <Package size={16} />
              <span>
                Available: {selectedProduct.total_stock} units
                {selectedProduct.is_low_stock && ' (Low Stock)'}
              </span>
            </div>
          )}
          
          {/* Quantity */}
          <div>
            <label className="block text-sm font-medium text-[#b5bac1] mb-1">
              Quantity *
            </label>
            <input
              type="number"
              value={quantity}
              onChange={(e) => {
                setQuantity(e.target.value)
                setError(null)
              }}
              placeholder="Units sold"
              min="1"
              max={selectedProduct?.total_stock || undefined}
              className="w-full bg-[#1e1f22] border border-[#3f4147] rounded px-3 py-2 text-white placeholder-[#72767d] focus:outline-none focus:border-[#5865f2]"
              required
            />
          </div>
          
          {/* Unit Price */}
          <div>
            <label className="block text-sm font-medium text-[#b5bac1] mb-1">
              Unit Price *
            </label>
            <input
              type="number"
              value={unitPrice}
              onChange={(e) => setUnitPrice(e.target.value)}
              placeholder="Price per unit"
              min="0"
              step="0.01"
              className="w-full bg-[#1e1f22] border border-[#3f4147] rounded px-3 py-2 text-white placeholder-[#72767d] focus:outline-none focus:border-[#5865f2]"
              required
            />
          </div>
          
          {/* Total Display */}
          {quantity && unitPrice && (
            <div className="bg-[#1e1f22] rounded-lg p-3 border border-[#3f4147] space-y-2">
              {discount && parseFloat(discount) > 0 && (
                <>
                  <div className="flex justify-between items-center text-sm">
                    <span className="text-[#949ba4]">Subtotal:</span>
                    <span className="text-[#b5bac1]">{calculateSubtotal().toLocaleString()}</span>
                  </div>
                  <div className="flex justify-between items-center text-sm">
                    <span className="text-[#949ba4]">Discount:</span>
                    <span className="text-orange-400">-{parseFloat(discount).toLocaleString()}</span>
                  </div>
                </>
              )}
              <div className="flex justify-between items-center">
                <span className="text-[#949ba4]">Total Amount:</span>
                <span className="text-xl font-bold text-green-400">
                  {calculateTotal().toLocaleString()}
                </span>
              </div>
            </div>
          )}
          
          {/* Discount & Payment Method Row */}
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-sm font-medium text-[#b5bac1] mb-1">
                Discount (amount)
              </label>
              <input
                type="number"
                value={discount}
                onChange={(e) => setDiscount(e.target.value)}
                placeholder="0"
                min="0"
                step="0.01"
                className="w-full bg-[#1e1f22] border border-[#3f4147] rounded px-3 py-2 text-white placeholder-[#72767d] focus:outline-none focus:border-[#5865f2]"
              />
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
          
          {/* Sales Channel */}
          <div>
            <label className="block text-sm font-medium text-[#b5bac1] mb-1">
              Sales Channel *
            </label>
            <select
              value={channel}
              onChange={(e) => setChannel(e.target.value as SalesChannel)}
              className="w-full bg-[#1e1f22] border border-[#3f4147] rounded px-3 py-2 text-white focus:outline-none focus:border-[#5865f2]"
              required
            >
              {SALES_CHANNELS.map((ch) => (
                <option key={ch.value} value={ch.value}>
                  {ch.label}
                </option>
              ))}
            </select>
            <p className="text-xs text-[#949ba4] mt-1">
              {SALES_CHANNELS.find(ch => ch.value === channel)?.description}
            </p>
          </div>
          
          {/* Customer Name (optional, shown for delivery/direct) */}
          {(channel === 'delivery' || channel === 'direct') && (
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-sm font-medium text-[#b5bac1] mb-1">
                  Customer Name
                </label>
                <input
                  type="text"
                  value={customerName}
                  onChange={(e) => setCustomerName(e.target.value)}
                  placeholder="e.g., ABC Restaurant"
                  className="w-full bg-[#1e1f22] border border-[#3f4147] rounded px-3 py-2 text-white placeholder-[#72767d] focus:outline-none focus:border-[#5865f2]"
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
                  className="w-full bg-[#1e1f22] border border-[#3f4147] rounded px-3 py-2 text-white placeholder-[#72767d] focus:outline-none focus:border-[#5865f2]"
                />
              </div>
            </div>
          )}
          
          {/* Advanced Fields Toggle */}
          <button
            type="button"
            onClick={() => setShowAdvanced(!showAdvanced)}
            className="flex items-center gap-2 text-sm text-[#949ba4] hover:text-white transition-colors w-full"
          >
            {showAdvanced ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
            {showAdvanced ? 'Hide' : 'Show'} Advanced Options (Affiliate, Date, Reference)
          </button>
          
          {/* Advanced Fields */}
          {showAdvanced && (
            <div className="space-y-4 p-3 bg-[#1e1f22] rounded-lg border border-[#3f4147]">
              {/* Sale Date & Reference */}
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-sm font-medium text-[#b5bac1] mb-1">
                    Sale Date
                  </label>
                  <input
                    type="datetime-local"
                    value={saleDate}
                    onChange={(e) => setSaleDate(e.target.value)}
                    className="w-full bg-[#2b2d31] border border-[#3f4147] rounded px-3 py-2 text-white focus:outline-none focus:border-[#5865f2]"
                  />
                  <p className="text-xs text-[#949ba4] mt-1">Override sale timestamp</p>
                </div>
                <div>
                  <label className="block text-sm font-medium text-[#b5bac1] mb-1">
                    Reference / Invoice #
                  </label>
                  <input
                    type="text"
                    value={reference}
                    onChange={(e) => setReference(e.target.value)}
                    placeholder="e.g., INV-2025-001"
                    className="w-full bg-[#2b2d31] border border-[#3f4147] rounded px-3 py-2 text-white placeholder-[#72767d] focus:outline-none focus:border-[#5865f2]"
                  />
                </div>
              </div>
              
              {/* Linked Order */}
              <div>
                <label className="block text-sm font-medium text-[#b5bac1] mb-1">
                  Linked Order ID
                </label>
                <input
                  type="number"
                  value={linkedOrderId}
                  onChange={(e) => setLinkedOrderId(e.target.value)}
                  placeholder="Order ID (if from an order)"
                  className="w-full bg-[#2b2d31] border border-[#3f4147] rounded px-3 py-2 text-white placeholder-[#72767d] focus:outline-none focus:border-[#5865f2]"
                />
              </div>
              
              {/* Affiliate Section */}
              <div className="border-t border-[#3f4147] pt-3 mt-3">
                <div className="flex items-center gap-2 mb-3">
                  <Users size={16} className="text-purple-400" />
                  <span className="text-sm font-medium text-purple-400">Affiliate Tracking</span>
                </div>
                <div className="grid grid-cols-3 gap-3">
                  <div>
                    <label className="block text-sm font-medium text-[#b5bac1] mb-1">
                      Affiliate Code
                    </label>
                    <input
                      type="text"
                      value={affiliateCode}
                      onChange={(e) => setAffiliateCode(e.target.value)}
                      placeholder="REF123"
                      className="w-full bg-[#2b2d31] border border-[#3f4147] rounded px-3 py-2 text-white placeholder-[#72767d] focus:outline-none focus:border-[#5865f2]"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-[#b5bac1] mb-1">
                      Affiliate Name
                    </label>
                    <input
                      type="text"
                      value={affiliateName}
                      onChange={(e) => setAffiliateName(e.target.value)}
                      placeholder="John Doe"
                      className="w-full bg-[#2b2d31] border border-[#3f4147] rounded px-3 py-2 text-white placeholder-[#72767d] focus:outline-none focus:border-[#5865f2]"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-[#b5bac1] mb-1">
                      Source
                    </label>
                    <select
                      value={affiliateSource}
                      onChange={(e) => setAffiliateSource(e.target.value)}
                      className="w-full bg-[#2b2d31] border border-[#3f4147] rounded px-3 py-2 text-white focus:outline-none focus:border-[#5865f2]"
                    >
                      <option value="">Select...</option>
                      <option value="referral">Referral</option>
                      <option value="influencer">Influencer</option>
                      <option value="partner">Partner</option>
                      <option value="employee">Employee</option>
                      <option value="social_media">Social Media</option>
                      <option value="other">Other</option>
                    </select>
                  </div>
                </div>
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
              onClick={onClose}
              className="flex-1 bg-[#4f545c] hover:bg-[#5d6269] text-white py-2 px-4 rounded transition-colors"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={loading || !selectedProduct || !quantity || !unitPrice}
              className="flex-1 flex items-center justify-center gap-2 bg-green-600 hover:bg-green-700 disabled:opacity-50 disabled:cursor-not-allowed text-white py-2 px-4 rounded transition-colors"
            >
              {loading ? (
                <Loader2 size={16} className="animate-spin" />
              ) : (
                <DollarSign size={16} />
              )}
              {loading ? 'Recording...' : 'Record Sale'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}
