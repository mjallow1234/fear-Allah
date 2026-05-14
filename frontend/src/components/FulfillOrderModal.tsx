/**
 * FulfillOrderModal
 * Pre-fills a sale form from order data and submits via POST /api/sales/.
 * Shows order items with editable unit prices, then creates one sale per line item.
 */
import { useState, useEffect } from 'react'
import { X, Loader2, ShoppingCart, AlertCircle, CheckCircle, Package } from 'lucide-react'
import api from '../services/api'

interface FulfillItem {
  product_id: number
  product_name: string
  quantity: number
  available_stock: number | null
  unit_price: string  // editable
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

export default function FulfillOrderModal({ orderId, open, onClose, onSuccess }: Props) {
  const [payload, setPayload] = useState<FulfillPayload | null>(null)
  const [items, setItems] = useState<FulfillItem[]>([])
  const [loading, setLoading] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [completedCount, setCompletedCount] = useState(0)

  useEffect(() => {
    if (!open) return
    setLoading(true)
    setError(null)
    setCompletedCount(0)
    api.get(`/api/orders/${orderId}/fulfill`)
      .then(res => {
        const data = res.data as FulfillPayload
        setPayload(data)
        setItems(data.items.map(it => ({
          ...it,
          unit_price: it.unit_price != null ? String(it.unit_price) : '',
        })))
      })
      .catch(err => {
        const detail = err?.response?.data?.detail
        setError(typeof detail === 'string' ? detail : 'Failed to load order data')
      })
      .finally(() => setLoading(false))
  }, [open, orderId])

  if (!open) return null

  const updateItemPrice = (idx: number, value: string) => {
    setItems(prev => prev.map((it, i) => i === idx ? { ...it, unit_price: value } : it))
  }

  const allPricesFilled = items.every(it => {
    const v = parseFloat(it.unit_price)
    return !isNaN(v) && v > 0
  })

  const hasStockIssue = items.some(it => it.available_stock !== null && it.quantity > it.available_stock)

  const handleSubmit = async () => {
    if (!payload || !allPricesFilled) return
    setSubmitting(true)
    setError(null)
    setCompletedCount(0)

    try {
      for (let i = 0; i < items.length; i++) {
        const item = items[i]
        const salePayload: Record<string, unknown> = {
          product_id: item.product_id,
          quantity: item.quantity,
          unit_price: parseFloat(item.unit_price),
          sale_channel: payload.sale_channel,
          related_order_id: payload.order_id,
        }
        if (payload.customer_name) salePayload.customer_name = payload.customer_name
        if (payload.customer_phone) salePayload.customer_phone = payload.customer_phone
        if (payload.reference) salePayload.reference = payload.reference
        if (payload.payment_method) salePayload.payment_method = payload.payment_method

        await api.post('/api/sales/', salePayload)
        setCompletedCount(i + 1)
      }
      onSuccess?.()
      onClose()
    } catch (err: any) {
      const detail = err?.response?.data?.detail
      const msg = typeof detail === 'string' ? detail : detail?.message || 'Failed to record sale'
      setError(msg)
    } finally {
      setSubmitting(false)
    }
  }

  const grandTotal = items.reduce((sum, it) => {
    const price = parseFloat(it.unit_price) || 0
    return sum + it.quantity * price
  }, 0)

  return (
    <div className="fixed inset-0 z-50 flex items-end sm:items-center justify-center">
      <div className="absolute inset-0 bg-black/70" onClick={onClose} />

      <div className="relative w-full sm:max-w-xl mx-0 sm:mx-4 max-h-[92dvh] flex flex-col bg-[#313338] rounded-t-xl sm:rounded-xl shadow-2xl">
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b border-[#3f4147]">
          <div className="flex items-center gap-2">
            <ShoppingCart size={20} className="text-green-400" />
            <h2 className="text-lg font-semibold text-white">Fulfill Order #{orderId}</h2>
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
              {items.length === 0 ? (
                <div className="text-center py-8">
                  <Package size={48} className="mx-auto text-[#949ba4] mb-4" />
                  <p className="text-white font-medium mb-1">No items in this order</p>
                  <p className="text-[#949ba4] text-sm">Cannot fulfill an order with no line items.</p>
                </div>
              ) : (
                <div className="space-y-3">
                  <h3 className="text-sm font-medium text-[#949ba4]">Line Items — Enter unit prices to confirm</h3>
                  {items.map((item, idx) => {
                    const price = parseFloat(item.unit_price) || 0
                    const lineTotal = item.quantity * price
                    const stockWarning = item.available_stock !== null && item.quantity > item.available_stock
                    return (
                      <div key={idx} className="bg-[#2b2d31] rounded-lg p-3 border border-[#1f2023]">
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
                            onChange={e => updateItemPrice(idx, e.target.value)}
                            placeholder="Enter price..."
                            className="flex-1 px-3 py-1.5 bg-[#1e1f22] border border-[#3f4147] rounded text-white text-sm placeholder-[#72767d] focus:outline-none focus:border-[#5865f2]"
                          />
                        </div>
                        {stockWarning && (
                          <p className="text-red-400 text-xs mt-1.5 flex items-center gap-1">
                            <AlertCircle size={12} /> Insufficient stock
                          </p>
                        )}
                      </div>
                    )
                  })}

                  {/* Grand Total */}
                  <div className="flex justify-between items-center pt-2 border-t border-[#3f4147]">
                    <span className="text-[#949ba4] font-medium">Total</span>
                    <span className="text-white text-lg font-semibold">{grandTotal.toLocaleString()}</span>
                  </div>
                </div>
              )}

              {/* Error during submission */}
              {error && payload && (
                <div className="bg-red-400/10 border border-red-400/20 rounded-lg p-3 text-red-400 text-sm flex items-center gap-2">
                  <AlertCircle size={16} />
                  {error}
                </div>
              )}

              {/* Submission progress */}
              {submitting && items.length > 1 && (
                <div className="text-sm text-[#949ba4] text-center">
                  Recording sale {completedCount + 1} of {items.length}...
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
              disabled={submitting || !allPricesFilled || hasStockIssue}
              className="px-4 py-2 text-sm bg-green-600 hover:bg-green-700 text-white rounded-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-1.5"
            >
              {submitting ? (
                <><Loader2 size={14} className="animate-spin" /> Recording...</>
              ) : (
                <><CheckCircle size={14} /> Fulfill Order</>
              )}
            </button>
          </div>
        )}
      </div>
    </div>
  )
}
