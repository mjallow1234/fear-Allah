/**
 * Sales Page
 * Phase 7.4 - Sales UI
 * 
 * Displays sales overview, agent performance, inventory status,
 * raw materials management, and transaction history.
 */
import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
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
  Boxes
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
import api from '../services/api'

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
  const [activeTab, setActiveTab] = useState<TabType>('overview')
  const [showSalesForm, setShowSalesForm] = useState(false)
  const [showInventoryForm, setShowInventoryForm] = useState(false)
  const [showRawMaterialForm, setShowRawMaterialForm] = useState(false)
  // Use dynamic forms when available (toggle _setUseDynamicForms to false for legacy forms)
  const [useDynamicForms, _setUseDynamicForms] = useState(true)
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
  const user = useAuthStore((state) => state.user)
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
  
  // Determine if user is admin (can see all data including agent performance and transactions)
  const isAdmin = user?.is_system_admin === true
  
  // Fetch raw materials
  const fetchRawMaterials = async () => {
    if (!isAdmin) return
    setLoadingRawMaterials(true)
    try {
      const response = await api.get('/api/inventory/raw-materials/')
      setRawMaterials(response.data.items || response.data || [])
    } catch (err) {
      console.error('Failed to fetch raw materials:', err)
    } finally {
      setLoadingRawMaterials(false)
    }
  }
  
  // Fetch raw materials overview stats (admin only)
  const fetchRawMaterialsOverview = async () => {
    if (!isAdmin) return
    try {
      const response = await api.get('/api/inventory/raw-materials/overview/stats')
      setRawMaterialsOverview(response.data)
    } catch (err) {
      console.error('Failed to fetch raw materials overview:', err)
    }
  }
  
  // Fetch data on mount - only fetch admin-restricted data if user is admin
  useEffect(() => {
    // Sales: Summary is available to all, agent performance is admin-only
    fetchSummary()
    if (isAdmin) {
      fetchAgentPerformance()
      fetchRawMaterials()
      fetchRawMaterialsOverview()
    }
    
    // Inventory: Items and low stock available to all, transactions are admin-only
    fetchInventoryItems()
    fetchLowStock()
    if (isAdmin) {
      fetchTransactions()
    }
  }, [isAdmin])
  
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
  
  // Date range filter buttons
  const dateRanges: { value: DateRangeFilter; label: string }[] = [
    { value: 'today', label: 'Today' },
    { value: 'week', label: 'This Week' },
    { value: 'month', label: 'This Month' }
  ]

  return (
    <div className="flex flex-col h-full bg-[#313338]">
      {/* Header */}
      <div className="h-12 border-b border-[#1f2023] flex items-center px-4 justify-between flex-shrink-0">
        <div className="flex items-center gap-3">
          <button
            onClick={() => navigate(-1)}
            className="p-1 text-[#949ba4] hover:text-white transition-colors"
          >
            <ArrowLeft size={20} />
          </button>
          <DollarSign size={20} className="text-green-400" />
          <span className="text-white font-semibold">Sales & Inventory</span>
        </div>
        
        <div className="flex items-center gap-4">
          {/* Action Buttons */}
          <div className="flex items-center gap-2">
            <button
              onClick={() => setShowSalesForm(true)}
              className="flex items-center gap-1.5 px-3 py-1.5 text-sm bg-green-600 hover:bg-green-700 text-white rounded-lg transition-colors"
            >
              <Plus size={14} />
              Record Sale
            </button>
            <button
              onClick={() => setShowInventoryForm(true)}
              className="flex items-center gap-1.5 px-3 py-1.5 text-sm bg-blue-600 hover:bg-blue-700 text-white rounded-lg transition-colors"
            >
              <Package size={14} />
              Manage Inventory
            </button>
          </div>
          
          {/* Date Range Filter */}
          <div className="flex items-center gap-1 bg-[#1e1f22] rounded-lg p-1">
            {dateRanges.map(({ value, label }) => (
              <button
                key={value}
                onClick={() => setDateRange(value)}
                className={clsx(
                  'px-3 py-1 text-sm rounded-md transition-colors',
                  dateRange === value
                    ? 'bg-[#5865f2] text-white'
                    : 'text-[#949ba4] hover:text-white hover:bg-[#35373c]'
                )}
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
              onAddClick={isAdmin ? () => setShowRawMaterialForm(true) : undefined}
              onRefresh={fetchRawMaterials}
              onItemClick={(materialId) => {
                setSelectedMaterialId(materialId)
                setShowMaterialDrawer(true)
              }}
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
            }}
            fallbackComponent={
              <SalesForm
                isOpen={true}
                onClose={() => setShowSalesForm(false)}
                onSuccess={() => {
                  fetchSummary()
                  fetchInventoryItems()
                  fetchLowStock()
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
            title="Raw Materials"
            onSuccess={() => {
              fetchRawMaterials()
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
        {/* Total Revenue */}
        <div className="bg-[#2b2d31] rounded-lg p-6 border border-[#1f2023]">
          <div className="flex items-center justify-between mb-2">
            <span className="text-[#949ba4] text-sm">Total Revenue</span>
            <DollarSign size={20} className="text-green-400" />
          </div>
          <p className="text-3xl font-bold text-white">
            {formatGMD(summary.total_revenue)}
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
                      {formatGMD(data.revenue)}
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
  loading
}: {
  agents: ReturnType<typeof useSalesStore.getState>['agentPerformance']
  loading: boolean
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

  // Sort by revenue descending (with safe fallback for undefined values)
  const sortedAgents = [...agents].sort((a, b) => Number(b.revenue ?? 0) - Number(a.revenue ?? 0))

  return (
    <div className="bg-[#2b2d31] rounded-lg border border-[#1f2023] overflow-hidden">
      <table className="w-full">
        <thead>
          <tr className="border-b border-[#1f2023]">
            <th className="text-left text-[#949ba4] text-sm font-medium px-4 py-3">Rank</th>
            <th className="text-left text-[#949ba4] text-sm font-medium px-4 py-3">Agent</th>
            <th className="text-right text-[#949ba4] text-sm font-medium px-4 py-3">Sales</th>
            <th className="text-right text-[#949ba4] text-sm font-medium px-4 py-3">Units Sold</th>
            <th className="text-right text-[#949ba4] text-sm font-medium px-4 py-3">Revenue</th>
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
              <td className="px-4 py-3 text-right">
                <span className="text-green-400 font-semibold">
                  {formatGMD(agent.revenue)}
                </span>
              </td>
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
  onItemClick
}: {
  items: ReturnType<typeof useInventoryStore.getState>['items']
  lowStockItems: ReturnType<typeof useInventoryStore.getState>['lowStockItems']
  loading: boolean
  onItemClick?: (productId: number) => void
}) {
  const [showLowOnly, setShowLowOnly] = useState(false)
  
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
          
          return (
            <div
              key={item.id}
              onClick={() => onItemClick?.(item.product_id)}
              className={clsx(
                'bg-[#2b2d31] rounded-lg p-4 border cursor-pointer hover:bg-[#35373c] transition-colors',
                item.status === 'critical' ? 'border-red-500/50' :
                item.status === 'low' ? 'border-yellow-500/50' :
                'border-[#1f2023]'
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
  loading
}: {
  transactions: ReturnType<typeof useInventoryStore.getState>['transactions']
  loading: boolean
}) {
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
    'return': 'bg-purple-500/10 text-purple-400'
  }

  return (
    <div className="bg-[#2b2d31] rounded-lg border border-[#1f2023] overflow-hidden">
      <table className="w-full">
        <thead>
          <tr className="border-b border-[#1f2023]">
            <th className="text-left text-[#949ba4] text-sm font-medium px-4 py-3">Product</th>
            <th className="text-center text-[#949ba4] text-sm font-medium px-4 py-3">Change</th>
            <th className="text-center text-[#949ba4] text-sm font-medium px-4 py-3">Reason</th>
            <th className="text-right text-[#949ba4] text-sm font-medium px-4 py-3">Date</th>
          </tr>
        </thead>
        <tbody>
          {transactions.map((tx) => (
            <tr key={tx.id} className="border-b border-[#1f2023] last:border-0 hover:bg-[#35373c]">
              <td className="px-4 py-3">
                <span className="text-white">{tx.product_name}</span>
              </td>
              <td className="px-4 py-3 text-center">
                <span className={clsx(
                  'inline-flex items-center gap-1 font-semibold',
                  tx.change > 0 ? 'text-green-400' : 'text-red-400'
                )}>
                  {tx.change > 0 ? (
                    <>
                      <ArrowUpRight size={14} />
                      +{tx.change}
                    </>
                  ) : (
                    <>
                      <ArrowDownRight size={14} />
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
                </span>
              </td>
              <td className="px-4 py-3 text-right text-[#949ba4] text-sm">
                {formatDateTime(tx.created_at)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
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
  onAddClick,
  onRefresh,
  onItemClick,
}: {
  materials: RawMaterial[]
  loading: boolean
  onAddClick?: () => void
  onRefresh?: () => void
  onItemClick?: (materialId: number) => void
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
          {onAddClick && (
            <button
              onClick={onAddClick}
              className="flex items-center gap-1.5 px-3 py-1.5 text-sm bg-amber-600 hover:bg-amber-700 text-white rounded-lg transition-colors"
            >
              <Plus size={14} />
              Add Material
            </button>
          )}
        </div>
      </div>
      
      {/* Empty State */}
      {materials.length === 0 ? (
        <div className="bg-[#2b2d31] rounded-lg border border-[#1f2023] p-8 text-center">
          <Boxes size={48} className="mx-auto text-[#949ba4] mb-4" />
          <p className="text-white font-medium mb-2">No Raw Materials</p>
          <p className="text-[#949ba4] text-sm mb-4">
            Add raw materials to track ingredients, supplies, and production inputs.
          </p>
          {onAddClick && (
            <button
              onClick={onAddClick}
              className="px-4 py-2 bg-amber-600 hover:bg-amber-700 text-white rounded-lg text-sm transition-colors"
            >
              Add First Material
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
