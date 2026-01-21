import { X, Boxes, BarChart3, TrendingDown, TrendingUp, Building2, Pencil, Minus, Trash } from 'lucide-react'
import { useEffect, useState, useCallback } from 'react'
import clsx from 'clsx'
import api from '../services/api'
import { extractAxiosError } from '../utils/errorUtils'

interface RawMaterialDetail {
  id: number
  name: string
  description: string | null
  unit: string
  current_stock: number
  min_stock_level: number
  cost_per_unit: number | null
  supplier: string | null
  is_low_stock: boolean
  total_used: number
  total_added: number
  transaction_count: number
  created_at: string | null
  updated_at: string | null
}

interface RawMaterialDetailsDrawerProps {
  materialId: number | null
  isOpen: boolean
  onClose: () => void
  isAdmin?: boolean
  onEdit?: (id: number) => void
  onAdjust?: (id: number) => void
  onDelete?: (id: number) => void
}

export default function RawMaterialDetailsDrawer({ materialId, isOpen, onClose, isAdmin, onEdit, onAdjust, onDelete }: RawMaterialDetailsDrawerProps) {
  const [material, setMaterial] = useState<RawMaterialDetail | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // Reset state when drawer closes
  useEffect(() => {
    if (!isOpen) {
      setMaterial(null)
      setError(null)
      setLoading(false)
    }
  }, [isOpen])

  const fetchMaterialDetails = useCallback(async (id: number) => {
    setLoading(true)
    setError(null)
    
    try {
      const response = await api.get(`/api/inventory/raw-materials/${id}`)
      setMaterial(response.data)
    } catch (err: unknown) {
      // Graceful error handling - don't crash the UI
      console.error('[RawMaterialDetailsDrawer] Fetch error:', err)
      if (err && typeof err === 'object' && 'response' in err) {
        const axiosErr = err as { response?: { status?: number; data?: { detail?: unknown } } }
        if (axiosErr.response?.status === 404) {
          setError('Raw material not found')
        } else {
          setError(extractAxiosError(err, 'Failed to fetch material details'))
        }
      } else {
        setError('Network error - please try again')
      }
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    // Guard: Do nothing if drawer is closed or materialId is invalid
    if (!isOpen || materialId == null) return
    fetchMaterialDetails(materialId)
  }, [isOpen, materialId, fetchMaterialDetails])

  const getStockStatus = (stock: number, threshold: number) => {
    if (stock <= 0) return { label: 'Out of Stock', color: 'text-red-400', bg: 'bg-red-500/10' }
    if (stock <= threshold) return { label: 'Low Stock', color: 'text-yellow-400', bg: 'bg-yellow-500/10' }
    return { label: 'In Stock', color: 'text-green-400', bg: 'bg-green-500/10' }
  }

  if (!isOpen) return null

  const status = material ? getStockStatus(material.current_stock, material.min_stock_level) : null

  return (
    <>
      {/* Backdrop */}
      <div 
        className="fixed inset-0 bg-black/50 z-40 transition-opacity"
        onClick={onClose}
      />
      
      {/* Drawer */}
      <div className="fixed right-0 top-0 h-full w-96 bg-[#2b2d31] shadow-xl z-50 transform transition-transform overflow-y-auto">
        {/* Header */}
        <div className="sticky top-0 bg-[#2b2d31] border-b border-[#1f2023] px-4 py-3 flex items-center justify-between">
          <h2 className="text-lg font-semibold text-white flex items-center gap-2">
            <Boxes size={20} className="text-amber-400" />
            Raw Material Details
          </h2>
          <div className="flex items-center gap-2">
            {isAdmin && onEdit && (
              <button
                onClick={() => onEdit(materialId as number)}
                className="px-3 py-1.5 text-sm bg-[#4f545c] hover:bg-[#5d6269] text-white rounded transition-colors"
                title="Edit"
              >
                <Pencil size={14} />
              </button>
            )}
            {isAdmin && onAdjust && (
              <button
                onClick={() => onAdjust(materialId as number)}
                className="px-3 py-1.5 text-sm bg-[#4f545c] hover:bg-[#5d6269] text-white rounded transition-colors"
                title="Adjust"
              >
                <Minus size={14} />
              </button>
            )}
            {isAdmin && onDelete && (
              <button
                onClick={() => onDelete(materialId as number)}
                className="px-3 py-1.5 text-sm bg-red-600 hover:bg-red-700 text-white rounded transition-colors"
                title="Delete"
              >
                <Trash size={14} />
              </button>
            )}
            <button
              onClick={onClose}
              className="p-1 text-[#949ba4] hover:text-white transition-colors rounded"
            >
              <X size={20} />
            </button>
          </div>
        </div>
        
        {/* Content */}
        <div className="p-4">
          {loading && (
            <div className="flex items-center justify-center py-12">
              <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-amber-500" />
            </div>
          )}
          
          {error && (
            <div className="bg-red-500/10 border border-red-500/20 rounded-lg p-4 text-red-400">
              <p>{error}</p>
            </div>
          )}
          
          {material && !loading && (
            <div className="space-y-6">
              {/* Material Name & Status */}
              <div>
                <h3 className="text-xl font-semibold text-white mb-2">
                  {material.name}
                </h3>
                {status && (
                  <span className={clsx('px-2 py-1 rounded text-xs font-medium', status.bg, status.color)}>
                    {status.label}
                  </span>
                )}
              </div>
              
              {/* Description */}
              {material.description && (
                <p className="text-sm text-[#b5bac1]">{material.description}</p>
              )}
              
              {/* Stock Overview */}
              <div className="bg-[#1e1f22] rounded-lg p-4">
                <h4 className="text-sm font-medium text-[#949ba4] mb-3 flex items-center gap-2">
                  <BarChart3 size={16} />
                  Stock Overview
                </h4>
                
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <p className="text-2xl font-bold text-white">{material.current_stock}</p>
                    <p className="text-xs text-[#949ba4]">Current Stock ({material.unit})</p>
                  </div>
                  <div>
                    <p className="text-2xl font-bold text-yellow-400">{material.min_stock_level}</p>
                    <p className="text-xs text-[#949ba4]">Min Level ({material.unit})</p>
                  </div>
                </div>
                
                {/* Stock Progress Bar */}
                <div className="mt-4">
                  <div className="flex justify-between text-xs text-[#949ba4] mb-1">
                    <span>Stock Level</span>
                    <span>{material.current_stock} / {material.min_stock_level} (min)</span>
                  </div>
                  <div className="h-2 bg-[#35373c] rounded-full overflow-hidden">
                    <div 
                      className={clsx(
                        'h-full transition-all',
                        material.current_stock <= 0 ? 'bg-red-500' :
                        material.current_stock <= material.min_stock_level ? 'bg-yellow-500' : 'bg-green-500'
                      )}
                      style={{ 
                        width: `${Math.min(100, (material.current_stock / Math.max(material.min_stock_level * 3, 100)) * 100)}%` 
                      }}
                    />
                  </div>
                </div>
              </div>
              
              {/* Usage Statistics */}
              <div className="bg-[#1e1f22] rounded-lg p-4">
                <h4 className="text-sm font-medium text-[#949ba4] mb-3 flex items-center gap-2">
                  <TrendingDown size={16} className="text-red-400" />
                  Usage Statistics
                </h4>
                
                <div className="grid grid-cols-3 gap-4">
                  <div>
                    <div className="flex items-center gap-1">
                      <TrendingUp size={14} className="text-green-400" />
                      <p className="text-lg font-bold text-green-400">{material.total_added}</p>
                    </div>
                    <p className="text-xs text-[#949ba4]">Total Added</p>
                  </div>
                  <div>
                    <div className="flex items-center gap-1">
                      <TrendingDown size={14} className="text-red-400" />
                      <p className="text-lg font-bold text-red-400">{material.total_used}</p>
                    </div>
                    <p className="text-xs text-[#949ba4]">Total Used</p>
                  </div>
                  <div>
                    <p className="text-lg font-bold text-[#5865f2]">{material.transaction_count}</p>
                    <p className="text-xs text-[#949ba4]">Transactions</p>
                  </div>
                </div>
              </div>
              
              {/* Cost & Supplier */}
              {(material.cost_per_unit || material.supplier) && (
                <div className="bg-[#1e1f22] rounded-lg p-4">
                  <h4 className="text-sm font-medium text-[#949ba4] mb-3 flex items-center gap-2">
                    <Building2 size={16} />
                    Supplier Info
                  </h4>
                  
                  <div className="space-y-2 text-sm">
                    {material.cost_per_unit != null && (
                      <div className="flex justify-between">
                        <span className="text-[#949ba4]">Cost per Unit</span>
                        <span className="text-white font-medium">
                          D {material.cost_per_unit.toLocaleString()} / {material.unit}
                        </span>
                      </div>
                    )}
                    {material.supplier && (
                      <div className="flex justify-between">
                        <span className="text-[#949ba4]">Supplier</span>
                        <span className="text-white">{material.supplier}</span>
                      </div>
                    )}
                  </div>
                </div>
              )}
              
              {/* Additional Info */}
              <div className="bg-[#1e1f22] rounded-lg p-4">
                <h4 className="text-sm font-medium text-[#949ba4] mb-3">Details</h4>
                
                <div className="space-y-2 text-sm">
                  <div className="flex justify-between">
                    <span className="text-[#949ba4]">Material ID</span>
                    <span className="text-white font-mono">{material.id}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-[#949ba4]">Unit</span>
                    <span className="text-white">{material.unit}</span>
                  </div>
                </div>
              </div>
              
              {/* Timestamps */}
              {(material.created_at || material.updated_at) && (
                <div className="text-xs text-[#949ba4] space-y-1">
                  {material.created_at && (
                    <p>Created: {new Date(material.created_at).toLocaleString()}</p>
                  )}
                  {material.updated_at && (
                    <p>Updated: {new Date(material.updated_at).toLocaleString()}</p>
                  )}
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </>
  )
}
