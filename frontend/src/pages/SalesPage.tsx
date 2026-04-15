/**
 * Sales Page
 * Phase 7.4 - Sales UI
 * 
 * Displays sales overview, agent performance, inventory status,
 * raw materials management, and transaction history.
 */
import React, { useEffect, useState } from 'react'
import { useNavigate, useSearchParams, useLocation } from 'react-router-dom'
import {
  ArrowLeft,
  DollarSign,
  ShoppingCart,
  Users,
  Package,
  TrendingUp,
  Loader2,
  RefreshCw,
  AlertTriangle,
  CheckCircle,
  XCircle,
  Calendar,
  ArrowUpRight,
  ArrowDownRight,
  Plus,
  Boxes,
  Pencil,
  Minus,
  Trash,
  RotateCcw
} from 'lucide-react'
import clsx from 'clsx'
import { useSalesStore, DateRangeFilter, SalesChannel } from '../stores/salesStore'
import { useInventoryStore, StockStatus } from '../stores/inventoryStore'
import { useAuthStore } from '../stores/authStore'
import useOperationalPermissions from '../permissions/useOperationalPermissions'
import ProductDetailsDrawer from '../components/ProductDetailsDrawer'
import RawMaterialDetailsDrawer from '../components/RawMaterialDetailsDrawer'
import SalesForm from '../components/forms/SalesForm'
import InventoryForm from '../components/forms/InventoryForm'
import RawMaterialForm from '../components/forms/RawMaterialForm'
import DynamicFormModal from '../components/forms/DynamicFormModal'
import { useNotificationContext } from '../contexts/NotificationProvider'
import api from '../services/api'
import { subscribeToSales } from '../realtime/sales'

// Tab types
type TabType = 'overview' | 'agents' | 'inventory' | 'raw-materials' | 'transactions'

// Channel display config
const channelConfig: Record<SalesChannel, { label: string; color: string }> = {
  'AGENT': { label: 'Agent Sales', color: 'bg-blue-600' },
  'STORE': { label: 'Store Sales', color: 'bg-green-600' },
  'WHOLESALE': { label: 'Wholesale', color: 'bg-purple-600' }
}

// Stock status config
const stockStatusConfig: Record<StockStatus, { label: string; color: string; bgColor: string; icon: typeof CheckCircle }> = {
  'healthy': { label: 'Healthy', color: 'text-green-400', bgColor: 'bg-green-400/10', icon: CheckCircle },
  'low': { label: 'Low', color: 'text-yellow-400', bgColor: 'bg-yellow-400/10', icon: AlertTriangle },
  'critical': { label: 'Critical', color: 'text-red-400', bgColor: 'bg-red-400/10', icon: XCircle }
}

// Format currency as Gambian Dalasi (GMD)
const formatGMD = (value?: number): string =>
  `D ${Number(value ?? 0).toLocaleString()}`

// Format date/time
function formatDateTime(dateStr: string): string {
  const date = new Date(dateStr)
  return date.toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit'
  })
}

