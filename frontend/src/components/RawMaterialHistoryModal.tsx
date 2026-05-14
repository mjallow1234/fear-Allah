import { useState, useEffect, useCallback } from 'react'
import { X, Loader2, History, TrendingUp, TrendingDown, Package, Undo2 } from 'lucide-react'
import api from '../services/api'
import { useTaskStore } from '../stores/taskStore'

interface Transaction {
  id: number
  change: number
  reason: string
  notes: string | null
  reversed: boolean
  reversal_of_id: number | null
  performed_by: { id: number; name: string } | null
  created_at: string | null
}

interface TransactionsResponse {
  material_id: number
  material_name: string
  current_stock: number
  unit: string
  transactions: Transaction[]
  count: number
}

interface Props {
  materialId: number
  materialName: string
  open: boolean
  onClose: () => void
  isAdmin?: boolean
  onReversed?: () => void
}

const REASON_CONFIG: Record<string, { label: string; color: string; bg: string }> = {
  add:            { label: 'Add',       color: 'text-green-400', bg: 'bg-green-400/10' },
  consume:        { label: 'Consume',   color: 'text-red-400',   bg: 'bg-red-400/10' },
  adjust:         { label: 'Adjust',    color: 'text-yellow-400', bg: 'bg-yellow-400/10' },
  return:         { label: 'Return',    color: 'text-blue-400',  bg: 'bg-blue-400/10' },
  processing_out: { label: 'Processing', color: 'text-purple-400', bg: 'bg-purple-400/10' },
}

