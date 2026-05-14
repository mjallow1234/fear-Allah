/**
 * ConvertToSaleModal
 * Converts an order into one or more sales via POST /api/orders/{id}/record-sales.
 * Pre-fills items from the order's fulfill payload; user enters unit prices.
 * Idempotent — the backend prevents duplicate sales via idempotency keys.
 */
import { useState, useEffect } from 'react'
import { X, Loader2, ShoppingCart, AlertCircle, CheckCircle, Plus, Trash2 } from 'lucide-react'
import api from '../services/api'
import { useOrderStore } from '../stores/orderStore'
import { useSalesStore } from '../stores/salesStore'
import { useInventoryStore } from '../stores/inventoryStore'
import { useNotificationContext } from '../contexts/NotificationProvider'
import { useTaskStore } from '../stores/taskStore'

interface LineItem {
  product_id: string
  product_name: string
  quantity: string
  unit_price: string
  available_stock: number | null
}

interface FulfillPayload {
  order_id: number
  order_type: string
  order_status: string
  sale_channel: string
  customer_name: string | null
  customer_phone: string | null
  reference: string | null
  payment_method: string | null
  items: Array<{
    product_id: number
    product_name: string
    quantity: number
    available_stock: number | null
    unit_price: number | null
  }>
}

interface Props {
  orderId: number
  open: boolean
  onClose: () => void
  onSuccess?: () => void
}

