/**
 * Sale Details Page
 * Route: /sales/:id
 *
 * Full detail view for a single sale. Mobile-first card layout.
 * Respects existing admin / non-admin permission model:
 *   - Admins see unit_price, total_amount, affiliate info
 *   - Non-admins see '—' for all financial fields
 * Users who cannot view others' sales and request a foreign sale get a 403.
 */
import { useEffect, useState, useCallback } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import {
  ArrowLeft,
  ShoppingCart,
  User,
  Package,
  CreditCard,
  ClipboardList,
  RefreshCw,
  Loader2,
  AlertTriangle,
  RotateCcw,
  ExternalLink,
  Calendar,
  Tag,
} from 'lucide-react'
import clsx from 'clsx'
import { useAuthStore } from '../stores/authStore'
import api from '../services/api'

// ─── Types ────────────────────────────────────────────────────────────────────

interface SaleDetail {
  sale_id: number
  product_id: number
  product_name: string
  quantity: number
  unit_price: number | null
  total_amount: number | null
  sale_channel: string
  sold_by_user_id: number | null
  location: string | null
  reference: string | null
  customer_name: string | null
  customer_phone: string | null
  payment_method: string | null
  discount: number | null
  sale_date: string | null
  related_order_id: number | null
  linked_order_id: number | null
  is_reversed: boolean
  reversed_at: string | null
  affiliate_code: string | null
  affiliate_name: string | null
  affiliate_source: string | null
  sold_by: { id: number; username: string; display_name: string } | null
  reversed_by: { id: number; username: string; display_name: string } | null
  related_order: { id: number; status: string; customer_name: string | null } | null
  inventory_transaction: {
    id: number
    change: number
    reason: string
    notes: string | null
    created_at: string
  } | null
  created_at: string
}

// ─── Helpers ─────────────────────────────────────────────────────────────────

