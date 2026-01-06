/**
 * Order Store for order management.
 * Phase 7.3 - Order UI
 * 
 * Manages orders and automation status state.
 * Socket.IO only, no polling.
 */
import { create } from 'zustand'
import api from '../services/api'

// Enums matching backend (accept both cases for compatibility)
export type OrderType = 'AGENT_RESTOCK' | 'AGENT_RETAIL' | 'STORE_KEEPER_RESTOCK' | 'CUSTOMER_WHOLESALE' |
                        'agent_restock' | 'agent_retail' | 'store_keeper_restock' | 'customer_wholesale'
export type OrderStatus = 'DRAFT' | 'SUBMITTED' | 'IN_PROGRESS' | 'AWAITING_CONFIRMATION' | 'COMPLETED' | 'CANCELLED' |
                          'draft' | 'submitted' | 'in_progress' | 'awaiting_confirmation' | 'completed' | 'cancelled'

// Normalize status to uppercase for display consistency
export function normalizeStatus(status: string | undefined | null): OrderStatus {
  if (!status) return 'SUBMITTED'
  return status.toUpperCase() as OrderStatus
}

// Normalize order type to uppercase for display consistency
export function normalizeOrderType(type: string | undefined | null): OrderType {
  if (!type) return 'AGENT_RESTOCK'
  return type.toUpperCase() as OrderType
}

export interface Order {
  id: number
  order_type: OrderType
  status: OrderStatus
  items: string | null
  meta: string | null
  created_at: string
  updated_at: string | null
}

export interface OrderAutomationStatus {
  has_automation: boolean
  task_id?: number
  task_status?: string
  title?: string
  total_assignments?: number
  completed_assignments?: number
  progress_percent?: number
}

// Order with parsed items for display
export interface OrderWithDetails extends Order {
  parsed_items?: Array<{ product_id: number; quantity: number; product_name?: string }>
  parsed_meta?: Record<string, unknown>
  automation?: OrderAutomationStatus
}

interface OrderState {
  // Data
  orders: OrderWithDetails[]
  selectedOrder: OrderWithDetails | null
  automationStatus: OrderAutomationStatus | null
  
  // Loading states
  loading: boolean
  loadingOrder: boolean
  loadingAutomation: boolean
  
  // Error state
  error: string | null
  
  // Actions
  fetchOrders: () => Promise<void>
  fetchOrderById: (orderId: number) => Promise<void>
  fetchOrderAutomation: (orderId: number) => Promise<void>
  
  // Socket event handlers
  handleOrderCreated: (data: { order_id: number; status: string; order_type?: string }) => void
  handleOrderUpdated: (data: { order_id: number; status: string; order_type?: string }) => void
  handleOrderCompleted: (data: { order_id: number }) => void
  
  // UI helpers
  setSelectedOrder: (order: OrderWithDetails | null) => void
  addOrderFromNotification: (orderId: number) => void
  clearError: () => void
  reset: () => void
}

