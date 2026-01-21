/**
 * Inventory Form Component
 * Admin/storekeeper only - create/update products, adjust stock and thresholds.
 */
import { useState, useEffect } from 'react'
import { useAuthStore } from '../../stores/authStore'
import { X, Package, AlertCircle, CheckCircle, Loader2, Plus, Minus, Settings } from 'lucide-react'
import api from '../../services/api'

interface InventoryFormProps {
  isOpen: boolean
  onClose: () => void
  onSuccess?: () => void
  editItem?: InventoryItem | null  // If provided, edit mode
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

type FormMode = 'create' | 'adjust' | 'threshold'

export default function InventoryForm({ isOpen, onClose, onSuccess, editItem }: InventoryFormProps) {
  const user = useAuthStore((state) => state.user)
  // Operational admin (operational_role_name === 'admin') may manage inventory; system admins keep system console privileges only
  const isAdmin = user?.operational_role_name === 'admin'
  
  // Form mode
  const [mode, setMode] = useState<FormMode>('create')
  
  // Inventory list for adjust/threshold modes
  const [inventory, setInventory] = useState<InventoryItem[]>([])
  const [loadingInventory, setLoadingInventory] = useState(false)
  
  // Create mode fields
  const [productId, setProductId] = useState('')
  const [productName, setProductName] = useState('')
  const [initialStock, setInitialStock] = useState('')
  const [lowStockThreshold, setLowStockThreshold] = useState('10')
  
  // Adjust mode fields
  const [selectedItem, setSelectedItem] = useState<InventoryItem | null>(null)
  const [adjustAmount, setAdjustAmount] = useState('')
  const [adjustType, setAdjustType] = useState<'add' | 'remove'>('add')
  const [adjustReason, setAdjustReason] = useState('')
  
  // Threshold mode fields
  const [newThreshold, setNewThreshold] = useState('')
  
  // UI state
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState<string | null>(null)
  
  // Get effective role
  const effectiveRole = isAdmin ? 'admin' : (user?.role || 'member')
  
  // Only system administrators may manage inventory (UI-level gating). Backend still enforces ACLs.
  const canManageInventory = isAdmin
  
  // Fetch inventory on open
  useEffect(() => {
    if (isOpen && (mode === 'adjust' || mode === 'threshold')) {
      fetchInventory()
    }
  }, [isOpen, mode])
  
  // Set edit item if provided
  useEffect(() => {
    if (editItem) {
      setMode('adjust')
      setSelectedItem(editItem)
    }
  }, [editItem])
  
  // Reset form when closed
  useEffect(() => {
    if (!isOpen) {
      setMode('create')
      setProductId('')
      setProductName('')
      setInitialStock('')
      setLowStockThreshold('10')
      setSelectedItem(null)
      setAdjustAmount('')
      setAdjustType('add')
      setAdjustReason('')
      setNewThreshold('')
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
  
  const handleCreateProduct = async () => {
    if (!productName || !initialStock) {
      setError('Please fill in product name and initial stock')
      return
    }
    
    setLoading(true)
    setError(null)
    setSuccess(null)
    
    try {
      // Generate product_id from name if not provided
      const pid = productId || Date.now()
      
      await api.post('/api/inventory/', {
        product_id: parseInt(String(pid), 10),
        product_name: productName,
        initial_stock: parseInt(initialStock, 10),
        low_stock_threshold: parseInt(lowStockThreshold, 10),
      })
      
      setSuccess(`Product "${productName}" created with ${initialStock} units`)
      
      // Reset create fields
      setProductId('')
      setProductName('')
      setInitialStock('')
      setLowStockThreshold('10')
      
      if (onSuccess) onSuccess()
    } catch (err: unknown) {
      const errorMessage = err instanceof Error ? err.message : 'Failed to create product'
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
  
  const handleAdjustStock = async () => {
    if (!selectedItem || !adjustAmount || !adjustReason) {
      setError('Please select item, enter amount, and provide reason')
      return
    }
    
    const amount = parseInt(adjustAmount, 10)
    if (adjustType === 'remove' && amount > selectedItem.total_stock) {
      setError(`Cannot remove ${amount} units. Only ${selectedItem.total_stock} available.`)
      return
    }
    
    setLoading(true)
    setError(null)
    setSuccess(null)
    
    try {
      const finalAmount = adjustType === 'add' ? amount : -amount
      
      await api.post(`/api/inventory/product/${selectedItem.product_id}/adjust`, {
        adjustment: finalAmount,
        reason: 'adjustment',
        notes: adjustReason,
      })
      
      const newStock = selectedItem.total_stock + finalAmount
      setSuccess(`Stock ${adjustType === 'add' ? 'increased' : 'decreased'} by ${amount}. New stock: ${newStock}`)
      
      // Refresh inventory
      fetchInventory()
      
      // Reset adjust fields
      setSelectedItem(null)
      setAdjustAmount('')
      setAdjustReason('')
      
      if (onSuccess) onSuccess()
    } catch (err: unknown) {
      const errorMessage = err instanceof Error ? err.message : 'Failed to adjust stock'
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
  
  const handleUpdateThreshold = async () => {
    if (!selectedItem || !newThreshold) {
      setError('Please select item and enter new threshold')
      return
    }
    
    setLoading(true)
    setError(null)
    setSuccess(null)
    
    try {
      await api.put(`/api/inventory/product/${selectedItem.product_id}/threshold`, {
        threshold: parseInt(newThreshold, 10),
      })
      
      setSuccess(`Threshold updated to ${newThreshold} for "${selectedItem.product_name}"`)
      
      // Refresh inventory
      fetchInventory()
      
      // Reset threshold fields
      setSelectedItem(null)
      setNewThreshold('')
      
      if (onSuccess) onSuccess()
    } catch (err: unknown) {
      const errorMessage = err instanceof Error ? err.message : 'Failed to update threshold'
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
  
  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    
    switch (mode) {
      case 'create':
        await handleCreateProduct()
        break
      case 'adjust':
        await handleAdjustStock()
        break
      case 'threshold':
        await handleUpdateThreshold()
        break
    }
  }
  
  if (!isOpen) return null
  
  // Block restricted roles
  if (!canManageInventory) {
    return (
      <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
        <div className="bg-[#313338] rounded-lg w-full max-w-md mx-4 p-6">
          <div className="flex items-center gap-2 text-red-400 mb-4">
            <AlertCircle size={24} />
            <h2 className="text-lg font-semibold">Access Denied</h2>
          </div>
          <p className="text-[#b5bac1] mb-4">
            Your role ({effectiveRole}) does not have permission to manage inventory.
            Only Admin and Storekeeper roles can access this feature.
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
            <Package className="text-blue-400" size={20} />
            <h2 className="text-lg font-semibold text-white">Manage Inventory</h2>
          </div>
          <button
            onClick={onClose}
            className="text-[#949ba4] hover:text-white transition-colors"
          >
            <X size={20} />
          </button>
        </div>
        
        {/* Mode Tabs */}
        <div className="flex border-b border-[#3f4147]">
          <button
            onClick={() => { setMode('create'); setError(null); setSuccess(null); }}
            className={`flex-1 py-3 px-4 text-sm font-medium transition-colors ${
              mode === 'create'
                ? 'text-[#5865f2] border-b-2 border-[#5865f2]'
                : 'text-[#949ba4] hover:text-white'
            }`}
          >
            <Plus size={14} className="inline mr-1" />
            Create Product
          </button>
          <button
            onClick={() => { setMode('adjust'); setError(null); setSuccess(null); }}
            className={`flex-1 py-3 px-4 text-sm font-medium transition-colors ${
              mode === 'adjust'
                ? 'text-[#5865f2] border-b-2 border-[#5865f2]'
                : 'text-[#949ba4] hover:text-white'
            }`}
          >
            <Package size={14} className="inline mr-1" />
            Adjust Stock
          </button>
          <button
            onClick={() => { setMode('threshold'); setError(null); setSuccess(null); }}
            className={`flex-1 py-3 px-4 text-sm font-medium transition-colors ${
              mode === 'threshold'
                ? 'text-[#5865f2] border-b-2 border-[#5865f2]'
                : 'text-[#949ba4] hover:text-white'
            }`}
          >
            <Settings size={14} className="inline mr-1" />
            Threshold
          </button>
        </div>
        
        {/* Form */}
        <form onSubmit={handleSubmit} className="p-4 space-y-4">
          {/* CREATE MODE */}
          {mode === 'create' && (
            <>
              <div>
                <label className="block text-sm font-medium text-[#b5bac1] mb-1">
                  Product ID (optional)
                </label>
                <input
                  type="number"
                  value={productId}
                  onChange={(e) => setProductId(e.target.value)}
                  placeholder="Auto-generated if empty"
                  className="w-full bg-[#1e1f22] border border-[#3f4147] rounded px-3 py-2 text-white placeholder-[#72767d] focus:outline-none focus:border-[#5865f2]"
                />
              </div>
              
              <div>
                <label className="block text-sm font-medium text-[#b5bac1] mb-1">
                  Product Name *
                </label>
                <input
                  type="text"
                  value={productName}
                  onChange={(e) => setProductName(e.target.value)}
                  placeholder="e.g., Cement Bag 25kg"
                  className="w-full bg-[#1e1f22] border border-[#3f4147] rounded px-3 py-2 text-white placeholder-[#72767d] focus:outline-none focus:border-[#5865f2]"
                  required
                />
              </div>
              
              <div>
                <label className="block text-sm font-medium text-[#b5bac1] mb-1">
                  Initial Stock *
                </label>
                <input
                  type="number"
                  value={initialStock}
                  onChange={(e) => setInitialStock(e.target.value)}
                  placeholder="Starting quantity"
                  min="0"
                  className="w-full bg-[#1e1f22] border border-[#3f4147] rounded px-3 py-2 text-white placeholder-[#72767d] focus:outline-none focus:border-[#5865f2]"
                  required
                />
              </div>
              
              <div>
                <label className="block text-sm font-medium text-[#b5bac1] mb-1">
                  Low Stock Threshold
                </label>
                <input
                  type="number"
                  value={lowStockThreshold}
                  onChange={(e) => setLowStockThreshold(e.target.value)}
                  placeholder="Alert when below this"
                  min="0"
                  className="w-full bg-[#1e1f22] border border-[#3f4147] rounded px-3 py-2 text-white placeholder-[#72767d] focus:outline-none focus:border-[#5865f2]"
                />
                <p className="text-xs text-[#949ba4] mt-1">
                  You'll be alerted when stock falls below this level
                </p>
              </div>
            </>
          )}
          
          {/* ADJUST MODE */}
          {mode === 'adjust' && (
            <>
              <div>
                <label className="block text-sm font-medium text-[#b5bac1] mb-1">
                  Select Product *
                </label>
                {loadingInventory ? (
                  <div className="flex items-center gap-2 text-[#949ba4] py-2">
                    <Loader2 size={16} className="animate-spin" />
                    Loading inventory...
                  </div>
                ) : (
                  <select
                    value={selectedItem?.id || ''}
                    onChange={(e) => {
                      const item = inventory.find(i => i.id === parseInt(e.target.value, 10))
                      setSelectedItem(item || null)
                    }}
                    className="w-full bg-[#1e1f22] border border-[#3f4147] rounded px-3 py-2 text-white focus:outline-none focus:border-[#5865f2]"
                    required
                  >
                    <option value="">Select product...</option>
                    {inventory.map((item) => (
                      <option key={item.id} value={item.id}>
                        {item.product_name} (Current: {item.total_stock})
                      </option>
                    ))}
                  </select>
                )}
              </div>
              
              {selectedItem && (
                <div className="bg-[#1e1f22] rounded-lg p-3 border border-[#3f4147]">
                  <div className="grid grid-cols-2 gap-2 text-sm">
                    <div>
                      <span className="text-[#949ba4]">Current Stock:</span>
                      <span className="text-white ml-2">{selectedItem.total_stock}</span>
                    </div>
                    <div>
                      <span className="text-[#949ba4]">Total Sold:</span>
                      <span className="text-white ml-2">{selectedItem.total_sold}</span>
                    </div>
                  </div>
                </div>
              )}
              
              <div>
                <label className="block text-sm font-medium text-[#b5bac1] mb-1">
                  Adjustment Type *
                </label>
                <div className="flex gap-2">
                  <button
                    type="button"
                    onClick={() => setAdjustType('add')}
                    className={`flex-1 flex items-center justify-center gap-2 py-2 px-4 rounded transition-colors ${
                      adjustType === 'add'
                        ? 'bg-green-600 text-white'
                        : 'bg-[#1e1f22] text-[#949ba4] hover:text-white'
                    }`}
                  >
                    <Plus size={16} />
                    Add Stock
                  </button>
                  <button
                    type="button"
                    onClick={() => setAdjustType('remove')}
                    className={`flex-1 flex items-center justify-center gap-2 py-2 px-4 rounded transition-colors ${
                      adjustType === 'remove'
                        ? 'bg-red-600 text-white'
                        : 'bg-[#1e1f22] text-[#949ba4] hover:text-white'
                    }`}
                  >
                    <Minus size={16} />
                    Remove Stock
                  </button>
                </div>
              </div>
              
              <div>
                <label className="block text-sm font-medium text-[#b5bac1] mb-1">
                  Amount *
                </label>
                <input
                  type="number"
                  value={adjustAmount}
                  onChange={(e) => setAdjustAmount(e.target.value)}
                  placeholder="Quantity to adjust"
                  min="1"
                  className="w-full bg-[#1e1f22] border border-[#3f4147] rounded px-3 py-2 text-white placeholder-[#72767d] focus:outline-none focus:border-[#5865f2]"
                  required
                />
              </div>
              
              <div>
                <label className="block text-sm font-medium text-[#b5bac1] mb-1">
                  Reason *
                </label>
                <input
                  type="text"
                  value={adjustReason}
                  onChange={(e) => setAdjustReason(e.target.value)}
                  placeholder="e.g., Restock delivery, Damaged goods, Inventory count"
                  className="w-full bg-[#1e1f22] border border-[#3f4147] rounded px-3 py-2 text-white placeholder-[#72767d] focus:outline-none focus:border-[#5865f2]"
                  required
                />
              </div>
            </>
          )}
          
          {/* THRESHOLD MODE */}
          {mode === 'threshold' && (
            <>
              <div>
                <label className="block text-sm font-medium text-[#b5bac1] mb-1">
                  Select Product *
                </label>
                {loadingInventory ? (
                  <div className="flex items-center gap-2 text-[#949ba4] py-2">
                    <Loader2 size={16} className="animate-spin" />
                    Loading inventory...
                  </div>
                ) : (
                  <select
                    value={selectedItem?.id || ''}
                    onChange={(e) => {
                      const item = inventory.find(i => i.id === parseInt(e.target.value, 10))
                      setSelectedItem(item || null)
                      if (item) setNewThreshold(String(item.low_stock_threshold))
                    }}
                    className="w-full bg-[#1e1f22] border border-[#3f4147] rounded px-3 py-2 text-white focus:outline-none focus:border-[#5865f2]"
                    required
                  >
                    <option value="">Select product...</option>
                    {inventory.map((item) => (
                      <option key={item.id} value={item.id}>
                        {item.product_name} (Threshold: {item.low_stock_threshold})
                      </option>
                    ))}
                  </select>
                )}
              </div>
              
              {selectedItem && (
                <div className="bg-[#1e1f22] rounded-lg p-3 border border-[#3f4147]">
                  <div className="grid grid-cols-2 gap-2 text-sm">
                    <div>
                      <span className="text-[#949ba4]">Current Stock:</span>
                      <span className="text-white ml-2">{selectedItem.total_stock}</span>
                    </div>
                    <div>
                      <span className="text-[#949ba4]">Current Threshold:</span>
                      <span className="text-white ml-2">{selectedItem.low_stock_threshold}</span>
                    </div>
                  </div>
                </div>
              )}
              
              <div>
                <label className="block text-sm font-medium text-[#b5bac1] mb-1">
                  New Low Stock Threshold *
                </label>
                <input
                  type="number"
                  value={newThreshold}
                  onChange={(e) => setNewThreshold(e.target.value)}
                  placeholder="New threshold value"
                  min="0"
                  className="w-full bg-[#1e1f22] border border-[#3f4147] rounded px-3 py-2 text-white placeholder-[#72767d] focus:outline-none focus:border-[#5865f2]"
                  required
                />
                <p className="text-xs text-[#949ba4] mt-1">
                  Alert will trigger when stock falls at or below this level
                </p>
              </div>
            </>
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
              onClick={onClose}
              className="flex-1 bg-[#4f545c] hover:bg-[#5d6269] text-white py-2 px-4 rounded transition-colors"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={loading}
              className="flex-1 flex items-center justify-center gap-2 bg-[#5865f2] hover:bg-[#4752c4] disabled:opacity-50 disabled:cursor-not-allowed text-white py-2 px-4 rounded transition-colors"
            >
              {loading ? (
                <Loader2 size={16} className="animate-spin" />
              ) : (
                <Package size={16} />
              )}
              {loading ? 'Saving...' : (
                mode === 'create' ? 'Create Product' :
                mode === 'adjust' ? 'Adjust Stock' :
                'Update Threshold'
              )}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}