export default function ConvertToSaleModal({ orderId, open, onClose, onSuccess }: Props) {
  const [payload, setPayload] = useState<FulfillPayload | null>(null)
  const [items, setItems] = useState<LineItem[]>([])
  const [loading, setLoading] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const { addToast } = useNotificationContext()

  // Fetch prefill data from the existing fulfill endpoint
  useEffect(() => {
    if (!open) return
    setLoading(true)
    setError(null)
    api.get(`/api/orders/${orderId}/fulfill`)
      .then(res => {
        const data = res.data as FulfillPayload
        setPayload(data)
        if (data.items.length > 0) {
          setItems(data.items.map(it => ({
            product_id: String(it.product_id),
            product_name: it.product_name,
            quantity: String(it.quantity),
            unit_price: it.unit_price != null ? String(it.unit_price) : '',
            available_stock: it.available_stock,
          })))
        } else {
          // No items on order — start with one empty row for manual entry
          setItems([{ product_id: '', product_name: '', quantity: '', unit_price: '', available_stock: null }])
        }
      })
      .catch(err => {
        const detail = err?.response?.data?.detail
        setError(typeof detail === 'string' ? detail : 'Failed to load order data')
      })
      .finally(() => setLoading(false))
  }, [open, orderId])

  if (!open) return null

  const updateItem = (idx: number, field: keyof LineItem, value: string) => {
    setItems(prev => prev.map((it, i) => i === idx ? { ...it, [field]: value } : it))
  }

  const removeItem = (idx: number) => {
    setItems(prev => prev.filter((_, i) => i !== idx))
  }

  const addItem = () => {
    setItems(prev => [...prev, { product_id: '', product_name: '', quantity: '', unit_price: '', available_stock: null }])
  }

  const allValid = items.length > 0 && items.every(it => {
    const pid = parseInt(it.product_id)
    const qty = parseInt(it.quantity)
    const price = parseFloat(it.unit_price)
    return !isNaN(pid) && pid > 0 && !isNaN(qty) && qty > 0 && !isNaN(price) && price >= 0
  })

  const hasStockIssue = items.some(it => {
    const qty = parseInt(it.quantity)
    return it.available_stock !== null && !isNaN(qty) && qty > it.available_stock
  })

  const grandTotal = items.reduce((sum, it) => {
    const qty = parseInt(it.quantity) || 0
    const price = parseFloat(it.unit_price) || 0
    return sum + qty * price
  }, 0)

  const handleSubmit = async () => {
    if (!allValid) return
    setSubmitting(true)
    setError(null)

    try {
      const requestItems = items.map(it => ({
        product_id: parseInt(it.product_id),
        quantity: parseInt(it.quantity),
        unit_price: parseFloat(it.unit_price),
      }))

      const res = await api.post(`/api/orders/${orderId}/record-sales`, { items: requestItems })
      const data = res.data as { success: boolean; sales_created: number[] }

      addToast({ type: 'success', title: `Converted to ${data.sales_created.length} sale(s)` })

      // Refresh stores
      useOrderStore.getState().fetchOrders()
      useSalesStore.getState().fetchSummary()
      useInventoryStore.getState().fetchInventory()

      // 🔥 Ensure Task UI updates and close modal immediately after
      await useTaskStore.getState().fetchMyTasks()
      onClose()

      onSuccess?.()
    } catch (err: any) {
      const detail = err?.response?.data?.detail
      const msg = typeof detail === 'string' ? detail : detail?.message || 'Failed to convert order to sale'
      setError(msg)
    } finally {
      setSubmitting(false)
    }
  }

  const hasOrderItems = payload && payload.items.length > 0

  return (
    <div className="fixed inset-0 z-50 flex items-end sm:items-center justify-center">
      <div className="absolute inset-0 bg-black/70" onClick={onClose} />

      <div className="relative w-full sm:max-w-xl mx-0 sm:mx-4 max-h-[92dvh] flex flex-col bg-[#313338] rounded-t-xl sm:rounded-xl shadow-2xl">
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b border-[#3f4147]">
          <div className="flex items-center gap-2">
            <ShoppingCart size={20} className="text-green-400" />
            <h2 className="text-lg font-semibold text-white">Convert Order #{orderId} to Sale</h2>
          </div>
          <button onClick={onClose} className="p-1.5 text-[#b5bac1] hover:text-white rounded hover:bg-[#35373c] transition-colors">
            <X size={20} />
          </button>
        </div>

        {/* Body */}
        <div className="flex-1 overflow-y-auto overscroll-contain p-4 space-y-4">
          {loading ? (
            <div className="flex items-center justify-center py-12">
              <Loader2 className="animate-spin text-[#5865f2]" size={32} />
            </div>
          ) : error && !payload ? (
            <div className="text-center py-8">
              <AlertCircle size={48} className="mx-auto text-red-400 mb-4" />
              <p className="text-red-400">{error}</p>
            </div>
          ) : payload ? (
            <>
              {/* Order Info Summary */}
              <div className="bg-[#2b2d31] rounded-lg p-3 border border-[#1f2023] text-sm space-y-1">
                <div className="flex justify-between">
                  <span className="text-[#949ba4]">Channel</span>
                  <span className="text-white capitalize">{payload.sale_channel}</span>
                </div>
                {payload.customer_name && (
                  <div className="flex justify-between">
                    <span className="text-[#949ba4]">Customer</span>
                    <span className="text-white">{payload.customer_name}</span>
                  </div>
                )}
                {payload.payment_method && (
                  <div className="flex justify-between">
                    <span className="text-[#949ba4]">Payment</span>
                    <span className="text-white capitalize">{payload.payment_method}</span>
                  </div>
                )}
                {payload.reference && (
                  <div className="flex justify-between">
                    <span className="text-[#949ba4]">Reference</span>
                    <span className="text-white">{payload.reference}</span>
                  </div>
                )}
              </div>

              {/* Line Items */}
              <div className="space-y-3">
                <div className="flex items-center justify-between">
                  <h3 className="text-sm font-medium text-[#949ba4]">
                    {hasOrderItems ? 'Line Items — Enter unit prices to confirm' : 'Add items manually'}
                  </h3>
                  {!hasOrderItems && (
                    <button
                      onClick={addItem}
                      className="flex items-center gap-1 text-xs text-[#5865f2] hover:text-[#7983f5] transition-colors"
                    >
                      <Plus size={12} /> Add Item
                    </button>
                  )}
                </div>

                {items.map((item, idx) => {
                  const qty = parseInt(item.quantity) || 0
                  const price = parseFloat(item.unit_price) || 0
                  const lineTotal = qty * price
                  const stockWarning = item.available_stock !== null && qty > item.available_stock

                  return (
                    <div key={idx} className="bg-[#2b2d31] rounded-lg p-3 border border-[#1f2023]">
                      {hasOrderItems ? (
                        /* Pre-filled item — show name, qty is fixed, price is editable */
                        <>
                          <div className="flex items-start justify-between mb-2">
                            <div>
                              <span className="text-white font-medium">{item.product_name}</span>
                              <div className="flex gap-3 text-xs text-[#949ba4] mt-0.5">
                                <span>Qty: <span className="text-white">{item.quantity}</span></span>
                                {item.available_stock !== null && (
                                  <span className={stockWarning ? 'text-red-400' : ''}>
                                    Stock: {item.available_stock}
                                  </span>
                                )}
                              </div>
                            </div>
                            <span className="text-white font-semibold text-sm">
                              {price > 0 ? lineTotal.toLocaleString() : '—'}
                            </span>
                          </div>
                          <div className="flex items-center gap-2">
                            <label className="text-xs text-[#949ba4] whitespace-nowrap">Unit Price</label>
                            <input
                              type="number"
                              min="0"
                              step="any"
                              value={item.unit_price}
                              onChange={e => updateItem(idx, 'unit_price', e.target.value)}
                              placeholder="Enter price..."
                              className="flex-1 px-3 py-1.5 bg-[#1e1f22] border border-[#3f4147] rounded text-white text-sm placeholder-[#72767d] focus:outline-none focus:border-[#5865f2]"
                            />
                          </div>
                        </>
                      ) : (
                        /* Manual entry — all fields editable */
                        <>
                          <div className="flex items-center justify-between mb-2">
                            <span className="text-xs text-[#949ba4]">Item {idx + 1}</span>
                            {items.length > 1 && (
                              <button onClick={() => removeItem(idx)} className="text-red-400 hover:text-red-300">
                                <Trash2 size={14} />
                              </button>
                            )}
                          </div>
                          <div className="grid grid-cols-3 gap-2">
                            <div>
                              <label className="text-xs text-[#949ba4]">Product ID</label>
                              <input
                                type="number"
                                value={item.product_id}
                                onChange={e => updateItem(idx, 'product_id', e.target.value)}
                                placeholder="ID"
                                className="w-full px-2 py-1.5 bg-[#1e1f22] border border-[#3f4147] rounded text-white text-sm placeholder-[#72767d] focus:outline-none focus:border-[#5865f2]"
                              />
                            </div>
                            <div>
                              <label className="text-xs text-[#949ba4]">Quantity</label>
                              <input
                                type="number"
                                min="1"
                                value={item.quantity}
                                onChange={e => updateItem(idx, 'quantity', e.target.value)}
                                placeholder="Qty"
                                className="w-full px-2 py-1.5 bg-[#1e1f22] border border-[#3f4147] rounded text-white text-sm placeholder-[#72767d] focus:outline-none focus:border-[#5865f2]"
                              />
                            </div>
                            <div>
                              <label className="text-xs text-[#949ba4]">Unit Price</label>
                              <input
                                type="number"
                                min="0"
                                step="any"
                                value={item.unit_price}
                                onChange={e => updateItem(idx, 'unit_price', e.target.value)}
                                placeholder="Price"
                                className="w-full px-2 py-1.5 bg-[#1e1f22] border border-[#3f4147] rounded text-white text-sm placeholder-[#72767d] focus:outline-none focus:border-[#5865f2]"
                              />
                            </div>
                          </div>
                        </>
                      )}
                      {stockWarning && (
                        <p className="text-red-400 text-xs mt-1.5 flex items-center gap-1">
                          <AlertCircle size={12} /> Insufficient stock
                        </p>
                      )}
                    </div>
                  )
                })}

                {/* Grand Total */}
                {items.length > 0 && (
                  <div className="flex justify-between items-center pt-2 border-t border-[#3f4147]">
                    <span className="text-[#949ba4] font-medium">Total</span>
                    <span className="text-white text-lg font-semibold">{grandTotal.toLocaleString()}</span>
                  </div>
                )}
              </div>

              {/* Error during submission */}
              {error && payload && (
                <div className="bg-red-400/10 border border-red-400/20 rounded-lg p-3 text-red-400 text-sm flex items-center gap-2">
                  <AlertCircle size={16} />
                  {error}
                </div>
              )}
            </>
          ) : null}
        </div>

        {/* Footer */}
        {payload && items.length > 0 && (
          <div className="p-4 border-t border-[#3f4147] flex justify-end gap-2">
            <button
              onClick={onClose}
              className="px-4 py-2 text-sm text-[#b5bac1] hover:text-white transition-colors"
            >
              Cancel
            </button>
            <button
              onClick={handleSubmit}
              disabled={submitting || !allValid || hasStockIssue}
              className="px-4 py-2 text-sm bg-green-600 hover:bg-green-700 text-white rounded-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-1.5"
            >
              {submitting ? (
                <><Loader2 size={14} className="animate-spin" /> Converting...</>
              ) : (
                <><CheckCircle size={14} /> Convert to Sale</>
              )}
            </button>
          </div>
        )}
      </div>
    </div>
  )
}
