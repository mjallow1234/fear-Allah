/**
 * Audit Store for admin audit log management.
 * Phase 8.2 - Admin Audit Log
 * Phase 8.4.2 - Stabilization (in-flight guards, rate-limit handling)
 * 
 * Manages audit log data with filters and pagination.
 */
import { create } from 'zustand'
import api from '../services/api'
import { AxiosError } from 'axios'

export interface AuditLogEntry {
  id: number
  user_id: number | null
  username: string | null
  action: string
  target_type: string | null
  target_id: number | null
  description: string | null
  meta: Record<string, unknown> | null
  ip_address: string | null
  request_id: string | null
  created_at: string
}

interface AuditFilters {
  user_id?: number | null
  action?: string | null
  target_type?: string | null
  target_id?: number | null
  start_date?: string | null
  end_date?: string | null
}

interface AuditState {
  // Data
  logs: AuditLogEntry[]
  total: number
  
  // Pagination
  page: number
  limit: number
  
  // Filters
  filters: AuditFilters
  
  // Filter options
  actionTypes: string[]
  targetTypes: string[]
  
  // Loading states
  loading: boolean
  loadingOptions: boolean
  
  // In-flight guards (Phase 8.4.2 - prevent duplicate requests)
  _fetchingLogs: boolean
  _fetchingOptions: boolean
  _optionsFetched: boolean  // Only fetch once per session
  
  // Rate limit state
  rateLimited: boolean
  rateLimitRetryAt: number | null
  
  // Error state
  error: string | null
  
  // Actions
  setPage: (page: number) => void
  setFilters: (filters: Partial<AuditFilters>) => void
  clearFilters: () => void
  fetchLogs: () => Promise<void>
  fetchFilterOptions: () => Promise<void>
  resetRateLimitState: () => void
}

const initialFilters: AuditFilters = {
  user_id: null,
  action: null,
  target_type: null,
  target_id: null,
  start_date: null,
  end_date: null,
}

export const useAuditStore = create<AuditState>((set, get) => ({
  // Initial state
  logs: [],
  total: 0,
  page: 1,
  limit: 50,
  filters: { ...initialFilters },
  actionTypes: [],
  targetTypes: [],
  loading: false,
  loadingOptions: false,
  _fetchingLogs: false,
  _fetchingOptions: false,
  _optionsFetched: false,
  rateLimited: false,
  rateLimitRetryAt: null,
  error: null,
  
  setPage: (page) => {
    set({ page })
    get().fetchLogs()
  },
  
  setFilters: (newFilters) => {
    set({ 
      filters: { ...get().filters, ...newFilters },
      page: 1  // Reset to first page on filter change
    })
    get().fetchLogs()
  },
  
  clearFilters: () => {
    set({ filters: { ...initialFilters }, page: 1 })
    get().fetchLogs()
  },
  
  resetRateLimitState: () => {
    set({ rateLimited: false, rateLimitRetryAt: null, error: null })
  },
  
  fetchLogs: async () => {
    // In-flight guard: prevent duplicate requests (Phase 8.4.2)
    if (get()._fetchingLogs) {
      console.log('[AuditStore] fetchLogs already in flight, skipping')
      return
    }
    
    set({ _fetchingLogs: true, loading: true, error: null })
    try {
      const { page, limit, filters } = get()
      
      // Build query params - use page-based pagination for /api/system/audit-log
      const params: Record<string, string | number> = { page, limit }
      if (filters.user_id) params.user_id = filters.user_id
      if (filters.action) params.action = filters.action
      if (filters.target_type) params.target_type = filters.target_type
      if (filters.target_id) params.target_id = filters.target_id
      if (filters.start_date) params.start_date = filters.start_date
      if (filters.end_date) params.end_date = filters.end_date
      
      const response = await api.get('/api/system/audit-log', { params })
      
      set({
        logs: response.data.logs || [],
        total: response.data.total || 0,
        loading: false,
        _fetchingLogs: false,
        rateLimited: false,
        rateLimitRetryAt: null,
      })
    } catch (error: unknown) {
      console.error('Failed to fetch audit logs:', error)
      
      // Check for rate limit (429)
      const axiosError = error as AxiosError
      if (axiosError.response?.status === 429) {
        const retryAfter = axiosError.response.headers['retry-after']
        const retryAt = retryAfter ? Date.now() + (parseInt(retryAfter) * 1000) : Date.now() + 60000
        set({
          loading: false,
          _fetchingLogs: false,
          rateLimited: true,
          rateLimitRetryAt: retryAt,
          error: 'Audit data temporarily rate-limited. Retrying shortly.',
        })
        return
      }
      
      // Defensive: show empty state, don't throw
      set({
        logs: [],
        total: 0,
        loading: false,
        _fetchingLogs: false,
        error: error instanceof Error ? error.message : 'Failed to fetch audit logs',
      })
    }
  },
  
  fetchFilterOptions: async () => {
    // Only fetch once per session (Phase 8.4.2)
    if (get()._optionsFetched) {
      console.log('[AuditStore] Filter options already fetched, skipping')
      return
    }
    
    // In-flight guard: prevent duplicate requests
    if (get()._fetchingOptions) {
      console.log('[AuditStore] fetchFilterOptions already in flight, skipping')
      return
    }
    
    set({ _fetchingOptions: true, loadingOptions: true })
    try {
      // Fetch action types and target types in parallel
      const [actionsRes, typesRes] = await Promise.all([
        api.get('/api/system/audit-log/actions'),
        api.get('/api/system/audit-log/target-types'),
      ])
      
      set({
        actionTypes: actionsRes.data.actions || [],
        targetTypes: typesRes.data.target_types || [],
        loadingOptions: false,
        _fetchingOptions: false,
        _optionsFetched: true,  // Mark as fetched
      })
    } catch (error: unknown) {
      console.error('Failed to fetch filter options:', error)
      
      // Check for rate limit (429)
      const axiosError = error as AxiosError
      if (axiosError.response?.status === 429) {
        set({ 
          loadingOptions: false,
          _fetchingOptions: false,
          // Don't set _optionsFetched so it can retry later
        })
        return
      }
      
      // Defensive: don't throw, just show empty options
      set({ 
        actionTypes: [],
        targetTypes: [],
        loadingOptions: false,
        _fetchingOptions: false,
        _optionsFetched: true,  // Mark as attempted
      })
    }
  },
}))
