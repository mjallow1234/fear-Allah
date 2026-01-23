/**
 * Admin Audit Page
 * Phase 8.2 - Admin Audit Log
 * Phase 8.4.2 - Stabilization (rate-limit handling, read-only indicators)
 * 
 * Read-only view of system audit logs with filtering.
 * Admin-only access.
 */
import { useEffect, useState, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  ArrowLeft,
  FileText,
  Filter,
  RefreshCw,
  Loader2,
  ChevronLeft,
  ChevronRight,
  User,
  Activity,
  AlertTriangle,
  Eye
} from 'lucide-react'
import clsx from 'clsx'
import { useAuditStore, AuditLogEntry } from '../stores/auditStore'

// Format date/time for display
function formatDateTime(dateStr: string): string {
  const date = new Date(dateStr)
  return date.toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit'
  })
}

// Format relative time
function formatRelativeTime(dateStr: string): string {
  const date = new Date(dateStr)
  const now = new Date()
  const diffMs = now.getTime() - date.getTime()
  const diffMins = Math.floor(diffMs / 60000)
  const diffHours = Math.floor(diffMs / 3600000)
  const diffDays = Math.floor(diffMs / 86400000)
  
  if (diffMins < 1) return 'just now'
  if (diffMins < 60) return `${diffMins}m ago`
  if (diffHours < 24) return `${diffHours}h ago`
  if (diffDays < 7) return `${diffDays}d ago`
  return formatDateTime(dateStr)
}

// Action badge colors based on action type
function getActionBadgeColor(action: string): string {
  if (action.includes('create') || action.includes('login')) return 'bg-green-500/20 text-green-400'
  if (action.includes('update') || action.includes('change')) return 'bg-blue-500/20 text-blue-400'
  if (action.includes('delete') || action.includes('ban')) return 'bg-red-500/20 text-red-400'
  if (action.includes('admin')) return 'bg-purple-500/20 text-purple-400'
  return 'bg-gray-500/20 text-gray-400'
}

// Target type icon
function getTargetTypeIcon(targetType: string | null): string {
  const icons: Record<string, string> = {
    'user': '👤',
    'channel': '💬',
    'message': '📝',
    'sale': '💰',
    'inventory': '📦',
    'order': '📋',
    'task': '✅',
    'system': '⚙️',
    'auth': '🔐',
  }
  return icons[targetType || ''] || '📄'
}

