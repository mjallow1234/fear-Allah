import { X, Package, TrendingUp, BarChart3 } from 'lucide-react'
import { useEffect, useState, useCallback } from 'react'
import clsx from 'clsx'
import api from '../services/api'
import { extractAxiosError } from '../utils/errorUtils'

interface ProductDetail {
  id: number
  product_id: number
  product_name: string
  total_stock: number
  total_sold: number
  low_stock_threshold: number
  unit_price?: number
  cost_price?: number
  category?: string
  description?: string
  created_at?: string
  updated_at?: string
}

interface ProductDetailsDrawerProps {
  productId: number | null
  isOpen: boolean
  onClose: () => void
}

export default function ProductDetailsDrawer({ productId, isOpen, onClose }: ProductDetailsDrawerProps) {
  const [product, setProduct] = useState<ProductDetail | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // Reset state when drawer closes
  useEffect(() => {
    if (!isOpen) {
      setProduct(null)
      setError(null)
      setLoading(false)
    }
  }, [isOpen])

  const fetchProductDetails = useCallback(async (id: number) => {
    setLoading(true)
    setError(null)
    
    try {
      const response = await api.get(`/api/inventory/product/${id}`)
      setProduct(response.data)
    } catch (err: unknown) {
      // Graceful error handling - don't crash the UI
      console.error('[ProductDetailsDrawer] Fetch error:', err)
      if (err && typeof err === 'object' && 'response' in err) {
        const axiosErr = err as { response?: { status?: number; data?: { detail?: unknown } } }
        if (axiosErr.response?.status === 404) {
          setError('Product not found')
        } else {
          setError(extractAxiosError(err, 'Failed to fetch product details'))
        }
      } else {
        setError('Network error - please try again')
      }
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    // Guard: Do nothing if drawer is closed or productId is invalid
    if (!isOpen || productId == null) return
    fetchProductDetails(productId)
  }, [isOpen, productId, fetchProductDetails])

  const getStockStatus = (stock: number, threshold: number) => {
    if (stock <= 0) return { label: 'Out of Stock', color: 'text-red-400', bg: 'bg-red-500/10' }
    if (stock <= threshold) return { label: 'Low Stock', color: 'text-yellow-400', bg: 'bg-yellow-500/10' }
    return { label: 'In Stock', color: 'text-green-400', bg: 'bg-green-500/10' }
  }

  if (!isOpen) return null

  const status = product ? getStockStatus(product.total_stock, product.low_stock_threshold) : null

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
            <Package size={20} />
            Product Details
          </h2>
          <button
            onClick={onClose}
            className="p-1 text-[#949ba4] hover:text-white transition-colors rounded"
          >
            <X size={20} />
          </button>
        </div>
        
        {/* Content */}
        <div className="p-4">
          {loading && (
            <div className="flex items-center justify-center py-12">
              <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-[#5865f2]" />
            </div>
          )}
          
          {error && (
            <div className="bg-red-500/10 border border-red-500/20 rounded-lg p-4 text-red-400">
              <p>{error}</p>
            </div>
          )}
          
          {product && !loading && (
            <div className="space-y-6">
              {/* Product Name & Status */}
              <div>
                <h3 className="text-xl font-semibold text-white mb-2">
                  {product.product_name}
                </h3>
                {status && (
                  <span className={clsx('px-2 py-1 rounded text-xs font-medium', status.bg, status.color)}>
                    {status.label}
                  </span>
                )}
              </div>
              
              {/* Stock Overview */}
              <div className="bg-[#1e1f22] rounded-lg p-4">
                <h4 className="text-sm font-medium text-[#949ba4] mb-3 flex items-center gap-2">
                  <BarChart3 size={16} />
                  Stock Overview
                </h4>
                
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <p className="text-2xl font-bold text-white">{product.total_stock}</p>
                    <p className="text-xs text-[#949ba4]">Current Stock</p>
                  </div>
                  <div>
                    <p className="text-2xl font-bold text-[#5865f2]">{product.total_sold || 0}</p>
                    <p className="text-xs text-[#949ba4]">Total Sold</p>
                  </div>
                </div>
                
                {/* Stock Progress Bar */}
                <div className="mt-4">
                  <div className="flex justify-between text-xs text-[#949ba4] mb-1">
                    <span>Stock Level</span>
                    <span>{product.total_stock} / {product.low_stock_threshold} (threshold)</span>
                  </div>
                  <div className="h-2 bg-[#35373c] rounded-full overflow-hidden">
                    <div 
                      className={clsx(
                        'h-full transition-all',
                        product.total_stock <= 0 ? 'bg-red-500' :
                        product.total_stock <= product.low_stock_threshold ? 'bg-yellow-500' : 'bg-green-500'
                      )}
                      style={{ 
                        width: `${Math.min(100, (product.total_stock / Math.max(product.low_stock_threshold * 3, 100)) * 100)}%` 
                      }}
                    />
                  </div>
                </div>
              </div>
              
              {/* Pricing (if available) */}
              {(product.unit_price || product.cost_price) && (
                <div className="bg-[#1e1f22] rounded-lg p-4">
                  <h4 className="text-sm font-medium text-[#949ba4] mb-3 flex items-center gap-2">
                    <TrendingUp size={16} />
                    Pricing
                  </h4>
                  
                  <div className="grid grid-cols-2 gap-4">
                    {product.unit_price && (
                      <div>
                        <p className="text-xl font-bold text-white">${product.unit_price.toFixed(2)}</p>
                        <p className="text-xs text-[#949ba4]">Unit Price</p>
                      </div>
                    )}
                    {product.cost_price && (
                      <div>
                        <p className="text-xl font-bold text-[#949ba4]">${product.cost_price.toFixed(2)}</p>
                        <p className="text-xs text-[#949ba4]">Cost Price</p>
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
                    <span className="text-[#949ba4]">Product ID</span>
                    <span className="text-white font-mono">{product.product_id}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-[#949ba4]">Low Stock Alert</span>
                    <span className="text-white">{product.low_stock_threshold} units</span>
                  </div>
                  {product.category && (
                    <div className="flex justify-between">
                      <span className="text-[#949ba4]">Category</span>
                      <span className="text-white">{product.category}</span>
                    </div>
                  )}
                </div>
                
                {product.description && (
                  <div className="mt-4 pt-4 border-t border-[#35373c]">
                    <p className="text-xs text-[#949ba4] mb-1">Description</p>
                    <p className="text-sm text-white">{product.description}</p>
                  </div>
                )}
              </div>
              
              {/* Timestamps */}
              {(product.created_at || product.updated_at) && (
                <div className="text-xs text-[#949ba4] space-y-1">
                  {product.created_at && (
                    <p>Created: {new Date(product.created_at).toLocaleString()}</p>
                  )}
                  {product.updated_at && (
                    <p>Updated: {new Date(product.updated_at).toLocaleString()}</p>
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