export default function SalesPage() {
  const navigate = useNavigate()
  const location = useLocation()
  const [searchParams, setSearchParams] = useSearchParams()
  const { addToast } = useNotificationContext()
  const [activeTab, setActiveTab] = useState<TabType>('overview')
  const [highlightId, setHighlightId] = useState<number | null>(null)
  const [productHighlightId, setProductHighlightId] = useState<number | null>(null)
  const [showSalesForm, setShowSalesForm] = useState(false)
  const [showInventoryForm, setShowInventoryForm] = useState(false)
  const [showRawMaterialForm, setShowRawMaterialForm] = useState(false)
  const [showCreateMaterialForm, setShowCreateMaterialForm] = useState(false)
  // Use dynamic forms when available (toggle _setUseDynamicForms to false for legacy forms)
  const [useDynamicForms, _setUseDynamicForms] = useState(true)

  // React to URL query param changes (notification clicks, direct links)
  useEffect(() => {
    const params = new URLSearchParams(location.search)
    const tabParam = params.get('tab')
    const highlightParam = params.get('highlight')
    const productParam = params.get('product')

    if (highlightParam) {
      setHighlightId(parseInt(highlightParam, 10) || null)
      setActiveTab((tabParam as TabType) || 'transactions')
    } else if (productParam) {
      setProductHighlightId(parseInt(productParam, 10) || null)
      setActiveTab((tabParam as TabType) || 'inventory')
    } else if (tabParam && ['overview', 'agents', 'inventory', 'raw-materials', 'transactions'].includes(tabParam)) {
      setActiveTab(tabParam as TabType)
    }

    // Clean up query params from URL after reading
    if (params.has('tab') || params.has('highlight') || params.has('product')) {
      setSearchParams({}, { replace: true })
    }
  }, [location.search]) // eslint-disable-line react-hooks/exhaustive-deps

  // Subscribe to real-time sale events
  useEffect(() => {
    const unsubscribe = subscribeToSales()
    return () => unsubscribe()
  }, [])

  // Auto-clear highlight after 4 seconds
  useEffect(() => {
    if (highlightId !== null) {
      const timer = setTimeout(() => setHighlightId(null), 4000)
      return () => clearTimeout(timer)
    }
  }, [highlightId])

  // Auto-clear product highlight after 4 seconds
  useEffect(() => {
    if (productHighlightId !== null) {
      const timer = setTimeout(() => setProductHighlightId(null), 4000)
      return () => clearTimeout(timer)
    }
  }, [productHighlightId])
  const [selectedProductId, setSelectedProductId] = useState<number | null>(null)
  const [showProductDrawer, setShowProductDrawer] = useState(false)
  const [selectedMaterialId, setSelectedMaterialId] = useState<number | null>(null)
  const [showMaterialDrawer, setShowMaterialDrawer] = useState(false)
  const [rawMaterialsOverview, setRawMaterialsOverview] = useState<{
    total_materials: number
    low_stock_count: number
    total_used: number
    total_added: number
    total_transactions: number
  } | null>(null)
  
  // Raw materials state
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
  const [rawMaterials, setRawMaterials] = useState<RawMaterial[]>([])
  const [loadingRawMaterials, setLoadingRawMaterials] = useState(false)
  
  // Auth store for role check
  const { currentUser } = useAuthStore()
  // Enforce matrix v1: revenue visible **only** to system admins (strict role check)
  // Revenue visibility must NOT depend on API response — hard block by role here.
  const isAdmin = currentUser?.role === 'system_admin'
  const canManageRawMaterials = currentUser?.operational_roles?.includes('admin')
  // System admin flag used to restrict certain auto-fetch calls (system-admin-only APIs)
  const isSystemAdmin = currentUser?.is_system_admin === true
  // Permissions for Sales sub-views
  const perms = useOperationalPermissions()
  
  // Simple restricted panel renderer
  const RestrictedSection = ({ message = 'You do not have access to this section.' }: { message?: string }) => (
    <div className="text-sm text-[#949ba4]">{message}</div>
  )
  
  // Sales store
  const {
    summary,
    agentPerformance,
    dateRange,
    loadingSummary,
    loadingAgents,
    setDateRange,
    fetchSummary,
    fetchAgentPerformance
  } = useSalesStore()
  
  // Inventory store
  const {
    items: inventoryItems,
    lowStockItems,
    transactions,
    loadingItems,
    loadingTransactions,
    fetchInventory: fetchInventoryItems,
    fetchLowStock,
    fetchTransactions
  } = useInventoryStore()
  
  
  // Fetch raw materials
  const fetchRawMaterials = async () => {
    // Check operational permissions or allow system admins
    if (!perms.sales?.rawMaterials && !currentUser?.is_system_admin) return

    setLoadingRawMaterials(true)
    try {
      const response = await api.get('/api/inventory/raw-materials/')
      setRawMaterials(response.data.items || response.data || [])
    } catch (err: any) {
      if (!(err?.response && err.response.status === 403)) {
        console.error('Failed to fetch raw materials:', err)
      }
    } finally {
      setLoadingRawMaterials(false)
    }
  }
  
  // Fetch raw materials overview stats (admin only)
  const fetchRawMaterialsOverview = async () => {
    // Check operational permissions or allow system admins
    if (!perms.sales?.rawMaterials && !currentUser?.is_system_admin) return
    try {
      const response = await api.get('/api/inventory/raw-materials/overview/stats')
      setRawMaterialsOverview(response.data)
    } catch (err: any) {
      if (!(err?.response && err.response.status === 403)) {
        console.error('Failed to fetch raw materials overview:', err)
      }
    }
  }
  
  // Fetch data on mount - only fetch admin-restricted data if user is admin
  useEffect(() => {
    // Sales: Summary is available to all, agent performance is admin-only
    fetchSummary()
    // Only call system-admin-only APIs when the user is a system admin
    if (isSystemAdmin) {
      fetchAgentPerformance()
      fetchRawMaterials()
      fetchRawMaterialsOverview()
    }
    
    // Inventory: Items and low stock available to all, transactions are system-admin-only
    fetchInventoryItems()
    fetchLowStock()
    if (isSystemAdmin) {
      fetchTransactions()
    }
  }, [isSystemAdmin])
  
  const isLoading = loadingSummary || (isAdmin && loadingAgents) || loadingItems || (isAdmin && loadingTransactions) || (isAdmin && loadingRawMaterials)
  
  const handleRefresh = () => {
    fetchSummary()
    if (isAdmin) {
      fetchAgentPerformance()
      fetchRawMaterials()
      fetchRawMaterialsOverview()
    }
    fetchInventoryItems()
    fetchLowStock()
    if (isAdmin) {
      fetchTransactions()
    }
  }

  // Raw material action handlers (admin only)
  const handleCreateRawMaterial = () => {
    setShowCreateMaterialForm(true)
  }

  const handleAddRawMaterial = () => {
    setSelectedMaterialId(null)
    setShowRawMaterialForm(true)
  }

  const handleEditRawMaterial = (id: number) => {
    setSelectedMaterialId(id)
    setShowRawMaterialForm(true)
  }

  const handleAdjustRawMaterial = (id: number) => {
    setSelectedMaterialId(id)
    setShowRawMaterialForm(true)
  }

  const handleDeleteRawMaterial = async (id: number) => {
    if (!confirm('Delete this raw material?')) return
    try {
      await api.delete(`/api/inventory/raw-materials/${id}`)
      fetchRawMaterials()
    } catch (err) {
      console.error('Failed to delete raw material:', err)
    }
  }
  
  // Date range filter buttons
  const dateRanges: { value: DateRangeFilter; label: string }[] = [
    { value: 'today', label: 'Today' },
    { value: 'week', label: 'This Week' },
    { value: 'month', label: 'This Month' }
  ]

  return (
    <div className="flex flex-col h-full" style={{ backgroundColor: 'var(--main-bg)' }}>
      {/* Header */}
      <div className="h-12 flex items-center px-4 justify-between flex-shrink-0" style={{ borderBottom: '1px solid var(--sidebar-border)' }}>
        <div className="flex items-center gap-3">
          <button
            onClick={() => navigate(-1)}
            className="p-1 transition-colors"
            style={{ color: 'var(--text-secondary)' }}
          >
            <ArrowLeft size={20} />
          </button>
          <DollarSign size={20} style={{ color: 'var(--accent)' }} />
          <span className="font-semibold" style={{ color: 'var(--text-primary)' }}>Sales & Inventory</span>
        </div>
        
        <div className="flex items-center gap-4">
          {/* Action Buttons */}
          <div className="flex items-center gap-2">
            {(currentUser?.operational_roles?.some(r => ["admin","sales_agent","storekeeper"].includes(r))) && (
              <button
                onClick={() => setShowSalesForm(true)}
                className="flex items-center gap-1.5 px-3 py-1.5 text-sm bg-green-600 hover:bg-green-700 text-white rounded-lg transition-colors"
              >
                <Plus size={14} />
                Record Sale
              </button>
            )}
            {isAdmin && (
              <button
                onClick={() => setShowInventoryForm(true)}
                className="flex items-center gap-1.5 px-3 py-1.5 text-sm bg-blue-600 hover:bg-blue-700 text-white rounded-lg transition-colors"
              >
                <Package size={14} />
                Manage Inventory
              </button>
            )}
          </div>
          
          {/* Date Range Filter */}
          <div className="flex items-center gap-1 rounded-lg p-1" style={{ backgroundColor: 'var(--input-bg)' }}>
            {dateRanges.map(({ value, label }) => (
              <button
                key={value}
                onClick={() => setDateRange(value)}
                className={clsx('px-3 py-1 text-sm rounded-md transition-colors')}
                style={dateRange === value ? { backgroundColor: 'var(--accent)', color: 'var(--text-primary)' } : { color: 'var(--text-secondary)' }}
              >
                {label}
              </button>
            ))}
          </div>
          
          {/* Refresh button */}
          <button
            onClick={handleRefresh}
            disabled={isLoading}
            className="p-2 text-[#949ba4] hover:text-white transition-colors disabled:opacity-50"
            title="Refresh"
          >
            <RefreshCw size={18} className={isLoading ? 'animate-spin' : ''} />
          </button>
        </div>
      </div>
      
      {/* Tabs - visible according to operational permissions */}
      <div className="border-b border-[#1f2023] flex px-4 flex-shrink-0">
        {[
          { id: 'overview' as TabType, label: 'Overview', icon: TrendingUp, allowed: true },
          { id: 'agents' as TabType, label: 'Agent Performance', icon: Users, allowed: true },
          { id: 'inventory' as TabType, label: 'Inventory', icon: Package, allowed: true },
          { id: 'raw-materials' as TabType, label: 'Raw Materials', icon: Boxes, allowed: !!perms.sales?.rawMaterials },
          { id: 'transactions' as TabType, label: 'Transactions', icon: Calendar, allowed: true }
        ]
          .filter(tab => tab.allowed)
          .map(({ id, label, icon: Icon }) => (
          <button
            key={id}
            onClick={() => setActiveTab(id)}
            className={clsx(
              'px-4 py-3 text-sm font-medium flex items-center gap-2 border-b-2 transition-colors',
              activeTab === id
                ? 'text-white border-[#5865f2]'
                : 'text-[#949ba4] border-transparent hover:text-white hover:border-[#35373c]'
            )}
          >
            <Icon size={16} />
            {label}
          </button>
        ))}
      </div>

      {/* Keep active tab valid (no permission checks) */}
      {(() => {
        const allowedTabs = ['overview','agents','inventory','raw-materials','transactions'].filter(t => {
          if (t === 'raw-materials') return !!perms.sales?.rawMaterials
          return true
        })
        if (allowedTabs.length > 0 && !allowedTabs.includes(activeTab)) {
          setActiveTab(allowedTabs[0] as TabType)
        }
        return null
      })()}
      
      {/* Content */}
      <div className="flex-1 overflow-y-auto p-4">
        {activeTab === 'overview' && (
            perms.sales?.overview ? (
              <OverviewTab
                summary={summary}
                loading={loadingSummary}
                lowStockCount={lowStockItems.length}
                isAdmin={isAdmin}
                rawMaterialsOverview={rawMaterialsOverview}
              />
            ) : (
              <RestrictedSection message="Overview section restricted" />
            )
        )}
        
        {activeTab === 'agents' && (
            perms.sales?.agentPerformance ? (
              <AgentsTab
                agents={agentPerformance}
                loading={loadingAgents}
                isAdmin={isAdmin}
              />
            ) : (
              <RestrictedSection message="Agent Performance is restricted" />
            )
        )}
        
        {activeTab === 'inventory' && (
            perms.sales?.inventory ? (
              <InventoryTab
                items={inventoryItems}
                lowStockItems={lowStockItems}
                loading={loadingItems}
                highlightProductId={productHighlightId}
                onItemClick={(productId) => {
                  setSelectedProductId(productId)
                  setShowProductDrawer(true)
                }}
              />
            ) : (
              <RestrictedSection message="Inventory section restricted" />
            )
        )}
        
        {activeTab === 'raw-materials' && (
          // Raw materials require rawMaterials sales permission
          perms.sales?.rawMaterials ? (
            <RawMaterialsTab
              materials={rawMaterials}
              loading={loadingRawMaterials}
              isAdmin={isAdmin}

              /* ✅ ADMIN-ONLY ACTIONS */
              onCreateClick={isAdmin ? handleCreateRawMaterial : undefined}
              onAddClick={isAdmin ? handleAddRawMaterial : undefined}
              onEdit={isAdmin ? handleEditRawMaterial : undefined}
              onAdjust={isAdmin ? handleAdjustRawMaterial : undefined}
              onDelete={isAdmin ? handleDeleteRawMaterial : undefined}

              onRefresh={fetchRawMaterials}
              onItemClick={(materialId) => {
                setSelectedMaterialId(materialId)
                setShowMaterialDrawer(true)
              }}

              /* Control empty-state rendering for admins */
              canManageRawMaterials={canManageRawMaterials}
            />
          ) : (
            <RestrictedSection message="Raw Materials are restricted" />
          )
        )}
        
        {activeTab === 'transactions' && (
            perms.sales?.transactions ? (
              <TransactionsTab
                transactions={transactions}
                loading={loadingTransactions}
                isAdmin={isAdmin}
                highlightId={highlightId}
              />
            ) : (
              <RestrictedSection message="Transactions are restricted" />
            )
        )}
      </div>
      
      {/* Form Modals - Use dynamic forms if available, fallback to hardcoded */}
      {useDynamicForms ? (
        <>
          <DynamicFormModal
            isOpen={showSalesForm}
            onClose={() => setShowSalesForm(false)}
            formSlug="sales"
            title="Record Sale"
            onSuccess={() => {
              fetchSummary()
              fetchInventoryItems()
              fetchLowStock()
              if (isAdmin) fetchTransactions()
            }}
            fallbackComponent={
              <SalesForm
                isOpen={true}
                onClose={() => setShowSalesForm(false)}
                onSuccess={() => {
                  fetchSummary()
                  fetchInventoryItems()
                  fetchLowStock()
                  if (isAdmin) fetchTransactions()
                  setShowSalesForm(false)
                }}
              />
            }
          />
          
          <DynamicFormModal
            isOpen={showInventoryForm}
            onClose={() => setShowInventoryForm(false)}
            formSlug="inventory"
            title="Update Inventory"
            onSuccess={() => {
              fetchInventoryItems()
              fetchLowStock()
            }}
            fallbackComponent={
              <InventoryForm
                isOpen={true}
                onClose={() => setShowInventoryForm(false)}
                onSuccess={() => {
                  fetchInventoryItems()
                  fetchLowStock()
                  setShowInventoryForm(false)
                }}
              />
            }
          />
          
          <DynamicFormModal
            isOpen={showRawMaterialForm}
            onClose={() => setShowRawMaterialForm(false)}
            formSlug="raw_materials"
            title="Adjust Raw Material Stock"
            onSuccess={() => {
              fetchRawMaterials()
              addToast({ type: 'success', title: 'Stock adjusted successfully' })
            }}
            fallbackComponent={
              <RawMaterialForm
                isOpen={true}
                onClose={() => setShowRawMaterialForm(false)}
                onSuccess={() => {
                  fetchRawMaterials()
                  setShowRawMaterialForm(false)
                }}
              />
            }
          />

          <DynamicFormModal
            isOpen={showCreateMaterialForm}
            onClose={() => setShowCreateMaterialForm(false)}
            formSlug="raw_materials_create"
            title="Create Raw Material"
            onSuccess={(result) => {
              fetchRawMaterials()
              fetchRawMaterialsOverview()
              addToast({ type: 'success', title: 'Material created successfully' })
              // Auto-select the newly created material for quick adjust
              if (result?.result_id) {
                setSelectedMaterialId(result.result_id)
              }
            }}
          />
        </>
      ) : (
        <>
          <SalesForm
            isOpen={showSalesForm}
            onClose={() => setShowSalesForm(false)}
            onSuccess={() => {
              fetchSummary()
              fetchInventoryItems()
              fetchLowStock()
            }}
          />
          
          <InventoryForm
            isOpen={showInventoryForm}
            onClose={() => setShowInventoryForm(false)}
            onSuccess={() => {
              fetchInventoryItems()
              fetchLowStock()
            }}
          />
          
          <RawMaterialForm
            isOpen={showRawMaterialForm}
            onClose={() => setShowRawMaterialForm(false)}
            onSuccess={() => {
              fetchRawMaterials()
            }}
          />
        </>
      )}
      
      {/* Product Details Drawer */}
      <ProductDetailsDrawer
        productId={selectedProductId}
        isOpen={showProductDrawer}
        onClose={() => {
          setShowProductDrawer(false)
          setSelectedProductId(null)
        }}
      />
      
      {/* Raw Material Details Drawer */}
      <RawMaterialDetailsDrawer
        materialId={selectedMaterialId}
        isOpen={showMaterialDrawer}
        onClose={() => {
          setShowMaterialDrawer(false)
          setSelectedMaterialId(null)
        }}
        isAdmin={isAdmin}
        onEdit={isAdmin ? (id: number) => { setSelectedMaterialId(id); setShowRawMaterialForm(true) } : undefined}
        onAdjust={isAdmin ? (id: number) => { setSelectedMaterialId(id); setShowRawMaterialForm(true); } : undefined}
        onDelete={isAdmin ? async (id: number) => {
          if (!confirm('Delete this raw material?')) return
          try {
            await api.delete(`/api/inventory/raw-materials/${id}`)
            fetchRawMaterials()
            setShowMaterialDrawer(false)
            setSelectedMaterialId(null)
          } catch (err) {
            console.error('Failed to delete raw material:', err)
          }
        } : undefined}
      />
    </div>
  )
}