// Audit Log Row Component
function AuditLogRow({ log }: { log: AuditLogEntry }) {
  const [expanded, setExpanded] = useState(false)
  
  return (
    <div className="border-b border-gray-700/50 last:border-b-0">
      {/* Main Row */}
      <div
        className={clsx(
          'px-4 py-3 hover:bg-gray-800/50 cursor-pointer transition-colors',
          expanded && 'bg-gray-800/30'
        )}
        onClick={() => setExpanded(!expanded)}
      >
        <div className="flex items-center gap-4">
          {/* Timestamp */}
          <div className="w-32 flex-shrink-0">
            <div className="text-xs text-gray-400" title={formatDateTime(log.created_at)}>
              {formatRelativeTime(log.created_at)}
            </div>
          </div>
          
          {/* Actor */}
          <div className="w-32 flex-shrink-0">
            <div className="flex items-center gap-2">
              <User className="w-3 h-3 text-gray-500" />
              <span className="text-sm text-gray-300 truncate">
                {log.username || log.user_id || 'System'}
              </span>
            </div>
          </div>
          
          {/* Action */}
          <div className="flex-shrink-0">
            <span className={clsx(
              'px-2 py-1 rounded text-xs font-medium',
              getActionBadgeColor(log.action)
            )}>
              {log.action}
            </span>
          </div>
          
          {/* Target */}
          <div className="flex-1 min-w-0 flex items-center gap-2">
            <span className="text-base">{getTargetTypeIcon(log.target_type)}</span>
            <span className="text-sm text-gray-400 truncate">
              {log.target_type && (
                <>
                  {log.target_type}
                  {log.target_id && <span className="text-gray-500"> #{log.target_id}</span>}
                </>
              )}
            </span>
          </div>
          
          {/* Description Preview */}
          <div className="flex-1 min-w-0">
            {log.description && (
              <span className="text-sm text-gray-400 truncate block">
                {log.description}
              </span>
            )}
          </div>
          
          {/* Expand Indicator */}
          <div className="w-8 flex-shrink-0 text-right">
            <ChevronRight className={clsx(
              'w-4 h-4 text-gray-500 transition-transform inline-block',
              expanded && 'transform rotate-90'
            )} />
          </div>
        </div>
      </div>
      
      {/* Expanded Details */}
      {expanded && (
        <div className="px-4 py-3 bg-gray-800/20 border-t border-gray-700/30">
          <div className="grid grid-cols-2 gap-4 text-sm">
            <div>
              <div className="text-gray-500 text-xs mb-1">Full Timestamp</div>
              <div className="text-gray-300">{formatDateTime(log.created_at)}</div>
            </div>
            <div>
              <div className="text-gray-500 text-xs mb-1">Request ID</div>
              <div className="text-gray-300 font-mono text-xs">
                {log.request_id || '-'}
              </div>
            </div>
            <div>
              <div className="text-gray-500 text-xs mb-1">IP Address</div>
              <div className="text-gray-300 font-mono text-xs">
                {log.ip_address || '-'}
              </div>
            </div>
            <div>
              <div className="text-gray-500 text-xs mb-1">User ID</div>
              <div className="text-gray-300">
                {log.user_id || 'System'}
              </div>
            </div>
            {log.description && (
              <div className="col-span-2">
                <div className="text-gray-500 text-xs mb-1">Description</div>
                <div className="text-gray-300">{log.description}</div>
              </div>
            )}
            {log.meta && Object.keys(log.meta).length > 0 && (
              <div className="col-span-2">
                <div className="text-gray-500 text-xs mb-1">Metadata</div>
                <pre className="text-gray-300 font-mono text-xs bg-gray-900/50 p-2 rounded overflow-x-auto">
                  {JSON.stringify(log.meta, null, 2)}
                </pre>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  )
}

export default function AdminAuditPage() {
  const navigate = useNavigate()
  const [showFilters, setShowFilters] = useState(false)
  
  // useRef guard to prevent StrictMode double-fetch (Phase 8.4.2)
  const hasFetchedRef = useRef(false)
  
  // Local filter inputs (before applying)
  const [filterInputs, setFilterInputs] = useState({
    action: '',
    target_type: '',
    user_id: '',
    start_date: '',
    end_date: '',
  })
  
  // Store
  const {
    logs,
    total,
    page,
    limit,
    filters,
    actionTypes,
    targetTypes,
    loading,
    rateLimited,
    setPage,
    setFilters,
    clearFilters,
    fetchLogs,
    fetchFilterOptions,
    resetRateLimitState,
  } = useAuditStore()

  // NOTE: layout changes below make the page a column-flex so header + filters remain fixed
  // and the main audit list (the <main> below) becomes scrollable (flex-1 overflow-y-auto min-h-0).
  
  // Fetch on mount - with StrictMode guard (Phase 8.4.2)
  useEffect(() => {
    if (hasFetchedRef.current) return
    hasFetchedRef.current = true
    
    fetchLogs()
    fetchFilterOptions()
  }, [fetchLogs, fetchFilterOptions])
  
  // Calculate pagination
  const totalPages = Math.ceil(total / limit)
  const hasNextPage = page < totalPages
  const hasPrevPage = page > 1
  
  // Handle filter apply
  const handleApplyFilters = () => {
    setFilters({
      action: filterInputs.action || null,
      target_type: filterInputs.target_type || null,
      user_id: filterInputs.user_id ? parseInt(filterInputs.user_id) : null,
      start_date: filterInputs.start_date || null,
      end_date: filterInputs.end_date || null,
    })
    setShowFilters(false)
  }
  
  // Handle filter clear
  const handleClearFilters = () => {
    setFilterInputs({
      action: '',
      target_type: '',
      user_id: '',
      start_date: '',
      end_date: '',
    })
    clearFilters()
    setShowFilters(false)
  }
  
  // Check if any filters are active
  const hasActiveFilters = Object.values(filters).some(v => v !== null && v !== undefined)
  
  return (
    <div className="flex flex-col h-full bg-gray-900 text-white">
      {/* Rate Limit Banner (Phase 8.4.2) */}
      {rateLimited && (
        <div className="bg-yellow-600/20 border-b border-yellow-600/30 px-6 py-3">
          <div className="flex items-center gap-3">
            <AlertTriangle className="w-5 h-5 text-yellow-400" />
            <span className="text-yellow-200">
              Audit data temporarily rate-limited. Retrying shortly.
            </span>
            <button
              onClick={() => {
                resetRateLimitState()
                fetchLogs()
              }}
              className="ml-auto px-3 py-1 bg-yellow-600/30 hover:bg-yellow-600/50 rounded text-sm text-yellow-200 transition-colors"
            >
              Retry Now
            </button>
          </div>
        </div>
      )}
      
      {/* Header */}
      <header className="bg-gray-800/50 border-b border-gray-700/50 px-6 py-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-4">
            <button
              onClick={() => navigate('/system')}
              className="p-2 hover:bg-gray-700/50 rounded-lg transition-colors"
              title="Back to System Console"
            >
              <ArrowLeft className="w-5 h-5" />
            </button>
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 bg-purple-600/20 rounded-lg flex items-center justify-center">
                <FileText className="w-5 h-5 text-purple-400" />
              </div>
              <div>
                <div className="flex items-center gap-2">
                  <h1 className="text-xl font-semibold">Audit Log</h1>
                  {/* Read-only badge (Phase 8.4.2) */}
                  <span className="px-2 py-0.5 bg-gray-700/50 rounded text-xs text-gray-400 flex items-center gap-1">
                    <Eye className="w-3 h-3" />
                    Read-only (Phase 8.4)
                  </span>
                </div>
                <p className="text-sm text-gray-400">System activity history</p>
              </div>
            </div>
          </div>
          
          <div className="flex items-center gap-3">
            {/* Filter Toggle */}
            <button
              onClick={() => setShowFilters(!showFilters)}
              className={clsx(
                'flex items-center gap-2 px-4 py-2 rounded-lg transition-colors',
                hasActiveFilters 
                  ? 'bg-purple-600/30 text-purple-300 hover:bg-purple-600/40'
                  : 'bg-gray-700/50 hover:bg-gray-700'
              )}
            >
              <Filter className="w-4 h-4" />
              <span>Filters</span>
              {hasActiveFilters && (
                <span className="w-2 h-2 rounded-full bg-purple-400" />
              )}
            </button>
            
            {/* Refresh */}
            <button
              onClick={() => fetchLogs()}
              disabled={loading}
              className="flex items-center gap-2 px-4 py-2 bg-gray-700/50 hover:bg-gray-700 rounded-lg transition-colors disabled:opacity-50"
            >
              <RefreshCw className={clsx('w-4 h-4', loading && 'animate-spin')} />
              <span>Refresh</span>
            </button>
          </div>
        </div>
      </header>
      
      {/* Filters Panel */}
      {showFilters && (
        <div className="bg-gray-800/30 border-b border-gray-700/50 px-6 py-4">
          <div className="flex flex-wrap gap-4 items-end">
            {/* Action Filter */}
            <div className="flex-1 min-w-[200px]">
              <label className="block text-xs text-gray-400 mb-1">Action</label>
              <select
                value={filterInputs.action}
                onChange={(e) => setFilterInputs({ ...filterInputs, action: e.target.value })}
                className="w-full px-3 py-2 bg-gray-800 border border-gray-700 rounded-lg text-sm focus:outline-none focus:border-purple-500"
              >
                <option value="">All Actions</option>
                {actionTypes.map(action => (
                  <option key={action} value={action}>{action}</option>
                ))}
              </select>
            </div>
            
            {/* Target Type Filter */}
            <div className="flex-1 min-w-[200px]">
              <label className="block text-xs text-gray-400 mb-1">Target Type</label>
              <select
                value={filterInputs.target_type}
                onChange={(e) => setFilterInputs({ ...filterInputs, target_type: e.target.value })}
                className="w-full px-3 py-2 bg-gray-800 border border-gray-700 rounded-lg text-sm focus:outline-none focus:border-purple-500"
              >
                <option value="">All Types</option>
                {targetTypes.map(type => (
                  <option key={type} value={type}>{type}</option>
                ))}
              </select>
            </div>
            
            {/* User ID Filter */}
            <div className="w-32">
              <label className="block text-xs text-gray-400 mb-1">User ID</label>
              <input
                type="number"
                value={filterInputs.user_id}
                onChange={(e) => setFilterInputs({ ...filterInputs, user_id: e.target.value })}
                placeholder="Any"
                className="w-full px-3 py-2 bg-gray-800 border border-gray-700 rounded-lg text-sm focus:outline-none focus:border-purple-500"
              />
            </div>
            
            {/* Start Date */}
            <div className="w-44">
              <label className="block text-xs text-gray-400 mb-1">From Date</label>
              <input
                type="datetime-local"
                value={filterInputs.start_date}
                onChange={(e) => setFilterInputs({ ...filterInputs, start_date: e.target.value })}
                className="w-full px-3 py-2 bg-gray-800 border border-gray-700 rounded-lg text-sm focus:outline-none focus:border-purple-500"
              />
            </div>
            
            {/* End Date */}
            <div className="w-44">
              <label className="block text-xs text-gray-400 mb-1">To Date</label>
              <input
                type="datetime-local"
                value={filterInputs.end_date}
                onChange={(e) => setFilterInputs({ ...filterInputs, end_date: e.target.value })}
                className="w-full px-3 py-2 bg-gray-800 border border-gray-700 rounded-lg text-sm focus:outline-none focus:border-purple-500"
              />
            </div>
            
            {/* Filter Buttons */}
            <div className="flex gap-2">
              <button
                onClick={handleApplyFilters}
                className="px-4 py-2 bg-purple-600 hover:bg-purple-700 rounded-lg text-sm font-medium transition-colors"
              >
                Apply
              </button>
              <button
                onClick={handleClearFilters}
                className="px-4 py-2 bg-gray-700 hover:bg-gray-600 rounded-lg text-sm transition-colors"
              >
                Clear
              </button>
            </div>
          </div>
        </div>
      )}
      
      {/* Content - make this area scrollable while keeping header/filters fixed */}
      <main className="p-6 flex-1 overflow-y-auto min-h-0">
        {/* Stats Bar */}
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-4 text-sm text-gray-400">
            <span>
              Showing {logs.length} of {total.toLocaleString()} entries
            </span>
            {hasActiveFilters && (
              <span className="flex items-center gap-1 text-purple-400">
                <Filter className="w-3 h-3" />
                Filtered
              </span>
            )}
          </div>
          
          {/* Pagination Controls */}
          <div className="flex items-center gap-2">
            <button
              onClick={() => setPage(page - 1)}
              disabled={!hasPrevPage || loading}
              className="p-2 bg-gray-800 hover:bg-gray-700 disabled:opacity-50 disabled:cursor-not-allowed rounded-lg transition-colors"
            >
              <ChevronLeft className="w-4 h-4" />
            </button>
            <span className="px-3 py-1 text-sm text-gray-400">
              Page {page} of {totalPages || 1}
            </span>
            <button
              onClick={() => setPage(page + 1)}
              disabled={!hasNextPage || loading}
              className="p-2 bg-gray-800 hover:bg-gray-700 disabled:opacity-50 disabled:cursor-not-allowed rounded-lg transition-colors"
            >
              <ChevronRight className="w-4 h-4" />
            </button>
          </div>
        </div>
        
        {/* Audit Log Table */}
        <div className="bg-gray-800/30 rounded-xl border border-gray-700/50">
          {/* Table Header */}
          <div className="px-4 py-3 bg-gray-800/50 border-b border-gray-700/50">
            <div className="flex items-center gap-4 text-xs text-gray-500 font-medium uppercase tracking-wider">
              <div className="w-32 flex-shrink-0">Time</div>
              <div className="w-32 flex-shrink-0">Actor</div>
              <div className="flex-shrink-0 w-32">Action</div>
              <div className="flex-1">Target</div>
              <div className="flex-1">Description</div>
              <div className="w-8"></div>
            </div>
          </div>
          
          {/* Table Body */}
          {loading ? (
            <div className="flex items-center justify-center py-16">
              <Loader2 className="w-8 h-8 animate-spin text-purple-400" />
            </div>
          ) : logs.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-16 text-gray-500">
              <Activity className="w-12 h-12 mb-3 opacity-50" />
              <p>No audit logs found</p>
              {hasActiveFilters && (
                <button
                  onClick={handleClearFilters}
                  className="mt-2 text-purple-400 hover:text-purple-300 text-sm"
                >
                  Clear filters
                </button>
              )}
            </div>
          ) : (
            <div className="divide-y divide-gray-700/30">
              {logs.map(log => (
                <AuditLogRow key={log.id} log={log} />
              ))}
            </div>
          )}
        </div>
        
        {/* Bottom Pagination */}
        {totalPages > 1 && (
          <div className="flex justify-center mt-4">
            <div className="flex items-center gap-2">
              <button
                onClick={() => setPage(1)}
                disabled={page === 1 || loading}
                className="px-3 py-1 text-sm bg-gray-800 hover:bg-gray-700 disabled:opacity-50 disabled:cursor-not-allowed rounded transition-colors"
              >
                First
              </button>
              <button
                onClick={() => setPage(page - 1)}
                disabled={!hasPrevPage || loading}
                className="px-3 py-1 text-sm bg-gray-800 hover:bg-gray-700 disabled:opacity-50 disabled:cursor-not-allowed rounded transition-colors"
              >
                Previous
              </button>
              <span className="px-3 py-1 text-sm text-gray-400">
                {page} / {totalPages}
              </span>
              <button
                onClick={() => setPage(page + 1)}
                disabled={!hasNextPage || loading}
                className="px-3 py-1 text-sm bg-gray-800 hover:bg-gray-700 disabled:opacity-50 disabled:cursor-not-allowed rounded transition-colors"
              >
                Next
              </button>
              <button
                onClick={() => setPage(totalPages)}
                disabled={page === totalPages || loading}
                className="px-3 py-1 text-sm bg-gray-800 hover:bg-gray-700 disabled:opacity-50 disabled:cursor-not-allowed rounded transition-colors"
              >
                Last
              </button>
            </div>
          </div>
        )}
      </main>
    </div>
  )
}
