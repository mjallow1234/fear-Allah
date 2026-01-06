/**
 * Raw Material Form Component
 * Multi-tab form for managing raw materials: Add, Adjust Stock, Consume
 */
import { useState, useEffect } from 'react'
import { useAuthStore } from '../../stores/authStore'
import { X, Package, AlertCircle, CheckCircle, Loader2, Plus, Minus } from 'lucide-react'
import api from '../../services/api'

interface RawMaterialFormProps {
  isOpen: boolean
  onClose: () => void
  onSuccess?: () => void
  initialTab?: 'add' | 'adjust' | 'consume'
  selectedMaterial?: RawMaterial | null
}

interface RawMaterial {
  id: number
  name: string
  description: string | null
  unit: string
  current_stock: number
  min_stock_level: number
  cost_per_unit: number | null
  supplier: string | null
}

type Tab = 'add' | 'adjust' | 'consume'

export default function RawMaterialForm({ 
  isOpen, 
  onClose, 
  onSuccess, 
  initialTab = 'add',
  selectedMaterial = null 
}: RawMaterialFormProps) {
  const user = useAuthStore((state) => state.user)
  
  // Tab state
  const [activeTab, setActiveTab] = useState<Tab>(initialTab)
  
  // Raw materials list (for adjust/consume)
  const [materials, setMaterials] = useState<RawMaterial[]>([])
  const [loadingMaterials, setLoadingMaterials] = useState(false)
  
  // Add Material Form
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [unit, setUnit] = useState('kg')
  const [initialStock, setInitialStock] = useState('')
  const [minStockLevel, setMinStockLevel] = useState('')
  const [costPerUnit, setCostPerUnit] = useState('')
  const [supplier, setSupplier] = useState('')
  
  // Adjust/Consume Form
  const [selectedMaterialId, setSelectedMaterialId] = useState<number | null>(null)
  const [adjustQuantity, setAdjustQuantity] = useState('')
  const [adjustReason, setAdjustReason] = useState('')
  
  // UI state
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState<string | null>(null)
  
  const isAdmin = user?.is_system_admin === true
  
  // Fetch materials when opening adjust/consume tabs
  useEffect(() => {
    if (isOpen && (activeTab === 'adjust' || activeTab === 'consume')) {
      fetchMaterials()
    }
  }, [isOpen, activeTab])
  
  // Set initial tab and selected material
  useEffect(() => {
    if (isOpen) {
      setActiveTab(initialTab)
      if (selectedMaterial) {
        setSelectedMaterialId(selectedMaterial.id)
      }
    }
  }, [isOpen, initialTab, selectedMaterial])
  
  // Reset form when closed
  useEffect(() => {
    if (!isOpen) {
      resetForm()
    }
  }, [isOpen])
  
  const resetForm = () => {
    setName('')
    setDescription('')
    setUnit('kg')
    setInitialStock('')
    setMinStockLevel('')
    setCostPerUnit('')
    setSupplier('')
    setSelectedMaterialId(null)
    setAdjustQuantity('')
    setAdjustReason('')
    setError(null)
    setSuccess(null)
  }
  
  const fetchMaterials = async () => {
    setLoadingMaterials(true)
    try {
      const response = await api.get('/api/inventory/raw-materials/')
      setMaterials(response.data.items || response.data || [])
    } catch (err) {
      console.error('Failed to fetch raw materials:', err)
      setError('Failed to load raw materials')
    } finally {
      setLoadingMaterials(false)
    }
  }
  
  const handleAddMaterial = async (e: React.FormEvent) => {
    e.preventDefault()
    
    if (!name || !unit) {
      setError('Name and unit are required')
      return
    }
    
    setLoading(true)
    setError(null)
    setSuccess(null)
    
    try {
      const payload = {
        name,
        description: description || undefined,
        unit,
        current_stock: parseFloat(initialStock) || 0,
        min_stock_level: parseFloat(minStockLevel) || 0,
        cost_per_unit: costPerUnit ? parseFloat(costPerUnit) : undefined,
        supplier: supplier || undefined,
      }
      
      await api.post('/api/inventory/raw-materials/', payload)
      setSuccess(`Raw material "${name}" added successfully!`)
      resetForm()
      
      if (onSuccess) {
        onSuccess()
      }
    } catch (err: unknown) {
      const errorMessage = err instanceof Error ? err.message : 'Failed to add raw material'
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
  
  const handleAdjustStock = async (e: React.FormEvent) => {
    e.preventDefault()
    
    if (!selectedMaterialId || !adjustQuantity) {
      setError('Please select a material and enter a quantity')
      return
    }
    
    setLoading(true)
    setError(null)
    setSuccess(null)
    
    try {
      const quantity = parseFloat(adjustQuantity)
      // For consume tab, make quantity negative
      const finalChange = activeTab === 'consume' ? -Math.abs(quantity) : quantity
      
      // Backend expects: change (int), reason (add|consume|adjust|return), notes (optional)
      const payload = {
        change: Math.round(finalChange),  // Backend expects int
        reason: activeTab === 'consume' ? 'consume' : (finalChange > 0 ? 'add' : 'adjust'),
        notes: adjustReason || undefined,
      }
      
      await api.post(`/api/inventory/raw-materials/${selectedMaterialId}/adjust`, payload)
      
      const material = materials.find(m => m.id === selectedMaterialId)
      const action = activeTab === 'consume' ? 'consumed' : (finalChange > 0 ? 'added' : 'removed')
      setSuccess(`${Math.abs(finalChange)} ${material?.unit || 'units'} ${action} successfully!`)
      
      // Refresh materials list
      fetchMaterials()
      setAdjustQuantity('')
      setAdjustReason('')
      
      if (onSuccess) {
        onSuccess()
      }
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
  
  if (!isOpen) return null
  
  // Admin check
  if (!isAdmin) {
    return (
      <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
        <div className="bg-[#313338] rounded-lg w-full max-w-md mx-4 p-6">
          <div className="flex items-center gap-2 text-red-400 mb-4">
            <AlertCircle size={24} />
            <h2 className="text-lg font-semibold">Access Denied</h2>
          </div>
          <p className="text-[#b5bac1] mb-4">
            Only system administrators can manage raw materials.
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
  
  const selectedMaterialData = materials.find(m => m.id === selectedMaterialId)
  
  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
      <div className="bg-[#313338] rounded-lg w-full max-w-lg mx-4 max-h-[90vh] overflow-y-auto">
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b border-[#3f4147]">
          <div className="flex items-center gap-2">
            <Package className="text-amber-400" size={20} />
            <h2 className="text-lg font-semibold text-white">Raw Materials</h2>
          </div>
          <button
            onClick={onClose}
            className="text-[#949ba4] hover:text-white transition-colors"
          >
            <X size={20} />
          </button>
        </div>
        
        {/* Tabs */}
        <div className="flex border-b border-[#3f4147]">
          <button
            onClick={() => { setActiveTab('add'); resetForm(); }}
            className={`flex-1 py-3 px-4 text-sm font-medium transition-colors ${
              activeTab === 'add'
                ? 'text-amber-400 border-b-2 border-amber-400'
                : 'text-[#949ba4] hover:text-white'
            }`}
          >
            <Plus size={16} className="inline mr-1" />
            Add New
          </button>
          <button
            onClick={() => { setActiveTab('adjust'); setError(null); setSuccess(null); }}
            className={`flex-1 py-3 px-4 text-sm font-medium transition-colors ${
              activeTab === 'adjust'
                ? 'text-blue-400 border-b-2 border-blue-400'
                : 'text-[#949ba4] hover:text-white'
            }`}
          >
            <Plus size={16} className="inline mr-1" />
            Adjust Stock
          </button>
          <button
            onClick={() => { setActiveTab('consume'); setError(null); setSuccess(null); }}
            className={`flex-1 py-3 px-4 text-sm font-medium transition-colors ${
              activeTab === 'consume'
                ? 'text-red-400 border-b-2 border-red-400'
                : 'text-[#949ba4] hover:text-white'
            }`}
          >
            <Minus size={16} className="inline mr-1" />
            Consume
          </button>
        </div>
        
        {/* Tab Content */}
        <div className="p-4">
          {/* Add Material Tab */}
          {activeTab === 'add' && (
            <form onSubmit={handleAddMaterial} className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-[#b5bac1] mb-1">
                  Material Name *
                </label>
                <input
                  type="text"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder="e.g., Wheat Flour"
                  className="w-full bg-[#1e1f22] border border-[#3f4147] rounded px-3 py-2 text-white placeholder-[#72767d] focus:outline-none focus:border-[#5865f2]"
                  required
                />
              </div>
              
              <div>
                <label className="block text-sm font-medium text-[#b5bac1] mb-1">
                  Description
                </label>
                <textarea
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                  placeholder="Optional description..."
                  rows={2}
                  className="w-full bg-[#1e1f22] border border-[#3f4147] rounded px-3 py-2 text-white placeholder-[#72767d] focus:outline-none focus:border-[#5865f2] resize-none"
                />
              </div>
              
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-sm font-medium text-[#b5bac1] mb-1">
                    Unit *
                  </label>
                  <select
                    value={unit}
                    onChange={(e) => setUnit(e.target.value)}
                    className="w-full bg-[#1e1f22] border border-[#3f4147] rounded px-3 py-2 text-white focus:outline-none focus:border-[#5865f2]"
                  >
                    <option value="kg">Kilograms (kg)</option>
                    <option value="g">Grams (g)</option>
                    <option value="L">Liters (L)</option>
                    <option value="mL">Milliliters (mL)</option>
                    <option value="pcs">Pieces (pcs)</option>
                    <option value="bags">Bags</option>
                    <option value="boxes">Boxes</option>
                    <option value="m">Meters (m)</option>
                    <option value="rolls">Rolls</option>
                  </select>
                </div>
                <div>
                  <label className="block text-sm font-medium text-[#b5bac1] mb-1">
                    Initial Stock
                  </label>
                  <input
                    type="number"
                    value={initialStock}
                    onChange={(e) => setInitialStock(e.target.value)}
                    placeholder="0"
                    min="0"
                    step="0.01"
                    className="w-full bg-[#1e1f22] border border-[#3f4147] rounded px-3 py-2 text-white placeholder-[#72767d] focus:outline-none focus:border-[#5865f2]"
                  />
                </div>
              </div>
              
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-sm font-medium text-[#b5bac1] mb-1">
                    Min Stock Level
                  </label>
                  <input
                    type="number"
                    value={minStockLevel}
                    onChange={(e) => setMinStockLevel(e.target.value)}
                    placeholder="Alert threshold"
                    min="0"
                    step="0.01"
                    className="w-full bg-[#1e1f22] border border-[#3f4147] rounded px-3 py-2 text-white placeholder-[#72767d] focus:outline-none focus:border-[#5865f2]"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-[#b5bac1] mb-1">
                    Cost per Unit
                  </label>
                  <input
                    type="number"
                    value={costPerUnit}
                    onChange={(e) => setCostPerUnit(e.target.value)}
                    placeholder="Price"
                    min="0"
                    step="0.01"
                    className="w-full bg-[#1e1f22] border border-[#3f4147] rounded px-3 py-2 text-white placeholder-[#72767d] focus:outline-none focus:border-[#5865f2]"
                  />
                </div>
              </div>
              
              <div>
                <label className="block text-sm font-medium text-[#b5bac1] mb-1">
                  Supplier
                </label>
                <input
                  type="text"
                  value={supplier}
                  onChange={(e) => setSupplier(e.target.value)}
                  placeholder="e.g., ABC Supplies Co."
                  className="w-full bg-[#1e1f22] border border-[#3f4147] rounded px-3 py-2 text-white placeholder-[#72767d] focus:outline-none focus:border-[#5865f2]"
                />
              </div>
              
              {/* Messages */}
              {error && (
                <div className="flex items-center gap-2 text-red-400 bg-red-400/10 rounded p-3">
                  <AlertCircle size={16} />
                  <span className="text-sm">{error}</span>
                </div>
              )}
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
                  disabled={loading || !name || !unit}
                  className="flex-1 flex items-center justify-center gap-2 bg-amber-600 hover:bg-amber-700 disabled:opacity-50 disabled:cursor-not-allowed text-white py-2 px-4 rounded transition-colors"
                >
                  {loading ? (
                    <Loader2 size={16} className="animate-spin" />
                  ) : (
                    <Plus size={16} />
                  )}
                  {loading ? 'Adding...' : 'Add Material'}
                </button>
              </div>
            </form>
          )}
          
          {/* Adjust/Consume Tab */}
          {(activeTab === 'adjust' || activeTab === 'consume') && (
            <form onSubmit={handleAdjustStock} className="space-y-4">
              {/* Material Selector */}
              <div>
                <label className="block text-sm font-medium text-[#b5bac1] mb-1">
                  Select Material *
                </label>
                {loadingMaterials ? (
                  <div className="flex items-center gap-2 text-[#949ba4] py-2">
                    <Loader2 size={16} className="animate-spin" />
                    Loading materials...
                  </div>
                ) : (
                  <select
                    value={selectedMaterialId || ''}
                    onChange={(e) => setSelectedMaterialId(parseInt(e.target.value, 10) || null)}
                    className="w-full bg-[#1e1f22] border border-[#3f4147] rounded px-3 py-2 text-white focus:outline-none focus:border-[#5865f2]"
                    required
                  >
                    <option value="">Select material...</option>
                    {materials.map((m) => (
                      <option key={m.id} value={m.id}>
                        {m.name} (Stock: {m.current_stock} {m.unit})
                      </option>
                    ))}
                  </select>
                )}
              </div>
              
              {/* Stock Info */}
              {selectedMaterialData && (
                <div className={`flex items-center gap-2 px-3 py-2 rounded text-sm ${
                  selectedMaterialData.current_stock <= selectedMaterialData.min_stock_level
                    ? 'bg-yellow-400/10 text-yellow-400'
                    : 'bg-green-400/10 text-green-400'
                }`}>
                  <Package size={16} />
                  <span>
                    Current Stock: {selectedMaterialData.current_stock} {selectedMaterialData.unit}
                    {selectedMaterialData.current_stock <= selectedMaterialData.min_stock_level && ' (Low Stock!)'}
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
                  value={adjustQuantity}
                  onChange={(e) => setAdjustQuantity(e.target.value)}
                  placeholder={activeTab === 'consume' ? 'Amount to consume' : 'Adjustment amount (+/-)'}
                  min={activeTab === 'consume' ? '0.01' : undefined}
                  step="0.01"
                  className="w-full bg-[#1e1f22] border border-[#3f4147] rounded px-3 py-2 text-white placeholder-[#72767d] focus:outline-none focus:border-[#5865f2]"
                  required
                />
                {activeTab === 'adjust' && (
                  <p className="text-xs text-[#949ba4] mt-1">
                    Use positive values to add stock, negative to remove
                  </p>
                )}
              </div>
              
              {/* Reason */}
              <div>
                <label className="block text-sm font-medium text-[#b5bac1] mb-1">
                  Reason
                </label>
                <input
                  type="text"
                  value={adjustReason}
                  onChange={(e) => setAdjustReason(e.target.value)}
                  placeholder={activeTab === 'consume' ? 'e.g., Production batch #123' : 'e.g., Received from supplier'}
                  className="w-full bg-[#1e1f22] border border-[#3f4147] rounded px-3 py-2 text-white placeholder-[#72767d] focus:outline-none focus:border-[#5865f2]"
                />
              </div>
              
              {/* Preview */}
              {selectedMaterialData && adjustQuantity && (
                <div className="bg-[#1e1f22] rounded-lg p-3 border border-[#3f4147]">
                  <div className="flex justify-between items-center text-sm">
                    <span className="text-[#949ba4]">After adjustment:</span>
                    <span className={`font-medium ${
                      activeTab === 'consume' 
                        ? 'text-red-400' 
                        : parseFloat(adjustQuantity) > 0 
                          ? 'text-green-400' 
                          : 'text-red-400'
                    }`}>
                      {(selectedMaterialData.current_stock + (activeTab === 'consume' ? -Math.abs(parseFloat(adjustQuantity)) : parseFloat(adjustQuantity))).toFixed(2)} {selectedMaterialData.unit}
                    </span>
                  </div>
                </div>
              )}
              
              {/* Messages */}
              {error && (
                <div className="flex items-center gap-2 text-red-400 bg-red-400/10 rounded p-3">
                  <AlertCircle size={16} />
                  <span className="text-sm">{error}</span>
                </div>
              )}
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
                  disabled={loading || !selectedMaterialId || !adjustQuantity}
                  className={`flex-1 flex items-center justify-center gap-2 ${
                    activeTab === 'consume'
                      ? 'bg-red-600 hover:bg-red-700'
                      : 'bg-blue-600 hover:bg-blue-700'
                  } disabled:opacity-50 disabled:cursor-not-allowed text-white py-2 px-4 rounded transition-colors`}
                >
                  {loading ? (
                    <Loader2 size={16} className="animate-spin" />
                  ) : activeTab === 'consume' ? (
                    <Minus size={16} />
                  ) : (
                    <Plus size={16} />
                  )}
                  {loading 
                    ? 'Processing...' 
                    : activeTab === 'consume' 
                      ? 'Consume Material' 
                      : 'Adjust Stock'}
                </button>
              </div>
            </form>
          )}
        </div>
      </div>
    </div>
  )
}