function ReasonBadge({ reason }: { reason: string }) {
  const cfg = REASON_CONFIG[reason] || { label: reason, color: 'text-[#949ba4]', bg: 'bg-[#3f4147]' }
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium ${cfg.color} ${cfg.bg}`}>
      {cfg.label}
    </span>
  )
}

export default function RawMaterialHistoryModal({ materialId, materialName, open, onClose, isAdmin, onReversed }: Props) {
  const [data, setData] = useState<TransactionsResponse | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [reversingId, setReversingId] = useState<number | null>(null)
  const [confirmReverseId, setConfirmReverseId] = useState<number | null>(null)

  const fetchData = useCallback(() => {
    setLoading(true)
    setError(null)
    api.get(`/api/inventory/raw-materials/${materialId}/transactions?limit=100`)
      .then(res => setData(res.data))
      .catch(() => setError('Failed to load transaction history'))
      .finally(() => setLoading(false))
  }, [materialId])

  useEffect(() => {
    if (!open) return
    fetchData()
  }, [open, fetchData])

  const handleReverse = async (txId: number) => {
    setReversingId(txId)
    try {
      await api.post(`/api/inventory/raw-materials/transactions/${txId}/reverse`)
      await useTaskStore.getState().fetchMyTasks()
      setConfirmReverseId(null)
      fetchData()
      onReversed?.()
    } catch (err: any) {
      const msg = err?.response?.data?.detail || 'Failed to reverse transaction'
      setError(msg)
    } finally {
      setReversingId(null)
    }
  }

  if (!open) return null

  const totalAdded = data?.transactions.filter(t => t.change > 0).reduce((s, t) => s + t.change, 0) ?? 0
  const totalConsumed = data?.transactions.filter(t => t.change < 0).reduce((s, t) => s + Math.abs(t.change), 0) ?? 0

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      <div className="absolute inset-0 bg-black/70" onClick={onClose} />

      <div className="relative w-full max-w-2xl max-h-[90vh] flex flex-col bg-[#313338] rounded-xl shadow-2xl">
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b border-[#3f4147]">
          <div className="flex items-center gap-2">
            <History size={20} className="text-amber-400" />
            <h2 className="text-lg font-semibold text-white">{materialName} — History</h2>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 text-[#b5bac1] hover:text-white rounded hover:bg-[#35373c] transition-colors"
          >
            <X size={20} />
          </button>
        </div>

        {/* Body */}
        <div className="flex-1 overflow-y-auto p-4 space-y-4">
          {loading ? (
            <div className="flex items-center justify-center py-12">
              <Loader2 className="animate-spin text-[#5865f2]" size={32} />
            </div>
          ) : error ? (
            <div className="text-center py-8">
              <p className="text-red-400">{error}</p>
            </div>
          ) : data && data.transactions.length === 0 ? (
            <div className="text-center py-12">
              <History size={48} className="mx-auto text-[#949ba4] mb-4" />
              <p className="text-white font-medium mb-1">No history yet for this material</p>
              <p className="text-[#949ba4] text-sm">Stock changes will appear here once recorded.</p>
            </div>
          ) : data ? (
            <>
              {/* Summary Cards */}
              <div className="grid grid-cols-3 gap-3">
                <div className="bg-[#2b2d31] rounded-lg p-3 border border-[#1f2023]">
                  <div className="flex items-center gap-2 text-[#949ba4] text-xs mb-1">
                    <TrendingUp size={14} className="text-green-400" />
                    Total Added
                  </div>
                  <p className="text-green-400 text-lg font-semibold">+{totalAdded.toLocaleString()} <span className="text-xs font-normal text-[#949ba4]">{data.unit}</span></p>
                </div>
                <div className="bg-[#2b2d31] rounded-lg p-3 border border-[#1f2023]">
                  <div className="flex items-center gap-2 text-[#949ba4] text-xs mb-1">
                    <TrendingDown size={14} className="text-red-400" />
                    Total Consumed
                  </div>
                  <p className="text-red-400 text-lg font-semibold">−{totalConsumed.toLocaleString()} <span className="text-xs font-normal text-[#949ba4]">{data.unit}</span></p>
                </div>
                <div className="bg-[#2b2d31] rounded-lg p-3 border border-[#1f2023]">
                  <div className="flex items-center gap-2 text-[#949ba4] text-xs mb-1">
                    <Package size={14} className="text-[#5865f2]" />
                    Current Stock
                  </div>
                  <p className="text-white text-lg font-semibold">{data.current_stock.toLocaleString()} <span className="text-xs font-normal text-[#949ba4]">{data.unit}</span></p>
                </div>
              </div>

              {/* Transactions Table */}
              <div className="bg-[#2b2d31] rounded-lg border border-[#1f2023] overflow-hidden">
                <table className="w-full table-fixed">
                  <thead>
                    <tr className="border-b border-[#1f2023]">
                      <th className="w-[20%] text-left text-[#949ba4] text-xs font-medium px-4 py-2.5">Date</th>
                      <th className="w-[10%] text-center text-[#949ba4] text-xs font-medium px-4 py-2.5">Change</th>
                      <th className="w-[12%] text-center text-[#949ba4] text-xs font-medium px-4 py-2.5">Type</th>
                      <th className="w-[14%] text-left text-[#949ba4] text-xs font-medium px-4 py-2.5">User</th>
                      <th className="w-[24%] text-left text-[#949ba4] text-xs font-medium px-4 py-2.5">Note</th>
                      <th className="w-[20%] text-right text-[#949ba4] text-xs font-medium px-4 py-2.5">Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.transactions.map(tx => (
                      <tr key={tx.id} className={`border-b border-[#1f2023] last:border-0 ${tx.reversed ? 'opacity-50' : ''}`}>
                        <td className="w-[20%] text-left px-4 py-2.5 text-[#b5bac1] text-sm">
                          {tx.created_at
                            ? new Date(tx.created_at).toLocaleDateString('en-US', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })
                            : '—'}
                        </td>
                        <td className="w-[10%] text-center px-4 py-2.5 font-semibold text-sm">
                          {tx.change > 0
                            ? <span className="text-green-400">+{tx.change}</span>
                            : <span className="text-red-400">{tx.change}</span>}
                        </td>
                        <td className="w-[12%] text-center px-4 py-2.5">
                          <div className="flex justify-center">
                            <ReasonBadge reason={tx.reason} />
                          </div>
                        </td>
                        <td className="w-[14%] text-left px-4 py-2.5 text-[#b5bac1] text-sm truncate">
                          {tx.performed_by?.name || 'System'}
                        </td>
                        <td className="w-[24%] text-left px-4 py-2.5 text-[#949ba4] text-sm truncate" title={tx.notes || ''}>
                          {tx.notes || '—'}
                        </td>
                        <td className="w-[20%] text-right px-4 py-2.5">
                          <div className="flex justify-end gap-1.5">
                            {tx.reversed ? (
                              <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium text-[#949ba4] bg-[#3f4147]">
                                Reversed
                              </span>
                            ) : tx.reversal_of_id ? (
                              <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium text-blue-400 bg-blue-400/10">
                                Reversal
                              </span>
                            ) : isAdmin ? (
                              <button
                                onClick={() => setConfirmReverseId(tx.id)}
                                disabled={reversingId === tx.id}
                                className="inline-flex items-center gap-1 px-2 py-1 text-xs bg-[#4f545c] hover:bg-[#5d6269] text-white rounded transition-colors disabled:opacity-50"
                                title="Reverse this transaction"
                              >
                                {reversingId === tx.id ? <Loader2 size={12} className="animate-spin" /> : <Undo2 size={12} />}
                                Reverse
                              </button>
                            ) : null}
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              {/* Confirmation Dialog */}
              {confirmReverseId !== null && (
                <div className="fixed inset-0 z-[60] flex items-center justify-center">
                  <div className="absolute inset-0 bg-black/50" onClick={() => setConfirmReverseId(null)} />
                  <div className="relative bg-[#313338] rounded-xl p-6 max-w-sm shadow-2xl border border-[#3f4147]">
                    <h3 className="text-white font-semibold mb-2">Reverse Transaction?</h3>
                    <p className="text-[#b5bac1] text-sm mb-4">
                      This will create an opposite transaction to undo this stock change. The original record will be preserved.
                    </p>
                    <div className="flex justify-end gap-2">
                      <button
                        onClick={() => setConfirmReverseId(null)}
                        className="px-4 py-2 text-sm text-[#b5bac1] hover:text-white transition-colors"
                      >
                        Cancel
                      </button>
                      <button
                        onClick={() => handleReverse(confirmReverseId)}
                        disabled={reversingId !== null}
                        className="px-4 py-2 text-sm bg-red-600 hover:bg-red-700 text-white rounded-lg transition-colors disabled:opacity-50 flex items-center gap-1.5"
                      >
                        {reversingId ? <Loader2 size={14} className="animate-spin" /> : <Undo2 size={14} />}
                        Reverse
                      </button>
                    </div>
                  </div>
                </div>
              )}
            </>
          ) : null}
        </div>
      </div>
    </div>
  )
}