export const useOrderStore = create<OrderState>((set, get) => ({
  // Initial state
  orders: [],
  selectedOrder: null,
  automationStatus: null,
  loading: false,
  loadingOrder: false,
  loadingAutomation: false,
  error: null,
  
  fetchOrders: async () => {
    // Note: Backend doesn't have a list endpoint yet
    // This is a placeholder - orders come from notifications/tasks
    set({ loading: true, error: null })
    try {
      // For now, we don't have a list endpoint
      // Orders are populated from notifications and task links
      set({ loading: false })
    } catch (error: unknown) {
      const err = error as { response?: { data?: { detail?: string } } }
      console.error('[OrderStore] Failed to fetch orders:', error)
      set({ 
        error: err.response?.data?.detail || 'Failed to fetch orders',
        loading: false 
      })
    }
  },
  
  fetchOrderById: async (orderId: number) => {
    set({ loadingOrder: true, error: null })
    try {
      // Backend doesn't have GET /api/orders/{id} yet
      // We can only get automation status
      // Create a minimal order object
      const existingOrder = get().orders.find(o => o.id === orderId)
      if (existingOrder) {
        set({ selectedOrder: existingOrder, loadingOrder: false })
        // Also fetch automation status
        await get().fetchOrderAutomation(orderId)
        return
      }
      
      // If order not in local state, create placeholder and fetch automation
      const placeholderOrder: OrderWithDetails = {
        id: orderId,
        order_type: 'AGENT_RESTOCK', // Unknown until we have API
        status: 'SUBMITTED',
        items: null,
        meta: null,
        created_at: new Date().toISOString(),
        updated_at: null,
      }
      
      set({ selectedOrder: placeholderOrder, loadingOrder: false })
      await get().fetchOrderAutomation(orderId)
    } catch (error: unknown) {
      const err = error as { response?: { data?: { detail?: string } } }
      console.error('[OrderStore] Failed to fetch order:', error)
      set({ 
        error: err.response?.data?.detail || 'Failed to fetch order',
        loadingOrder: false 
      })
    }
  },
  
  fetchOrderAutomation: async (orderId: number) => {
    set({ loadingAutomation: true })
    try {
      const response = await api.get(`/api/orders/${orderId}/automation`)
      const automationStatus = response.data as OrderAutomationStatus
      
      set({ automationStatus, loadingAutomation: false })
      
      // Update selected order with automation info
      const selectedOrder = get().selectedOrder
      if (selectedOrder && selectedOrder.id === orderId) {
        set({ 
          selectedOrder: { ...selectedOrder, automation: automationStatus }
        })
      }
      
      // Also update in orders list
      set((state) => ({
        orders: state.orders.map(o => 
          o.id === orderId ? { ...o, automation: automationStatus } : o
        )
      }))
    } catch (error: unknown) {

      console.error('[OrderStore] Failed to fetch order automation:', error)
      set({ 
        automationStatus: { has_automation: false },
        loadingAutomation: false 
      })
    }
  },
  
  // Socket event handlers
  handleOrderCreated: (data) => {
    console.log('[OrderStore] Order created event:', data)
    // Add to orders list if we have more info
    const newOrder: OrderWithDetails = {
      id: data.order_id,
      order_type: normalizeOrderType(data.order_type),
      status: normalizeStatus(data.status),
      items: null,
      meta: null,
      created_at: new Date().toISOString(),
      updated_at: null,
    }
    set((state) => ({
      orders: [newOrder, ...state.orders.filter(o => o.id !== data.order_id)]
    }))
  },
  
  handleOrderUpdated: (data) => {
    console.log('[OrderStore] Order updated event:', data)
    const normalizedStatus = normalizeStatus(data.status)
    set((state) => ({
      orders: state.orders.map(o => 
        o.id === data.order_id 
          ? { ...o, status: normalizedStatus, updated_at: new Date().toISOString() }
          : o
      ),
      selectedOrder: state.selectedOrder?.id === data.order_id
        ? { ...state.selectedOrder, status: normalizedStatus }
        : state.selectedOrder,
    }))
  },
  
  handleOrderCompleted: (data) => {
    console.log('[OrderStore] Order completed event:', data)
    set((state) => ({
      orders: state.orders.map(o => 
        o.id === data.order_id ? { ...o, status: 'COMPLETED' as OrderStatus } : o
      ),
      selectedOrder: state.selectedOrder?.id === data.order_id
        ? { ...state.selectedOrder, status: 'COMPLETED' as OrderStatus }
        : state.selectedOrder,
    }))
  },
  
  // UI helpers
  setSelectedOrder: (order) => {
    set({ selectedOrder: order, automationStatus: null })
    if (order) {
      get().fetchOrderAutomation(order.id)
    }
  },
  
  addOrderFromNotification: (orderId: number) => {
    const exists = get().orders.some(o => o.id === orderId)
    if (!exists) {
      const newOrder: OrderWithDetails = {
        id: orderId,
        order_type: 'AGENT_RESTOCK',
        status: 'SUBMITTED',
        items: null,
        meta: null,
        created_at: new Date().toISOString(),
        updated_at: null,
      }
      set((state) => ({
        orders: [...state.orders, newOrder]
      }))
    }
  },
  
  clearError: () => set({ error: null }),
  
  reset: () => set({
    orders: [],
    selectedOrder: null,
    automationStatus: null,
    loading: false,
    loadingOrder: false,
    loadingAutomation: false,
    error: null,
  }),
}))