// Overview Tab Component
function OverviewTab({
  summary,
  loading,
  lowStockCount,
  isAdmin,
  rawMaterialsOverview
}: {
  summary: ReturnType<typeof useSalesStore.getState>['summary']
  loading: boolean
  lowStockCount: number
  isAdmin: boolean
  rawMaterialsOverview: {
    total_materials: number
    low_stock_count: number
    total_used: number
    total_added: number
    total_transactions: number
  } | null
}) {
  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 size={32} className="animate-spin text-[#5865f2]" />
      </div>
    )
  }
  
  if (!summary) {
    return (
      <div className="flex flex-col items-center justify-center h-64 text-[#949ba4]">
        <ShoppingCart size={48} className="mb-4 opacity-50" />
        <p>No sales data available</p>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* Summary Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {/* Total Revenue (system-admins only) */}
        <div className="bg-[#2b2d31] rounded-lg p-6 border border-[#1f2023]">
          <div className="flex items-center justify-between mb-2">
            <span className="text-[#949ba4] text-sm">Total Revenue</span>
            <DollarSign size={20} className="text-green-400" />
          </div>
          <p className="text-3xl font-bold text-white">
            {isAdmin ? formatGMD(summary.total_revenue) : '—'}
          </p>
        </div>
        
        {/* Total Sales */}
        <div className="bg-[#2b2d31] rounded-lg p-6 border border-[#1f2023]">
          <div className="flex items-center justify-between mb-2">
            <span className="text-[#949ba4] text-sm">Total Sales</span>
            <ShoppingCart size={20} className="text-blue-400" />
          </div>
          <p className="text-3xl font-bold text-white">
            {summary.total_sales.toLocaleString()}
          </p>
        </div>
        
        {/* Low Stock Alert */}
        <div className="bg-[#2b2d31] rounded-lg p-6 border border-[#1f2023]">
          <div className="flex items-center justify-between mb-2">
            <span className="text-[#949ba4] text-sm">Low Stock Items</span>
            <AlertTriangle size={20} className={lowStockCount > 0 ? 'text-yellow-400' : 'text-green-400'} />
          </div>
          <p className={clsx(
            'text-3xl font-bold',
            lowStockCount > 0 ? 'text-yellow-400' : 'text-green-400'
          )}>
            {lowStockCount}
          </p>
        </div>
      </div>
      
      {/* Sales by Channel */}
      <div className="bg-[#2b2d31] rounded-lg p-6 border border-[#1f2023]">
        <h3 className="text-white font-semibold mb-4">Sales by Channel</h3>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {(Object.entries(summary.sales_by_channel) as [SalesChannel, { count: number; revenue: number }][]).map(
            ([channel, data]) => {
              const config = channelConfig[channel]
              return (
                <div key={channel} className="bg-[#1e1f22] rounded-lg p-4">
                  <div className="flex items-center gap-2 mb-3">
                    <div className={clsx('w-3 h-3 rounded-full', config.color)} />
                    <span className="text-white font-medium">{config.label}</span>
                  </div>
                  <div className="space-y-1">
                    <p className="text-2xl font-bold text-white">
                      {isAdmin ? formatGMD(data.revenue) : '—'}
                    </p>
                    <p className="text-sm text-[#949ba4]">
                      {data.count.toLocaleString()} sales
                    </p>
                  </div>
                </div>
              )
            }
          )}
        </div>
      </div>
      
      {/* Raw Materials Overview - Admin Only */}
      {isAdmin && rawMaterialsOverview && (
        <div className="bg-[#2b2d31] rounded-lg p-6 border border-[#1f2023]">
          <div className="flex items-center gap-2 mb-4">
            <Boxes size={20} className="text-purple-400" />
            <h3 className="text-white font-semibold">Raw Materials Overview</h3>
          </div>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            {/* Total Materials */}
            <div className="bg-[#1e1f22] rounded-lg p-4">
              <p className="text-[#949ba4] text-sm mb-1">Total Materials</p>
              <p className="text-2xl font-bold text-white">
                {rawMaterialsOverview.total_materials}
              </p>
            </div>
            {/* Low Stock */}
            <div className="bg-[#1e1f22] rounded-lg p-4">
              <p className="text-[#949ba4] text-sm mb-1">Low Stock</p>
              <p className={clsx(
                'text-2xl font-bold',
                rawMaterialsOverview.low_stock_count > 0 ? 'text-yellow-400' : 'text-green-400'
              )}>
                {rawMaterialsOverview.low_stock_count}
              </p>
            </div>
            {/* Total Added */}
            <div className="bg-[#1e1f22] rounded-lg p-4">
              <p className="text-[#949ba4] text-sm mb-1">Total Added</p>
              <p className="text-2xl font-bold text-green-400">
                +{rawMaterialsOverview.total_added.toLocaleString()}
              </p>
            </div>
            {/* Total Used */}
            <div className="bg-[#1e1f22] rounded-lg p-4">
              <p className="text-[#949ba4] text-sm mb-1">Total Used</p>
              <p className="text-2xl font-bold text-red-400">
                -{rawMaterialsOverview.total_used.toLocaleString()}
              </p>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

// Agents Tab Component
function AgentsTab({
  agents,
  loading,
  isAdmin
}: {
  agents: ReturnType<typeof useSalesStore.getState>['agentPerformance']
  loading: boolean
  isAdmin: boolean
}) {
  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 size={32} className="animate-spin text-[#5865f2]" />
      </div>
    )
  }
  
  if (agents.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center h-64 text-[#949ba4]">
        <Users size={48} className="mb-4 opacity-50" />
        <p>No agent performance data available</p>
      </div>
    )
  }

  // Sort by revenue for admins, otherwise sort by total_sales to avoid leaking revenue info
  const sortedAgents = [...agents].sort((a, b) => {
    if (isAdmin) return Number(b.revenue ?? 0) - Number(a.revenue ?? 0)
    return Number(b.total_sales ?? 0) - Number(a.total_sales ?? 0)
  })

  return (
    <div className="bg-[#2b2d31] rounded-lg border border-[#1f2023] overflow-hidden">
      <table className="w-full">
        <thead>
          <tr className="border-b border-[#1f2023]">
            <th className="text-left text-[#949ba4] text-sm font-medium px-4 py-3">Rank</th>
            <th className="text-left text-[#949ba4] text-sm font-medium px-4 py-3">Agent</th>
            <th className="text-right text-[#949ba4] text-sm font-medium px-4 py-3">Sales</th>
            <th className="text-right text-[#949ba4] text-sm font-medium px-4 py-3">Units Sold</th>
            {isAdmin && (
              <th className="text-right text-[#949ba4] text-sm font-medium px-4 py-3">Revenue</th>
            )}
          </tr>
        </thead>
        <tbody>
          {sortedAgents.map((agent, index) => (
            <tr key={agent.agent_id} className="border-b border-[#1f2023] last:border-0 hover:bg-[#35373c]">
              <td className="px-4 py-3">
                <span className={clsx(
                  'w-6 h-6 rounded-full flex items-center justify-center text-xs font-bold',
                  index === 0 ? 'bg-yellow-500 text-black' :
                  index === 1 ? 'bg-gray-400 text-black' :
                  index === 2 ? 'bg-orange-600 text-white' :
                  'bg-[#1e1f22] text-[#949ba4]'
                )}>
                  {index + 1}
                </span>
              </td>
              <td className="px-4 py-3">
                <span className="text-white font-medium">{agent.agent_name || 'Unknown'}</span>
              </td>
              <td className="px-4 py-3 text-right text-white">
                {Number(agent.total_sales ?? 0).toLocaleString()}
              </td>
              <td className="px-4 py-3 text-right text-white">
                {Number(agent.units_sold ?? 0).toLocaleString()}
              </td>
              {isAdmin && (
                <td className="px-4 py-3 text-right">
                  <span className="text-green-400 font-semibold">
                    {formatGMD(agent.revenue)}
                  </span>
                </td>
              )}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

// Inventory Tab Component
function InventoryTab({
  items,
  lowStockItems,
  loading,
  highlightProductId = null,
  onItemClick
}: {
  items: ReturnType<typeof useInventoryStore.getState>['items']
  lowStockItems: ReturnType<typeof useInventoryStore.getState>['lowStockItems']
  loading: boolean
  highlightProductId?: number | null
  onItemClick?: (productId: number) => void
}) {
  const [showLowOnly, setShowLowOnly] = useState(false)
  const highlightRef = React.useRef<HTMLDivElement>(null)

  // Scroll to highlighted item once loaded
  useEffect(() => {
    if (highlightProductId && highlightRef.current) {
      highlightRef.current.scrollIntoView({ behavior: 'smooth', block: 'center' })
    }
  }, [highlightProductId, loading])
  
  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 size={32} className="animate-spin text-[#5865f2]" />
      </div>
    )
  }
  
  const displayItems = showLowOnly ? lowStockItems : items
  
  if (displayItems.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center h-64 text-[#949ba4]">
        <Package size={48} className="mb-4 opacity-50" />
        <p>{showLowOnly ? 'No low stock items' : 'No inventory data available'}</p>
      </div>
    )
  }

  return (
    <div className="space-y-4">
      {/* Filter Toggle */}
      <div className="flex items-center gap-4">
        <button
          onClick={() => setShowLowOnly(false)}
          className={clsx(
            'px-4 py-2 rounded-lg text-sm font-medium transition-colors',
            !showLowOnly
              ? 'bg-[#5865f2] text-white'
              : 'bg-[#2b2d31] text-[#949ba4] hover:text-white'
          )}
        >
          All Items ({items.length})
        </button>
        <button
          onClick={() => setShowLowOnly(true)}
          className={clsx(
            'px-4 py-2 rounded-lg text-sm font-medium transition-colors flex items-center gap-2',
            showLowOnly
              ? 'bg-yellow-500 text-black'
              : 'bg-[#2b2d31] text-[#949ba4] hover:text-white'
          )}
        >
          <AlertTriangle size={14} />
          Low Stock ({lowStockItems.length})
        </button>
      </div>
      
      {/* Inventory Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {displayItems.map((item) => {
          const statusConfig = stockStatusConfig[item.status]
          const StatusIcon = statusConfig.icon
          const isHighlighted = highlightProductId != null && item.product_id === highlightProductId
          
          return (
            <div
              key={item.id}
              ref={isHighlighted ? highlightRef : undefined}
              onClick={() => onItemClick?.(item.product_id)}
              className={clsx(
                'bg-[#2b2d31] rounded-lg p-4 border cursor-pointer hover:bg-[#35373c] transition-colors',
                isHighlighted && 'ring-1 ring-[#5865f2] bg-[#5865f2]/10 animate-pulse',
                !isHighlighted && (
                  item.status === 'critical' ? 'border-red-500/50' :
                  item.status === 'low' ? 'border-yellow-500/50' :
                  'border-[#1f2023]'
                )
              )}
            >
              <div className="flex items-start justify-between mb-3">
                <div>
                  <h4 className="text-white font-medium">{item.product_name}</h4>
                  <p className="text-[#949ba4] text-sm">ID: {item.product_id}</p>
                </div>
                <div className={clsx(
                  'px-2 py-1 rounded-full text-xs font-medium flex items-center gap-1',
                  statusConfig.bgColor,
                  statusConfig.color
                )}>
                  <StatusIcon size={12} />
                  {statusConfig.label}
                </div>
              </div>
              
              <div className="space-y-2">
                <div className="flex justify-between">
                  <span className="text-[#949ba4] text-sm">Current Stock</span>
                  <span className={clsx(
                    'font-semibold',
                    item.status === 'critical' ? 'text-red-400' :
                    item.status === 'low' ? 'text-yellow-400' :
                    'text-white'
                  )}>
                    {item.current_stock.toLocaleString()}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-[#949ba4] text-sm">Threshold</span>
                  <span className="text-[#949ba4]">{item.low_stock_threshold}</span>
                </div>
                
                {/* Stock bar */}
                <div className="h-2 bg-[#1e1f22] rounded-full overflow-hidden">
                  <div
                    className={clsx(
                      'h-full rounded-full transition-all',
                      item.status === 'critical' ? 'bg-red-500' :
                      item.status === 'low' ? 'bg-yellow-500' :
                      'bg-green-500'
                    )}
                    style={{
                      width: `${Math.min(100, (item.current_stock / (item.low_stock_threshold * 3)) * 100)}%`
                    }}
                  />
                </div>
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}

// Transactions Tab Component
function TransactionsTab({
  transactions,
  loading,
  isAdmin = false,
  highlightId = null
}: {
  transactions: ReturnType<typeof useInventoryStore.getState>['transactions']
  loading: boolean
  isAdmin?: boolean
  highlightId?: number | null
}) {
  const { reverseTransaction } = useInventoryStore()
  const { addToast } = useNotificationContext()
  const [reversingId, setReversingId] = useState<number | null>(null)
  const [confirmId, setConfirmId] = useState<number | null>(null)
  const [filter, setFilter] = useState<'all' | 'sales' | 'reversals'>('all')
  const highlightRef = React.useRef<HTMLTableRowElement>(null)

  // Scroll to highlighted row once loaded
  useEffect(() => {
    if (highlightId && highlightRef.current) {
      highlightRef.current.scrollIntoView({ behavior: 'smooth', block: 'center' })
    }
  }, [highlightId, loading])

  // Build a set of transaction IDs that have been reversed
  const reversedIds = new Set(
    transactions
      .filter(tx => tx.reference_transaction_id != null)
      .map(tx => tx.reference_transaction_id!)
  )
  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 size={32} className="animate-spin text-[#5865f2]" />
      </div>
    )
  }
  
  if (transactions.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center h-64 text-[#949ba4]">
        <Calendar size={48} className="mb-4 opacity-50" />
        <p>No transaction history available</p>
      </div>
    )
  }

  // Reason badge colors
  const reasonColors: Record<string, string> = {
    'sale': 'bg-blue-500/10 text-blue-400',
    'restock': 'bg-green-500/10 text-green-400',
    'adjustment': 'bg-yellow-500/10 text-yellow-400',
    'return': 'bg-purple-500/10 text-purple-400',
    'reversal': 'bg-orange-500/10 text-orange-400'
  }

  const handleReverse = async (txId: number) => {
    setReversingId(txId)
    setConfirmId(null)
    try {
      await reverseTransaction(txId)
      addToast({ type: 'success', title: 'Transaction reversed successfully' })
    } catch (err: any) {
      const msg = err?.response?.data?.detail || 'Failed to reverse transaction'
      addToast({ type: 'error', title: msg })
    } finally {
      setReversingId(null)
    }
  }

  const filteredTransactions = transactions.filter(tx => {
    if (filter === 'sales') return !tx.reference_transaction_id && tx.change < 0
    if (filter === 'reversals') return !!tx.reference_transaction_id
    return true
  })

  const counts = {
    all: transactions.length,
    sales: transactions.filter(tx => !tx.reference_transaction_id && tx.change < 0).length,
    reversals: transactions.filter(tx => !!tx.reference_transaction_id).length,
  }

  // Group transactions: parent rows with nested reversal children
  type GroupedTx = typeof transactions[number] & { children: typeof transactions }
  const grouped: Record<number, GroupedTx> = {}
  const orphans: typeof transactions = []

  for (const tx of filteredTransactions) {
    if (!tx.reference_transaction_id) {
      grouped[tx.id] = { ...tx, children: [] }
    }
  }
  for (const tx of filteredTransactions) {
    if (tx.reference_transaction_id) {
      const parent = grouped[tx.reference_transaction_id]
      if (parent) {
        parent.children.push(tx)
      } else {
        orphans.push(tx) // parent filtered out — render standalone
      }
    }
  }
  const groupedList = [...Object.values(grouped), ...orphans.map(tx => ({ ...tx, children: [] as typeof transactions }))]
    .sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime())

  const renderRow = (tx: typeof transactions[number], isChild: boolean) => {
    const isHighlighted = highlightId != null && tx.id === highlightId
    return (
    <tr
      key={tx.id}
      ref={isHighlighted ? highlightRef : undefined}
      className={clsx(
        'border-b border-[#1f2023] last:border-0 transition-colors duration-700',
        isChild ? 'bg-[#25262a]' : 'hover:bg-[#35373c]',
        !isChild && reversedIds.has(tx.id) && 'opacity-50',
        isHighlighted && 'ring-1 ring-[#5865f2] bg-[#5865f2]/10 animate-pulse',
      )}
    >
      <td className="px-4 py-3">
        {isChild ? (
          <span className="inline-flex items-center gap-1 text-[#949ba4] text-sm pl-4">
            <span className="text-[#5c5e66]">↳</span>
            {tx.product_name}
          </span>
        ) : (
          <span className="text-white">{tx.product_name}</span>
        )}
      </td>
      <td className="px-4 py-3 text-center">
        <span className={clsx(
          'inline-flex items-center gap-1 font-semibold',
          isChild ? 'text-sm' : '',
          tx.change > 0 ? 'text-green-400' : 'text-red-400'
        )}>
          {tx.change > 0 ? (
            <>
              <ArrowUpRight size={isChild ? 12 : 14} />
              +{tx.change}
            </>
          ) : (
            <>
              <ArrowDownRight size={isChild ? 12 : 14} />
              {tx.change}
            </>
          )}
        </span>
      </td>
      <td className="px-4 py-3 text-center">
        <span className={clsx(
          'px-2 py-1 rounded-full text-xs font-medium capitalize',
          reasonColors[tx.reason] || 'bg-gray-500/10 text-gray-400'
        )}>
          {tx.reason}
          {!isChild && reversedIds.has(tx.id) && ' (Reversed)'}
        </span>
      </td>
      <td className={clsx('px-4 py-3 text-center text-sm', isChild ? 'text-[#5c5e66]' : 'text-[#949ba4]')}>
        {tx.created_by?.display_name || tx.created_by?.username || 'System'}
      </td>
      <td className={clsx('px-4 py-3 text-right text-sm', isChild ? 'text-[#5c5e66]' : 'text-[#949ba4]')}>
        {formatDateTime(tx.created_at)}
      </td>
      {isAdmin && (
        <td className="px-4 py-3 text-center">
          {!isChild && tx.reason !== 'reversal' && !reversedIds.has(tx.id) ? (
            confirmId === tx.id ? (
              <div className="inline-flex items-center gap-1">
                <button
                  onClick={() => handleReverse(tx.id)}
                  disabled={reversingId === tx.id}
                  className="px-2 py-1 text-xs font-medium rounded bg-red-500/20 text-red-400 hover:bg-red-500/30 disabled:opacity-50"
                >
                  {reversingId === tx.id ? <Loader2 size={12} className="animate-spin" /> : 'Confirm'}
                </button>
                <button
                  onClick={() => setConfirmId(null)}
                  className="px-2 py-1 text-xs font-medium rounded bg-gray-500/20 text-gray-400 hover:bg-gray-500/30"
                >
                  Cancel
                </button>
              </div>
            ) : (
              <button
                onClick={() => setConfirmId(tx.id)}
                title="This will create a reversal entry. The original record will remain for audit purposes."
                className="inline-flex items-center gap-1 px-2 py-1 text-xs font-medium rounded text-[#949ba4] hover:bg-[#3f4147] hover:text-white"
              >
                <RotateCcw size={12} />
                Reverse
              </button>
            )
          ) : (
            <span className="text-xs text-[#5c5e66]">—</span>
          )}
        </td>
      )}
    </tr>
  )}

  return (
    <div>
      <div className="flex items-center gap-1 mb-3">
        {(['all', 'sales', 'reversals'] as const).map(f => (
          <button
            key={f}
            onClick={() => setFilter(f)}
            className={clsx(
              'px-3 py-1.5 text-xs font-medium rounded transition-colors capitalize',
              filter === f
                ? 'bg-[#5865f2] text-white'
                : 'text-[#949ba4] hover:text-white hover:bg-[#35373c]'
            )}
          >
            {f} ({counts[f]})
          </button>
        ))}
      </div>
      <div className="bg-[#2b2d31] rounded-lg border border-[#1f2023] overflow-hidden">
      <table className="w-full">
        <thead>
          <tr className="border-b border-[#1f2023]">
            <th className="text-left text-[#949ba4] text-sm font-medium px-4 py-3">Product</th>
            <th className="text-center text-[#949ba4] text-sm font-medium px-4 py-3">Change</th>
            <th className="text-center text-[#949ba4] text-sm font-medium px-4 py-3">Reason</th>
            <th className="text-center text-[#949ba4] text-sm font-medium px-4 py-3">By</th>
            <th className="text-right text-[#949ba4] text-sm font-medium px-4 py-3">Date</th>
            {isAdmin && <th className="text-center text-[#949ba4] text-sm font-medium px-4 py-3">Action</th>}
          </tr>
        </thead>
        <tbody>
          {groupedList.map((parent) => (
            <React.Fragment key={parent.id}>
              {renderRow(parent, false)}
              {parent.children.map(child => renderRow(child, true))}
            </React.Fragment>
          ))}
        </tbody>
      </table>
    </div>
    </div>
  )
}

// Raw Materials Tab Component
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

function RawMaterialsTab({
  materials,
  loading,
  isAdmin,
  onCreateClick,
  onAddClick,
  onRefresh,
  onItemClick,
  onEdit,
  onAdjust,
  onDelete,
}: {
  materials: RawMaterial[]
  loading: boolean
  isAdmin?: boolean
  onCreateClick?: () => void
  onAddClick?: () => void
  onRefresh?: () => void
  onItemClick?: (materialId: number) => void
  onEdit?: (materialId: number) => void
  onAdjust?: (materialId: number) => void
  onDelete?: (materialId: number) => void
}) {
  if (loading) {
    return (
      <div className="flex items-center justify-center py-12">
        <Loader2 className="animate-spin text-[#5865f2]" size={32} />
      </div>
    )
  }

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h3 className="text-lg font-semibold text-white flex items-center gap-2">
          <Boxes size={20} className="text-amber-400" />
          Raw Materials
          <span className="text-sm text-[#949ba4] font-normal">({materials.length})</span>
        </h3>
        <div className="flex items-center gap-2">
          {onRefresh && (
            <button
              onClick={onRefresh}
              className="px-3 py-1.5 text-sm text-[#949ba4] hover:text-white transition-colors"
            >
              <RefreshCw size={16} />
            </button>
          )}
          {onCreateClick && (
            <button
              onClick={onCreateClick}
              className="flex items-center gap-1.5 px-3 py-1.5 text-sm bg-green-600 hover:bg-green-700 text-white rounded-lg transition-colors"
            >
              <Plus size={14} />
              Create Material
            </button>
          )}
          {onAddClick && (
            <button
              onClick={onAddClick}
              className="flex items-center gap-1.5 px-3 py-1.5 text-sm bg-amber-600 hover:bg-amber-700 text-white rounded-lg transition-colors"
            >
              <RotateCcw size={14} />
              Adjust Stock
            </button>
          )}
        </div>
      </div>
      
      {/* Empty State */}
      {materials.length === 0 ? (
        <div className="bg-[#2b2d31] rounded-lg border border-[#1f2023] p-8 text-center">
          <Boxes size={48} className="mx-auto text-[#949ba4] mb-4" />
          <p className="text-white font-medium mb-2">No raw materials yet</p>
          <p className="text-[#949ba4] text-sm mb-4">
            Create your first material to start tracking stock
          </p>
          {onCreateClick && (
            <button
              onClick={onCreateClick}
              className="flex items-center gap-1.5 mx-auto px-4 py-2 bg-green-600 hover:bg-green-700 text-white rounded-lg text-sm transition-colors"
            >
              <Plus size={14} />
              Create Material
            </button>
          )}
        </div>
      ) : (
        <div className="bg-[#2b2d31] rounded-lg border border-[#1f2023] overflow-hidden">
          <table className="w-full">
            <thead>
              <tr className="border-b border-[#1f2023]">
                <th className="text-left text-[#949ba4] text-sm font-medium px-4 py-3">Material</th>
                <th className="text-center text-[#949ba4] text-sm font-medium px-4 py-3">Stock</th>
                <th className="text-center text-[#949ba4] text-sm font-medium px-4 py-3">Unit</th>
                <th className="text-center text-[#949ba4] text-sm font-medium px-4 py-3">Status</th>
                <th className="text-right text-[#949ba4] text-sm font-medium px-4 py-3">Supplier</th>
                {(onEdit || onAdjust || onDelete) && <th className="text-right text-[#949ba4] text-sm font-medium px-4 py-3">Actions</th>}
              </tr>
            </thead>
            <tbody>
              {materials.map((material) => {
                const isLowStock = material.current_stock <= material.min_stock_level
                return (
                  <tr 
                    key={material.id} 
                    className="border-b border-[#1f2023] last:border-0 hover:bg-[#35373c] cursor-pointer"
                    onClick={() => onItemClick && onItemClick(material.id)}
                  >
                    <td className="px-4 py-3">
                      <div>
                        <span className="text-white font-medium">{material.name}</span>
                        {material.description && (
                          <p className="text-xs text-[#949ba4] mt-0.5">{material.description}</p>
                        )}
                      </div>
                    </td>
                    <td className="px-4 py-3 text-center">
                      <span className={clsx(
                        'font-semibold',
                        isLowStock ? 'text-yellow-400' : 'text-white'
                      )}>
                        {material.current_stock.toLocaleString()}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-center text-[#b5bac1]">
                      {material.unit}
                    </td>
                    <td className="px-4 py-3 text-center">
                    </td>
                    <td className="px-4 py-3 text-center">
                      {isLowStock ? (
                        <span className="inline-flex items-center gap-1 px-2 py-1 rounded-full text-xs font-medium bg-yellow-400/10 text-yellow-400">
                          <AlertTriangle size={12} />
                          Low Stock
                        </span>
                      ) : (
                        <span className="inline-flex items-center gap-1 px-2 py-1 rounded-full text-xs font-medium bg-green-400/10 text-green-400">
                          <CheckCircle size={12} />
                          In Stock
                        </span>
                      )}
                    </td>
                    <td className="px-4 py-3 text-right text-[#949ba4] text-sm">
                      {material.supplier || '—'}
                    </td>
                    {(onEdit || onAdjust || onDelete) && (
                      <td className="px-4 py-3 text-right text-sm flex items-center gap-2">
                        {onEdit && (
                          <button
                            onClick={(e) => { e.stopPropagation(); onEdit(material.id) }}
                            title="Edit"
                            className="px-2 py-1 bg-[#4f545c] hover:bg-[#5d6269] text-white rounded"
                          >
                            <Pencil size={14} />
                          </button>
                        )}
                        {onAdjust && (
                          <button
                            onClick={(e) => { e.stopPropagation(); onAdjust(material.id) }}
                            title="Adjust Stock"
                            className="px-2 py-1 bg-amber-600 hover:bg-amber-700 text-white rounded text-xs flex items-center gap-1"
                          >
                            <RotateCcw size={12} />
                            Adjust
                          </button>
                        )}
                        {onDelete && (
                          <button
                            onClick={(e) => { e.stopPropagation(); onDelete(material.id) }}
                            title="Delete"
                            className="px-2 py-1 bg-red-600 hover:bg-red-700 text-white rounded"
                          >
                            <Trash size={14} />
                          </button>
                        )}
                      </td>
                    )}
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      )}
      
      {/* Low Stock Summary */}
      {materials.filter(m => m.current_stock <= m.min_stock_level).length > 0 && (
        <div className="bg-yellow-400/10 border border-yellow-400/20 rounded-lg p-4">
          <div className="flex items-center gap-2 text-yellow-400 mb-2">
            <AlertTriangle size={16} />
            <span className="font-medium">Low Stock Alert</span>
          </div>
          <p className="text-[#b5bac1] text-sm">
            {materials.filter(m => m.current_stock <= m.min_stock_level).length} material(s) below minimum stock level:
          </p>
          <ul className="mt-2 text-sm text-[#949ba4]">
            {materials.filter(m => m.current_stock <= m.min_stock_level).map(m => (
              <li key={m.id}>• {m.name}: {m.current_stock} {m.unit} (min: {m.min_stock_level})</li>
            ))}
          </ul>
        </div>
      )}
    </div>
  )
}

// Export forms for use in SalesPage
export { SalesForm, InventoryForm, RawMaterialForm }