function formatGMD(value: number | null | undefined): string {
  if (value == null) return '—'
  return `D ${Number(value).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
}

function formatDate(dateStr: string | null | undefined): string {
  if (!dateStr) return '—'
  return new Date(dateStr).toLocaleDateString('en-US', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

const CHANNEL_LABELS: Record<string, string> = {
  field: 'Field Sale',
  store: 'Store Sale',
  direct: 'Direct Sale',
  delivery: 'Delivery Sale',
  AGENT: 'Agent Sale',
  WHOLESALE: 'Wholesale',
}

const PAYMENT_LABELS: Record<string, string> = {
  cash: 'Cash',
  card: 'Card',
  transfer: 'Bank Transfer',
  credit: 'Credit',
  mobile_money: 'Mobile Money',
}

// ─── Sub-components ───────────────────────────────────────────────────────────

function SectionCard({
  title,
  icon: Icon,
  children,
  className,
}: {
  title: string
  icon: React.ElementType
  children: React.ReactNode
  className?: string
}) {
  return (
    <div
      className={clsx(
        'rounded-lg border overflow-hidden',
        'bg-[#2b2d31] border-[#1f2023]',
        className,
      )}
    >
      <div className="px-4 py-3 border-b border-[#1f2023] flex items-center gap-2">
        <Icon size={14} className="text-[#949ba4] flex-shrink-0" />
        <span className="text-xs font-semibold text-[#949ba4] uppercase tracking-wider">
          {title}
        </span>
      </div>
      <div className="px-4 py-3">{children}</div>
    </div>
  )
}

function Row({
  label,
  value,
  valueClass,
}: {
  label: string
  value: React.ReactNode
  valueClass?: string
}) {
  return (
    <div className="flex items-start justify-between gap-3 py-1.5 border-b border-[#1f2023] last:border-b-0">
      <span className="text-[#949ba4] text-sm flex-shrink-0">{label}</span>
      <span className={clsx('text-sm text-right break-all', valueClass ?? 'text-white')}>
        {value ?? '—'}
      </span>
    </div>
  )
}

// ─── Page ─────────────────────────────────────────────────────────────────────

export default function SaleDetailsPage() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const { currentUser } = useAuthStore()
  const isAdmin = Boolean(
    currentUser?.is_system_admin === true ||
      currentUser?.operational_roles?.includes('admin'),
  )

  const [sale, setSale] = useState<SaleDetail | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const fetchSale = useCallback(async () => {
    if (!id) return
    setLoading(true)
    setError(null)
    try {
      const resp = await api.get(`/api/sales/${id}`)
      setSale(resp.data as SaleDetail)
    } catch (err: unknown) {
      const status = (err as { response?: { status?: number } })?.response?.status
      if (status === 403) setError("You don't have permission to view this sale.")
      else if (status === 404) setError('Sale not found.')
      else setError('Failed to load sale details. Please try again.')
    } finally {
      setLoading(false)
    }
  }, [id])

  useEffect(() => {
    fetchSale()
  }, [fetchSale])

  // ── Render: loading ──────────────────────────────────────────────────────
  if (loading) {
    return (
      <div
        className="flex items-center justify-center h-full min-h-[300px]"
        style={{ backgroundColor: 'var(--main-bg)' }}
      >
        <Loader2 size={32} className="animate-spin text-[#5865f2]" />
      </div>
    )
  }

  // ── Render: error ────────────────────────────────────────────────────────
  if (error || !sale) {
    return (
      <div
        className="flex flex-col items-center justify-center h-full min-h-[300px] gap-4"
        style={{ backgroundColor: 'var(--main-bg)' }}
      >
        <AlertTriangle size={40} className="text-yellow-400" />
        <p className="text-[#949ba4] text-sm text-center px-6">{error ?? 'Sale not found.'}</p>
        <button
          onClick={() => navigate(-1)}
          className="px-4 py-2 text-sm font-medium text-white bg-[#5865f2] hover:bg-[#4752c4] rounded-lg transition-colors"
        >
          Go Back
        </button>
      </div>
    )
  }

  // ── Resolved values ──────────────────────────────────────────────────────
  const orderLinkId = sale.related_order_id ?? sale.linked_order_id
  const hasAffiliate = sale.affiliate_code || sale.affiliate_name || sale.affiliate_source
  const hasCustomer = sale.customer_name || sale.customer_phone
  const hasFinancial = sale.payment_method || (sale.discount != null && sale.discount !== 0)
  const soldByLabel = sale.sold_by
    ? sale.sold_by.display_name || sale.sold_by.username
    : 'Unknown'

  // ── Render: page ─────────────────────────────────────────────────────────
  return (
    <div
      className="flex flex-col min-h-full"
      style={{ backgroundColor: 'var(--main-bg)' }}
    >
      {/* ── Header ── */}
      <div
        className="flex-shrink-0 h-12 flex items-center px-3 sm:px-4 gap-2 justify-between border-b border-[#1f2023]"
        style={{ backgroundColor: 'var(--main-bg)' }}
      >
        <div className="flex items-center gap-2 min-w-0">
          <button
            onClick={() => navigate(-1)}
            className="p-1 flex-shrink-0 transition-colors hover:text-white"
            style={{ color: 'var(--text-secondary)' }}
            aria-label="Go back"
          >
            <ArrowLeft size={20} />
          </button>
          <ShoppingCart size={16} className="flex-shrink-0 text-green-400" />
          <span
            className="font-semibold text-sm sm:text-base truncate"
            style={{ color: 'var(--text-primary)' }}
          >
            Sale #{sale.sale_id}
          </span>
          {sale.is_reversed && (
            <span className="flex-shrink-0 px-2 py-0.5 text-xs font-medium bg-orange-500/20 text-orange-400 rounded-full flex items-center gap-1">
              <RotateCcw size={10} />
              Reversed
            </span>
          )}
        </div>

        <button
          onClick={fetchSale}
          disabled={loading}
          className="p-2 flex-shrink-0 text-[#949ba4] hover:text-white transition-colors disabled:opacity-40"
          aria-label="Refresh"
          title="Refresh"
        >
          <RefreshCw size={16} className={loading ? 'animate-spin' : ''} />
        </button>
      </div>

      {/* ── Content ── */}
      <div className="flex-1 overflow-auto">
        <div className="max-w-3xl mx-auto px-3 py-4 sm:px-6 sm:py-6 space-y-4">

          {/* Reversed banner */}
          {sale.is_reversed && (
            <div className="bg-orange-500/10 border border-orange-500/30 rounded-lg p-3 flex items-start gap-3">
              <RotateCcw size={16} className="text-orange-400 flex-shrink-0 mt-0.5" />
              <div>
                <p className="text-orange-300 text-sm font-medium">This sale has been reversed</p>
                {(sale.reversed_at || sale.reversed_by) && (
                  <p className="text-orange-400/70 text-xs mt-0.5">
                    {sale.reversed_at && `on ${formatDate(sale.reversed_at)}`}
                    {sale.reversed_by &&
                      ` by ${sale.reversed_by.display_name || sale.reversed_by.username}`}
                  </p>
                )}
              </div>
            </div>
          )}

          {/* Desktop 2-col: sale info + customer */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {/* Sale Info */}
            <SectionCard title="Sale Info" icon={ShoppingCart}>
              <Row label="Sale ID" value={`#${sale.sale_id}`} />
              <Row
                label="Channel"
                value={CHANNEL_LABELS[sale.sale_channel] ?? sale.sale_channel}
              />
              <Row label="Created" value={formatDate(sale.created_at)} />
              {sale.sale_date && <Row label="Sale Date" value={formatDate(sale.sale_date)} />}
              {sale.location && <Row label="Location" value={sale.location} />}
              {sale.reference && <Row label="Reference" value={sale.reference} />}
            </SectionCard>

            {/* Customer — only shown if there's data */}
            {hasCustomer && (
              <SectionCard title="Customer" icon={User}>
                {sale.customer_name && <Row label="Name" value={sale.customer_name} />}
                {sale.customer_phone && <Row label="Phone" value={sale.customer_phone} />}
              </SectionCard>
            )}
          </div>

          {/* Product */}
          <SectionCard title="Product" icon={Package}>
            <Row label="Product" value={sale.product_name} />
            <Row
              label="Quantity"
              value={
                <span className="font-semibold">
                  {sale.quantity.toLocaleString()} units
                </span>
              }
            />
            {isAdmin && sale.unit_price != null && (
              <Row
                label="Unit Price"
                value={formatGMD(sale.unit_price)}
                valueClass="text-green-400 font-medium"
              />
            )}
            {isAdmin && sale.total_amount != null && (
              <Row
                label="Total Amount"
                value={formatGMD(sale.total_amount)}
                valueClass="text-green-400 font-bold"
              />
            )}
            {!isAdmin && (
              <Row
                label="Revenue"
                value="—"
                valueClass="text-[#949ba4] italic text-xs"
              />
            )}
          </SectionCard>

          {/* Financial */}
          {hasFinancial && (
            <SectionCard title="Financial" icon={CreditCard}>
              {sale.payment_method && (
                <Row
                  label="Payment Method"
                  value={PAYMENT_LABELS[sale.payment_method] ?? sale.payment_method}
                />
              )}
              {sale.discount != null && sale.discount !== 0 && (
                <Row
                  label="Discount"
                  value={formatGMD(sale.discount)}
                  valueClass="text-yellow-400"
                />
              )}
              {isAdmin &&
                sale.total_amount != null &&
                sale.discount != null &&
                sale.discount !== 0 && (
                  <Row
                    label="Net Amount"
                    value={formatGMD(sale.total_amount - sale.discount)}
                    valueClass="text-green-400 font-bold"
                  />
                )}
            </SectionCard>
          )}

          {/* Linked Order */}
          {orderLinkId && (
            <SectionCard title="Linked Order" icon={ClipboardList}>
              <div className="flex items-center justify-between gap-3">
                <div className="min-w-0">
                  <p className="text-white text-sm font-medium">Order #{orderLinkId}</p>
                  {sale.related_order && (
                    <p className="text-[#949ba4] text-xs mt-0.5 capitalize">
                      {sale.related_order.status.replace(/_/g, ' ')}
                      {sale.related_order.customer_name
                        ? ` · ${sale.related_order.customer_name}`
                        : ''}
                    </p>
                  )}
                </div>
                <button
                  onClick={() => navigate(`/order-snapshot/${orderLinkId}`)}
                  className="flex-shrink-0 flex items-center gap-1 px-3 py-1.5 text-xs font-medium bg-[#5865f2] hover:bg-[#4752c4] text-white rounded-lg transition-colors"
                >
                  View <ExternalLink size={11} />
                </button>
              </div>
            </SectionCard>
          )}

          {/* Inventory Transaction */}
          {sale.inventory_transaction && (
            <SectionCard title="Inventory Transaction" icon={Package}>
              <Row label="TX ID" value={`#${sale.inventory_transaction.id}`} />
              <Row
                label="Stock Change"
                value={
                  <span
                    className={
                      sale.inventory_transaction.change < 0
                        ? 'text-red-400 font-semibold'
                        : 'text-green-400 font-semibold'
                    }
                  >
                    {sale.inventory_transaction.change > 0 ? '+' : ''}
                    {sale.inventory_transaction.change} units
                  </span>
                }
              />
              <Row label="Reason" value={sale.inventory_transaction.reason} />
              {sale.inventory_transaction.notes && (
                <Row label="Notes" value={sale.inventory_transaction.notes} />
              )}
              <Row
                label="Recorded"
                value={formatDate(sale.inventory_transaction.created_at)}
              />
            </SectionCard>
          )}

          {/* Affiliate */}
          {hasAffiliate && (
            <SectionCard title="Affiliate" icon={Tag}>
              {sale.affiliate_name && <Row label="Name" value={sale.affiliate_name} />}
              {sale.affiliate_code && <Row label="Code" value={sale.affiliate_code} />}
              {sale.affiliate_source && <Row label="Source" value={sale.affiliate_source} />}
            </SectionCard>
          )}

          {/* Audit */}
          <SectionCard title="Audit" icon={Calendar}>
            <Row label="Sold by" value={soldByLabel} />
            <Row label="Created" value={formatDate(sale.created_at)} />
            {sale.is_reversed && sale.reversed_by && (
              <Row
                label="Reversed by"
                value={sale.reversed_by.display_name || sale.reversed_by.username}
                valueClass="text-orange-400"
              />
            )}
            {sale.is_reversed && sale.reversed_at && (
              <Row
                label="Reversed at"
                value={formatDate(sale.reversed_at)}
                valueClass="text-orange-400"
              />
            )}
          </SectionCard>

        </div>
      </div>
    </div>
  )
}
