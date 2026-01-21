/**
 * Inventory Store for inventory data management.
 * Phase 7.4 - Sales UI
 * 
 * Manages inventory status and transaction history.
 */
import { create } from 'zustand'
import api from '../services/api'
import useOperationalPermissions from '../permissions/useOperationalPermissions'
import { useAuthStore } from '../stores/authStore'

// Inventory status levels
export type StockStatus = 'healthy' | 'low' | 'critical'

export interface InventoryItem {
  id: number
  product_id: number
  product_name: string
  current_stock: number
  low_stock_threshold: number
  status: StockStatus
}

export interface InventoryTransaction {
  id: number
  product_id: number
  product_name: string
  change: number // positive = add, negative = subtract
  reason: 'sale' | 'restock' | 'adjustment' | 'return' | string
  created_at: string
  notes?: string
}

interface InventoryState {
  // Data
  items: InventoryItem[]
  lowStockItems: InventoryItem[]
  transactions: InventoryTransaction[]
  
  // Loading states
  loadingItems: boolean
  loadingLowStock: boolean
  loadingTransactions: boolean
  
  // Error state
  error: string | null
  
  // Actions
  fetchInventory: () => Promise<void>
  fetchLowStock: () => Promise<void>
  fetchTransactions: () => Promise<void>
  fetchAll: () => Promise<void>
}

// Helper to determine stock status
function getStockStatus(current: number, threshold: number): StockStatus {
  if (current <= 0) return 'critical'
  if (current <= threshold) return 'low'
  return 'healthy'
}

export const useInventoryStore = create<InventoryState>((set, get) => ({
  // Initial state
  items: [],
  lowStockItems: [],
  transactions: [],
  loadingItems: false,
  loadingLowStock: false,
  loadingTransactions: false,
  error: null,
  
  fetchInventory: async () => {
    set({ loadingItems: true, error: null })
    try {
      const response = await api.get(`/api/inventory/`)
      
      // Handle response - may be array or object with items property
      const data = response.data
      const rawItems = Array.isArray(data) ? data : (data.items || [])
      
      // Normalize items and add status - API returns total_stock, not current_stock
      const items: InventoryItem[] = rawItems.map((item: Record<string, unknown>) => {
        const stock = (item.total_stock as number) ?? (item.current_stock as number) ?? (item.quantity as number) ?? 0
        const threshold = (item.low_stock_threshold as number) ?? (item.threshold as number) ?? 10
        return {
          id: item.id as number,
          product_id: item.product_id as number || item.id as number,
          product_name: item.product_name as string || item.name as string || `Product ${item.id}`,
          current_stock: stock,
          low_stock_threshold: threshold,
          status: getStockStatus(stock, threshold)
        }
      })
      
      set({ items, loadingItems: false })
    } catch (error: unknown) {
      console.error('Failed to fetch inventory:', error)
      set({ items: [], loadingItems: false })
    }
  },
  
  fetchLowStock: async () => {
    set({ loadingLowStock: true, error: null })
    try {
      const response = await api.get(`/api/inventory/low-stock`)
      
      const data = response.data
      const rawItems = Array.isArray(data) ? data : (data.items || [])
      
      const lowStockItems: InventoryItem[] = rawItems.map((item: Record<string, unknown>) => {
        const stock = (item.total_stock as number) ?? (item.current_stock as number) ?? (item.quantity as number) ?? 0
        const threshold = (item.low_stock_threshold as number) ?? (item.threshold as number) ?? 10
        return {
          id: item.id as number,
          product_id: item.product_id as number || item.id as number,
          product_name: item.product_name as string || item.name as string || `Product ${item.id}`,
          current_stock: stock,
          low_stock_threshold: threshold,
          status: getStockStatus(stock, threshold)
        }
      })
      
      set({ lowStockItems, loadingLowStock: false })
    } catch (error: unknown) {
      console.error('Failed to fetch low stock items:', error)
      set({ lowStockItems: [], loadingLowStock: false })
    }
  },
  
  fetchTransactions: async () => {
    set({ loadingTransactions: true, error: null })

    // Check operational permissions or allow system admins
    const perms = useOperationalPermissions()
    const currentUser = useAuthStore.getState().currentUser
    if (!perms.sales?.transactions && !currentUser?.is_system_admin) {
      set({ transactions: [], loadingTransactions: false })
      return
    }

    try {
      const response = await api.get(`/api/inventory/transactions`)
      
      const data = response.data
      const rawTransactions = Array.isArray(data) ? data : (data.transactions || [])
      
      const transactions: InventoryTransaction[] = rawTransactions.map((tx: Record<string, unknown>) => ({
        id: tx.id as number,
        product_id: tx.product_id as number,
        product_name: tx.product_name as string || `Product ${tx.product_id}`,
        change: tx.change as number || tx.quantity_change as number || 0,
        reason: tx.reason as string || tx.type as string || 'unknown',
        created_at: tx.created_at as string || new Date().toISOString(),
        notes: tx.notes as string | undefined
      }))
      
      set({ transactions, loadingTransactions: false })
    } catch (error: any) {
      // Avoid noisy console errors for expected forbidden responses
      if (!(error?.response && error.response.status === 403)) {
        console.error('Failed to fetch inventory transactions:', error)
      }
      set({ transactions: [], loadingTransactions: false })
    }
  },
  
  fetchAll: async () => {
    const { fetchInventory, fetchLowStock, fetchTransactions } = get()
    await Promise.all([fetchInventory(), fetchLowStock(), fetchTransactions()])
  }
}))
