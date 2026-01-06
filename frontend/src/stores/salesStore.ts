/**
 * Sales Store for sales data management.
 * Phase 7.4 - Sales UI
 * 
 * Manages sales summary and agent performance data.
 */
import { create } from 'zustand'
import api from '../services/api'

// Sales channel types
export type SalesChannel = 'AGENT' | 'STORE' | 'WHOLESALE'

export interface SalesSummary {
  total_revenue: number
  total_sales: number
  sales_by_channel: Record<SalesChannel, { count: number; revenue: number }>
}

export interface AgentPerformance {
  agent_id: number
  agent_name: string
  total_sales: number
  units_sold: number
  revenue: number
}

export type DateRangeFilter = 'today' | 'week' | 'month'

interface SalesState {
  // Data
  summary: SalesSummary | null
  agentPerformance: AgentPerformance[]
  
  // Filters
  dateRange: DateRangeFilter
  
  // Loading states
  loadingSummary: boolean
  loadingAgents: boolean
  
  // Error state
  error: string | null
  
  // Actions
  setDateRange: (range: DateRangeFilter) => void
  fetchSummary: () => Promise<void>
  fetchAgentPerformance: () => Promise<void>
  fetchAll: () => Promise<void>
}

export const useSalesStore = create<SalesState>((set, get) => ({
  // Initial state
  summary: null,
  agentPerformance: [],
  dateRange: 'week',
  loadingSummary: false,
  loadingAgents: false,
  error: null,
  
  setDateRange: (range) => {
    set({ dateRange: range })
    // Refetch data with new range
    get().fetchAll()
  },
  
  fetchSummary: async () => {
    set({ loadingSummary: true, error: null })
    try {
      const { dateRange } = get()
      const response = await api.get(`/api/sales/summary`, {
        params: { range: dateRange }
      })
      
      // Handle response - backend may return different formats
      const data = response.data
      const summary: SalesSummary = {
        total_revenue: data.total_revenue || 0,
        total_sales: data.total_sales || 0,
        sales_by_channel: data.sales_by_channel || {
          AGENT: { count: 0, revenue: 0 },
          STORE: { count: 0, revenue: 0 },
          WHOLESALE: { count: 0, revenue: 0 }
        }
      }
      
      set({ summary, loadingSummary: false })
    } catch (error: unknown) {
      console.error('Failed to fetch sales summary:', error)
      // On 404/error, set empty data instead of showing error
      set({ 
        summary: {
          total_revenue: 0,
          total_sales: 0,
          sales_by_channel: {
            AGENT: { count: 0, revenue: 0 },
            STORE: { count: 0, revenue: 0 },
            WHOLESALE: { count: 0, revenue: 0 }
          }
        },
        loadingSummary: false 
      })
    }
  },
  
  fetchAgentPerformance: async () => {
    set({ loadingAgents: true, error: null })
    try {
      const { dateRange } = get()
      const response = await api.get(`/api/sales/performance/agents`, {
        params: { range: dateRange }
      })
      
      // Handle response - may be array or object with agents property
      const data = response.data
      const agents: AgentPerformance[] = Array.isArray(data) 
        ? data 
        : (data.agents || [])
      
      set({ agentPerformance: agents, loadingAgents: false })
    } catch (error: unknown) {
      console.error('Failed to fetch agent performance:', error)
      // On 404/error, set empty array
      set({ agentPerformance: [], loadingAgents: false })
    }
  },
  
  fetchAll: async () => {
    const { fetchSummary, fetchAgentPerformance } = get()
    await Promise.all([fetchSummary(), fetchAgentPerformance()])
  }
}))
