/**
 * AI Insights Page
 * AI Infrastructure Skeleton - Phase AI.1
 * 
 * Admin-only dashboard showing AI-generated recommendations and insights.
 * Currently a placeholder - AI logic will be implemented later.
 * 
 * Future features:
 * - Demand forecasting insights
 * - Production planning recommendations
 * - Waste analysis alerts
 * - Sales & agent intelligence
 */
import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  ArrowLeft,
  Brain,
  Lightbulb,
  TrendingUp,
  Package,
  AlertTriangle,
  Users,
  RefreshCw,
  Loader2,
  Clock,
  XCircle,
  Sparkles,
  BarChart3,
  Zap,
  Factory,
  ShoppingCart,
  Truck,
  ChevronDown,
  ChevronUp,
  Check,
  X,
  Eye,
  MessageSquare,
  Tag,
  Flag,
  Shield,
  Edit3,
  Save,
} from 'lucide-react'
import clsx from 'clsx'
import api from '../services/api'

// Types for AI recommendations (matches backend schema)
interface AIRecommendation {
  id: string
  type: string
  scope: string
  confidence: number
  summary: string
  explanation: string[] | null
  data_refs: Record<string, unknown> | null
  generated_by: string
  // Lifecycle status (Phase 4.1)
  status: 'pending' | 'acknowledged' | 'approved' | 'rejected' | 'expired'
  feedback_note: string | null
  feedback_by_id: number | null
  feedback_at: string | null
  // Governance tags (Phase 5.1)
  priority: 'critical' | 'high' | 'medium' | 'low' | null
  category: 'inventory' | 'production' | 'procurement' | 'sales' | 'operations' | 'compliance' | null
  risk_level: 'high_risk' | 'medium_risk' | 'low_risk' | 'no_risk' | null
  assigned_to_id: number | null
  tags: string[] | null
  governance_note: string | null
  // Legacy
  is_dismissed: boolean
  dismissed_at: string | null
  expires_at: string | null
  created_at: string
}

// Governance options from API (Phase 5.1)
interface GovernanceOptions {
  priorities: { value: string; label: string; color: string }[]
  categories: { value: string; label: string }[]
  risk_levels: { value: string; label: string; color: string }[]
}

interface AIStatus {
  active_count: number
  last_run: string | null
  engine_status: string
}

// Scheduler status (Phase 4.2)
interface SchedulerStatus {
  enabled: boolean
  running: boolean
  last_auto_run: string | null
  last_expiry_check: string | null
  last_cleanup: string | null
  scheduled_jobs: { id: string; name: string; next_run: string | null }[]
}

// Map recommendation types to icons and colors
const typeConfig: Record<string, { icon: typeof Brain; color: string; label: string; category: 'insight' | 'recommendation' }> = {
  // Insights (Phase 9.1)
  demand_forecast: { icon: TrendingUp, color: 'text-blue-400 bg-blue-500/20', label: 'Demand Forecast', category: 'insight' },
  production_plan: { icon: Package, color: 'text-green-400 bg-green-500/20', label: 'Production Plan', category: 'insight' },
  waste_alert: { icon: AlertTriangle, color: 'text-amber-400 bg-amber-500/20', label: 'Waste Alert', category: 'insight' },
  yield_insight: { icon: BarChart3, color: 'text-purple-400 bg-purple-500/20', label: 'Yield Insight', category: 'insight' },
  sales_insight: { icon: Zap, color: 'text-cyan-400 bg-cyan-500/20', label: 'Sales Insight', category: 'insight' },
  agent_insight: { icon: Users, color: 'text-pink-400 bg-pink-500/20', label: 'Agent Insight', category: 'insight' },
  // Recommendations (Phase 9.2)
  production_recommendation: { icon: Factory, color: 'text-emerald-400 bg-emerald-500/20', label: 'Production Suggestion', category: 'recommendation' },
  reorder_recommendation: { icon: ShoppingCart, color: 'text-orange-400 bg-orange-500/20', label: 'Reorder Suggestion', category: 'recommendation' },
  procurement_recommendation: { icon: Truck, color: 'text-rose-400 bg-rose-500/20', label: 'Procurement Suggestion', category: 'recommendation' },
}

// Status badge config (Phase 4.1)
const statusConfig: Record<string, { label: string; color: string; bgColor: string }> = {
  pending: { label: 'Pending', color: 'text-gray-400', bgColor: 'bg-gray-500/20' },
  acknowledged: { label: 'Reviewed', color: 'text-blue-400', bgColor: 'bg-blue-500/20' },
  approved: { label: 'Approved', color: 'text-green-400', bgColor: 'bg-green-500/20' },
  rejected: { label: 'Rejected', color: 'text-red-400', bgColor: 'bg-red-500/20' },
  expired: { label: 'Expired', color: 'text-gray-500', bgColor: 'bg-gray-600/20' },
}

// Priority badge config (Phase 5.1)
const priorityConfig: Record<string, { label: string; color: string; bgColor: string }> = {
  critical: { label: 'Critical', color: 'text-red-400', bgColor: 'bg-red-500/20' },
  high: { label: 'High', color: 'text-orange-400', bgColor: 'bg-orange-500/20' },
  medium: { label: 'Medium', color: 'text-yellow-400', bgColor: 'bg-yellow-500/20' },
  low: { label: 'Low', color: 'text-gray-400', bgColor: 'bg-gray-500/20' },
}

// Risk level config (Phase 5.1)
const riskLevelConfig: Record<string, { label: string; color: string; bgColor: string }> = {
  high_risk: { label: 'High Risk', color: 'text-red-400', bgColor: 'bg-red-500/20' },
  medium_risk: { label: 'Medium Risk', color: 'text-orange-400', bgColor: 'bg-orange-500/20' },
  low_risk: { label: 'Low Risk', color: 'text-yellow-400', bgColor: 'bg-yellow-500/20' },
  no_risk: { label: 'No Risk', color: 'text-green-400', bgColor: 'bg-green-500/20' },
}

// Category config (Phase 5.1)
const categoryConfig: Record<string, { label: string; icon: typeof Package }> = {
  inventory: { label: 'Inventory', icon: Package },
  production: { label: 'Production', icon: Factory },
  procurement: { label: 'Procurement', icon: Truck },
  sales: { label: 'Sales', icon: ShoppingCart },
  operations: { label: 'Operations', icon: BarChart3 },
  compliance: { label: 'Compliance', icon: Shield },
}

// Confidence badge
function ConfidenceBadge({ confidence }: { confidence: number }) {
  const pct = Math.round(confidence * 100)
  let color = 'bg-red-500/20 text-red-400'
  if (pct >= 80) color = 'bg-green-500/20 text-green-400'
  else if (pct >= 60) color = 'bg-amber-500/20 text-amber-400'
  
  return (
    <span className={clsx('px-2 py-0.5 rounded-full text-xs font-medium', color)}>
      {pct}% confidence
    </span>
  )
}

// Status badge component
function StatusBadge({ status }: { status: string }) {
  const config = statusConfig[status] || statusConfig.pending
  return (
    <span className={clsx('px-2 py-0.5 rounded-full text-xs font-medium', config.color, config.bgColor)}>
      {config.label}
    </span>
  )
}

// Priority badge component (Phase 5.1)
function PriorityBadge({ priority }: { priority: string | null }) {
  if (!priority) return null
  const config = priorityConfig[priority] || priorityConfig.low
  return (
    <span className={clsx('flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium', config.color, config.bgColor)}>
      <Flag className="w-3 h-3" />
      {config.label}
    </span>
  )
}

// Risk level badge component (Phase 5.1)
function RiskBadge({ riskLevel }: { riskLevel: string | null }) {
  if (!riskLevel) return null
  const config = riskLevelConfig[riskLevel] || riskLevelConfig.no_risk
  return (
    <span className={clsx('flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium', config.color, config.bgColor)}>
      <Shield className="w-3 h-3" />
      {config.label}
    </span>
  )
}

// Category badge component (Phase 5.1)
function CategoryBadge({ category }: { category: string | null }) {
  if (!category) return null
  const config = categoryConfig[category]
  if (!config) return null
  const Icon = config.icon
  return (
    <span className="flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium text-indigo-400 bg-indigo-500/20">
      <Icon className="w-3 h-3" />
      {config.label}
    </span>
  )
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
  return date.toLocaleDateString()
}

export default function AIInsightsPage() {
  const navigate = useNavigate()
  const [recommendations, setRecommendations] = useState<AIRecommendation[]>([])
  const [status, setStatus] = useState<AIStatus | null>(null)
  const [schedulerStatus, setSchedulerStatus] = useState<SchedulerStatus | null>(null)
  const [loading, setLoading] = useState(true)
  const [runningAnalysis, setRunningAnalysis] = useState(false)
  const [runningRecommendations, setRunningRecommendations] = useState(false)
  const [runningJob, setRunningJob] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [filter, setFilter] = useState<string>('all')
  const [categoryTab, setCategoryTab] = useState<'all' | 'insight' | 'recommendation'>('all')
  const [expandedCards, setExpandedCards] = useState<Set<string>>(new Set())
  // Governance filters (Phase 5.1)
  const [priorityFilter, setPriorityFilter] = useState<string>('all')
  const [riskFilter, setRiskFilter] = useState<string>('all')
  const [govCategoryFilter, setGovCategoryFilter] = useState<string>('all')
  const [assignedFilter, setAssignedFilter] = useState<string>('all')
  const [showFilters, setShowFilters] = useState(false)
  // Governance editing state (Phase 5.1)
  const [governanceOptions, setGovernanceOptions] = useState<GovernanceOptions | null>(null)
  const [editingGovernance, setEditingGovernance] = useState<string | null>(null)
  const [governanceForm, setGovernanceForm] = useState<{
    priority: string
    category: string
    risk_level: string
    tags: string
    governance_note: string
  }>({ priority: '', category: '', risk_level: '', tags: '', governance_note: '' })
  const [savingGovernance, setSavingGovernance] = useState(false)
  // Admin users list for assignment filter
  const [adminUsers, setAdminUsers] = useState<{ id: number; username: string }[]>([])

  const toggleCardExpanded = (id: string) => {
    setExpandedCards(prev => {
      const next = new Set(prev)
      if (next.has(id)) {
        next.delete(id)
      } else {
        next.add(id)
      }
      return next
    })
  }

  // Fetch admin users for assignment filter
  const fetchAdminUsers = async () => {
    try {
      const res = await api.get('/api/admin/users?include_admins=true')
      const admins = res.data.users?.filter((u: any) => u.is_system_admin) || []
      setAdminUsers(admins.map((u: any) => ({ id: u.id, username: u.username })))
    } catch {
      // Ignore errors fetching admin users
    }
  }

  // Fetch AI status and recommendations
  const fetchData = async () => {
    setLoading(true)
    setError(null)
    try {
      // Fetch status
      const statusRes = await api.get('/api/ai/status')
      setStatus(statusRes.data)

      // Fetch scheduler status (Phase 4.2)
      try {
        const schedulerRes = await api.get('/api/ai/scheduler/status')
        setSchedulerStatus(schedulerRes.data)
      } catch {
        // Ignore scheduler status errors
      }

      // Fetch governance options (Phase 5.1)
      try {
        const govRes = await api.get('/api/ai/governance/options')
        setGovernanceOptions(govRes.data)
      } catch {
        // Ignore governance options errors
      }

      // Fetch recommendations with governance filters
      const params = new URLSearchParams()
      if (filter !== 'all') params.append('type', filter)
      if (categoryTab !== 'all') params.append('category', categoryTab)
      // Governance filters (Phase 5.1)
      if (priorityFilter !== 'all') params.append('priority', priorityFilter)
      if (riskFilter !== 'all') params.append('risk_level', riskFilter)
      if (govCategoryFilter !== 'all') params.append('gov_category', govCategoryFilter)
      if (assignedFilter !== 'all') params.append('assigned_to_id', assignedFilter)
      params.append('include_dismissed', 'false')
      
      const recRes = await api.get(`/api/ai/recommendations?${params}`)
      setRecommendations(recRes.data.recommendations || [])
    } catch (err: any) {
      if (err.response?.status === 403) {
        setError('Admin access required')
      } else {
        setError('Failed to load recommendations')
      }
    } finally {
      setLoading(false)
    }
  }

  // Run on-demand analysis (generate insights)
  const runAnalysis = async () => {
    setRunningAnalysis(true)
    try {
      await api.post('/api/ai/run')
      // Refresh data after analysis
      await fetchData()
    } catch (err) {
      console.error('Analysis failed:', err)
    } finally {
      setRunningAnalysis(false)
    }
  }

  // Run recommendation generation (Phase 9.2)
  const runRecommendations = async () => {
    setRunningRecommendations(true)
    try {
      await api.post('/api/ai/recommendations/run')
      // Refresh data after generating recommendations
      await fetchData()
    } catch (err) {
      console.error('Recommendation generation failed:', err)
    } finally {
      setRunningRecommendations(false)
    }
  }

  // Dismiss a recommendation
  const dismissRecommendation = async (id: string) => {
    try {
      await api.post(`/api/ai/recommendations/${id}/dismiss`)
      setRecommendations(prev => prev.filter(r => r.id !== id))
    } catch (err) {
      console.error('Dismiss failed:', err)
    }
  }

  // Lifecycle actions (Phase 4.1)
  const acknowledgeRecommendation = async (id: string) => {
    try {
      await api.post(`/api/ai/recommendations/${id}/acknowledge`)
      setRecommendations(prev => prev.map(r => 
        r.id === id ? { ...r, status: 'acknowledged' as const } : r
      ))
    } catch (err) {
      console.error('Acknowledge failed:', err)
    }
  }

  const approveRecommendation = async (id: string, note?: string) => {
    try {
      await api.post(`/api/ai/recommendations/${id}/approve`, { note })
      setRecommendations(prev => prev.map(r => 
        r.id === id ? { ...r, status: 'approved' as const, feedback_note: note || null } : r
      ))
    } catch (err) {
      console.error('Approve failed:', err)
    }
  }

  const rejectRecommendation = async (id: string, note?: string) => {
    try {
      await api.post(`/api/ai/recommendations/${id}/reject`, { note })
      setRecommendations(prev => prev.map(r => 
        r.id === id ? { ...r, status: 'rejected' as const, feedback_note: note || null } : r
      ))
    } catch (err) {
      console.error('Reject failed:', err)
    }
  }

  // Trigger scheduled job (Phase 4.2)
  const triggerSchedulerJob = async (jobId: string) => {
    setRunningJob(jobId)
    try {
      await api.post(`/api/ai/scheduler/trigger/${jobId}`)
      // Refresh data after job
      await fetchData()
    } catch (err) {
      console.error(`Scheduler job ${jobId} failed:`, err)
    } finally {
      setRunningJob(null)
    }
  }

  // Governance tag functions (Phase 5.1)
  const startEditingGovernance = (rec: AIRecommendation) => {
    setEditingGovernance(rec.id)
    setGovernanceForm({
      priority: rec.priority || '',
      category: rec.category || '',
      risk_level: rec.risk_level || '',
      tags: rec.tags ? rec.tags.join(', ') : '',
      governance_note: rec.governance_note || '',
    })
  }

  const cancelEditingGovernance = () => {
    setEditingGovernance(null)
    setGovernanceForm({ priority: '', category: '', risk_level: '', tags: '', governance_note: '' })
  }

  const saveGovernance = async (id: string) => {
    setSavingGovernance(true)
    try {
      const payload: Record<string, unknown> = {}
      if (governanceForm.priority) payload.priority = governanceForm.priority
      if (governanceForm.category) payload.category = governanceForm.category
      if (governanceForm.risk_level) payload.risk_level = governanceForm.risk_level
      if (governanceForm.tags) {
        payload.tags = governanceForm.tags.split(',').map(t => t.trim()).filter(Boolean)
      }
      if (governanceForm.governance_note) payload.governance_note = governanceForm.governance_note

      const res = await api.patch(`/api/ai/recommendations/${id}/governance`, payload)
      
      // Update local state with response
      setRecommendations(prev => prev.map(r => 
        r.id === id ? {
          ...r,
          priority: res.data.priority,
          category: res.data.category,
          risk_level: res.data.risk_level,
          tags: res.data.tags,
          governance_note: res.data.governance_note,
        } : r
      ))
      setEditingGovernance(null)
    } catch (err) {
      console.error('Save governance failed:', err)
    } finally {
      setSavingGovernance(false)
    }
  }

  useEffect(() => {
    fetchData()
    fetchAdminUsers()
  }, [filter, categoryTab, priorityFilter, riskFilter, govCategoryFilter, assignedFilter])

  // Empty state component
  const EmptyState = () => (
    <div className="flex flex-col items-center justify-center py-16 text-gray-400">
      <div className="w-24 h-24 mb-6 rounded-full bg-gray-800/50 flex items-center justify-center">
        <Brain className="w-12 h-12 text-gray-600" />
      </div>
      <h3 className="text-xl font-semibold text-gray-300 mb-2">No AI Insights Yet</h3>
      <p className="text-center max-w-md mb-6">
        The AI advisory system is ready to analyze your business data.
        Run an analysis to generate demand forecasts, production recommendations,
        and waste alerts.
      </p>
      <button
        onClick={runAnalysis}
        disabled={runningAnalysis}
        className="flex items-center gap-2 px-4 py-2 bg-indigo-600 hover:bg-indigo-700 
                   rounded-lg font-medium transition-colors disabled:opacity-50"
      >
        {runningAnalysis ? (
          <>
            <Loader2 className="w-4 h-4 animate-spin" />
            Analyzing...
          </>
        ) : (
          <>
            <Sparkles className="w-4 h-4" />
            Run AI Analysis
          </>
        )}
      </button>
      <p className="text-xs text-gray-500 mt-4">
        AI Infrastructure Skeleton - Logic will be implemented in Phase AI.2
      </p>
    </div>
  )

  return (
    <div className="h-full flex flex-col bg-gray-900 text-gray-100">
      {/* Header */}
      <header className="bg-gray-800/50 border-b border-gray-700 px-4 py-3 flex-shrink-0">
        <div className="max-w-7xl mx-auto flex items-center justify-between">
          <div className="flex items-center gap-4">
            <button
              onClick={() => navigate(-1)}
              className="p-2 hover:bg-gray-700 rounded-lg transition-colors"
              aria-label="Go back"
            >
              <ArrowLeft className="w-5 h-5" />
            </button>
            <div className="flex items-center gap-2">
              <Brain className="w-6 h-6 text-indigo-400" />
              <h1 className="text-xl font-bold">AI Insights</h1>
            </div>
            {status && (
              <span className="px-2 py-1 bg-indigo-500/20 text-indigo-400 rounded-full text-xs font-medium">
                {status.active_count} active
              </span>
            )}
          </div>
          
          <div className="flex items-center gap-3">
            {/* Status indicator */}
            <div className="flex items-center gap-2 text-sm text-gray-400">
              <div className={clsx(
                'w-2 h-2 rounded-full',
                status?.engine_status === 'ready' ? 'bg-green-400' : 'bg-amber-400'
              )} />
              <span className="capitalize">{status?.engine_status || 'Loading...'}</span>
            </div>
            
            {/* Run Analysis button (generates insights) */}
            <button
              onClick={runAnalysis}
              disabled={runningAnalysis || runningRecommendations}
              className="flex items-center gap-2 px-3 py-1.5 bg-indigo-600 hover:bg-indigo-700 
                         rounded-lg text-sm font-medium transition-colors disabled:opacity-50"
              title="Analyze business data to generate insights"
            >
              {runningAnalysis ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin" />
                  Analyzing...
                </>
              ) : (
                <>
                  <Sparkles className="w-4 h-4" />
                  Run Insights
                </>
              )}
            </button>

            {/* Generate Recommendations button (Phase 9.2) */}
            <button
              onClick={runRecommendations}
              disabled={runningAnalysis || runningRecommendations}
              className="flex items-center gap-2 px-3 py-1.5 bg-emerald-600 hover:bg-emerald-700 
                         rounded-lg text-sm font-medium transition-colors disabled:opacity-50"
              title="Generate suggestions from existing insights"
            >
              {runningRecommendations ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin" />
                  Generating...
                </>
              ) : (
                <>
                  <Lightbulb className="w-4 h-4" />
                  Get Suggestions
                </>
              )}
            </button>
            
            {/* Refresh button */}
            <button
              onClick={fetchData}
              disabled={loading}
              className="p-2 hover:bg-gray-700 rounded-lg transition-colors disabled:opacity-50"
              aria-label="Refresh"
            >
              <RefreshCw className={clsx('w-5 h-5', loading && 'animate-spin')} />
            </button>
          </div>
        </div>
      </header>

      {/* Main content - scrollable */}
      <main className="flex-1 overflow-y-auto">
        <div className="max-w-7xl mx-auto px-4 py-6">

        {/* Scheduler Status Panel (Phase 4.2) */}
        {schedulerStatus && (
          <div className="bg-gray-800/30 border border-gray-700 rounded-lg p-4 mb-6">
            <div className="flex items-center justify-between mb-3">
              <div className="flex items-center gap-2">
                <Clock className="w-5 h-5 text-gray-400" />
                <h3 className="font-medium text-gray-200">AI Scheduler</h3>
                <span className={clsx(
                  'px-2 py-0.5 rounded-full text-xs font-medium',
                  schedulerStatus.running
                    ? 'bg-green-500/20 text-green-400'
                    : 'bg-gray-500/20 text-gray-400'
                )}>
                  {schedulerStatus.running ? 'Running' : 'Manual Mode'}
                </span>
              </div>
              <div className="flex items-center gap-2">
                <button
                  onClick={() => triggerSchedulerJob('expiry_check')}
                  disabled={!!runningJob}
                  className="flex items-center gap-1 px-2 py-1 text-xs bg-gray-700 hover:bg-gray-600 
                             rounded transition-colors disabled:opacity-50"
                  title="Check for expired recommendations"
                >
                  {runningJob === 'expiry_check' ? (
                    <Loader2 className="w-3 h-3 animate-spin" />
                  ) : (
                    <XCircle className="w-3 h-3" />
                  )}
                  Expire Check
                </button>
                <button
                  onClick={() => triggerSchedulerJob('nightly_analysis')}
                  disabled={!!runningJob}
                  className="flex items-center gap-1 px-2 py-1 text-xs bg-indigo-700 hover:bg-indigo-600 
                             rounded transition-colors disabled:opacity-50"
                  title="Run full analysis cycle"
                >
                  {runningJob === 'nightly_analysis' ? (
                    <Loader2 className="w-3 h-3 animate-spin" />
                  ) : (
                    <Sparkles className="w-3 h-3" />
                  )}
                  Full Analysis
                </button>
              </div>
            </div>
            <div className="grid grid-cols-3 gap-4 text-xs text-gray-400">
              <div>
                <span className="text-gray-500">Last Analysis:</span>{' '}
                <span className="text-gray-300">
                  {schedulerStatus.last_auto_run
                    ? formatRelativeTime(schedulerStatus.last_auto_run)
                    : 'Never'}
                </span>
              </div>
              <div>
                <span className="text-gray-500">Last Expiry Check:</span>{' '}
                <span className="text-gray-300">
                  {schedulerStatus.last_expiry_check
                    ? formatRelativeTime(schedulerStatus.last_expiry_check)
                    : 'Never'}
                </span>
              </div>
              <div>
                <span className="text-gray-500">Last Cleanup:</span>{' '}
                <span className="text-gray-300">
                  {schedulerStatus.last_cleanup
                    ? formatRelativeTime(schedulerStatus.last_cleanup)
                    : 'Never'}
                </span>
              </div>
            </div>
          </div>
        )}

        {/* Category tabs (Insights vs Recommendations) */}
        <div className="flex gap-2 mb-4">
          <button
            onClick={() => { setCategoryTab('all'); setFilter('all') }}
            className={clsx(
              'px-4 py-2 rounded-lg text-sm font-medium transition-colors',
              categoryTab === 'all'
                ? 'bg-gray-700 text-white'
                : 'text-gray-400 hover:bg-gray-800'
            )}
          >
            All
          </button>
          <button
            onClick={() => { setCategoryTab('insight'); setFilter('all') }}
            className={clsx(
              'flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-colors',
              categoryTab === 'insight'
                ? 'bg-indigo-600/80 text-white'
                : 'text-gray-400 hover:bg-gray-800'
            )}
          >
            <Brain className="w-4 h-4" />
            Insights (Facts)
          </button>
          <button
            onClick={() => { setCategoryTab('recommendation'); setFilter('all') }}
            className={clsx(
              'flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-colors',
              categoryTab === 'recommendation'
                ? 'bg-emerald-600/80 text-white'
                : 'text-gray-400 hover:bg-gray-800'
            )}
          >
            <Lightbulb className="w-4 h-4" />
            Suggestions (AI)
          </button>
        </div>

        {/* Filter tabs */}
        <div className="flex gap-2 mb-6 overflow-x-auto pb-2">
          <button
            onClick={() => setFilter('all')}
            className={clsx(
              'px-3 py-1.5 rounded-lg text-sm font-medium transition-colors whitespace-nowrap',
              filter === 'all'
                ? 'bg-gray-700 text-white'
                : 'text-gray-400 hover:bg-gray-800'
            )}
          >
            All Types
          </button>
          {Object.entries(typeConfig)
            .filter(([, config]) => categoryTab === 'all' || config.category === categoryTab)
            .map(([type, config]) => {
            const Icon = config.icon
            return (
              <button
                key={type}
                onClick={() => setFilter(type)}
                className={clsx(
                  'flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm font-medium transition-colors whitespace-nowrap',
                  filter === type
                    ? 'bg-gray-700 text-white'
                    : 'text-gray-400 hover:bg-gray-800'
                )}
              >
                <Icon className="w-4 h-4" />
                {config.label}
              </button>
            )
          })}
        </div>

        {/* Governance Filters Panel (Phase 5.1) */}
        <div className="mb-6">
          <button
            onClick={() => setShowFilters(!showFilters)}
            className="flex items-center gap-2 text-sm text-gray-400 hover:text-white transition-colors mb-3"
          >
            <Tag className="w-4 h-4" />
            {showFilters ? 'Hide' : 'Show'} Governance Filters
            {showFilters ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
            {(priorityFilter !== 'all' || riskFilter !== 'all' || govCategoryFilter !== 'all' || assignedFilter !== 'all') && (
              <span className="px-1.5 py-0.5 bg-indigo-500/20 text-indigo-400 rounded text-xs">
                Filters active
              </span>
            )}
          </button>
          
          {showFilters && (
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4 p-4 bg-gray-800/30 border border-gray-700 rounded-lg">
              {/* Priority Filter */}
              <div>
                <label className="block text-xs text-gray-500 mb-1">Priority</label>
                <select
                  value={priorityFilter}
                  onChange={(e) => setPriorityFilter(e.target.value)}
                  className="w-full bg-gray-700 border border-gray-600 rounded px-3 py-1.5 text-sm text-white focus:border-indigo-500 focus:outline-none"
                >
                  <option value="all">All Priorities</option>
                  <option value="critical">Critical</option>
                  <option value="high">High</option>
                  <option value="medium">Medium</option>
                  <option value="low">Low</option>
                </select>
              </div>
              
              {/* Risk Level Filter */}
              <div>
                <label className="block text-xs text-gray-500 mb-1">Risk Level</label>
                <select
                  value={riskFilter}
                  onChange={(e) => setRiskFilter(e.target.value)}
                  className="w-full bg-gray-700 border border-gray-600 rounded px-3 py-1.5 text-sm text-white focus:border-indigo-500 focus:outline-none"
                >
                  <option value="all">All Risk Levels</option>
                  <option value="high_risk">High Risk</option>
                  <option value="medium_risk">Medium Risk</option>
                  <option value="low_risk">Low Risk</option>
                  <option value="no_risk">No Risk</option>
                </select>
              </div>
              
              {/* Category Filter */}
              <div>
                <label className="block text-xs text-gray-500 mb-1">Category</label>
                <select
                  value={govCategoryFilter}
                  onChange={(e) => setGovCategoryFilter(e.target.value)}
                  className="w-full bg-gray-700 border border-gray-600 rounded px-3 py-1.5 text-sm text-white focus:border-indigo-500 focus:outline-none"
                >
                  <option value="all">All Categories</option>
                  <option value="inventory">Inventory</option>
                  <option value="production">Production</option>
                  <option value="procurement">Procurement</option>
                  <option value="sales">Sales</option>
                  <option value="operations">Operations</option>
                  <option value="compliance">Compliance</option>
                </select>
              </div>
              
              {/* Assigned Admin Filter */}
              <div>
                <label className="block text-xs text-gray-500 mb-1">Assigned To</label>
                <select
                  value={assignedFilter}
                  onChange={(e) => setAssignedFilter(e.target.value)}
                  className="w-full bg-gray-700 border border-gray-600 rounded px-3 py-1.5 text-sm text-white focus:border-indigo-500 focus:outline-none"
                >
                  <option value="all">All / Unassigned</option>
                  {adminUsers.map(admin => (
                    <option key={admin.id} value={String(admin.id)}>
                      {admin.username}
                    </option>
                  ))}
                </select>
              </div>
              
              {/* Clear filters button */}
              {(priorityFilter !== 'all' || riskFilter !== 'all' || govCategoryFilter !== 'all' || assignedFilter !== 'all') && (
                <div className="col-span-2 md:col-span-4 pt-2 border-t border-gray-700">
                  <button
                    onClick={() => {
                      setPriorityFilter('all')
                      setRiskFilter('all')
                      setGovCategoryFilter('all')
                      setAssignedFilter('all')
                    }}
                    className="text-xs text-gray-400 hover:text-white transition-colors"
                  >
                    Clear all governance filters
                  </button>
                </div>
              )}
            </div>
          )}
        </div>

        {/* Error state */}
        {error && (
          <div className="bg-red-500/10 border border-red-500/30 rounded-lg p-4 mb-6 flex items-center gap-3">
            <AlertTriangle className="w-5 h-5 text-red-400 flex-shrink-0" />
            <p className="text-red-400">{error}</p>
          </div>
        )}

        {/* Loading state */}
        {loading && (
          <div className="flex items-center justify-center py-16">
            <Loader2 className="w-8 h-8 animate-spin text-indigo-400" />
          </div>
        )}

        {/* Empty state */}
        {!loading && !error && recommendations.length === 0 && <EmptyState />}

        {/* Recommendations grid */}
        {!loading && recommendations.length > 0 && (
          <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
            {recommendations.map(rec => {
              const config = typeConfig[rec.type] || { 
                icon: Lightbulb, 
                color: 'text-gray-400 bg-gray-500/20', 
                label: rec.type,
                category: 'insight'
              }
              const Icon = config.icon
              const isRecommendation = config.category === 'recommendation'
              const isExpanded = expandedCards.has(rec.id)
              const explanation = Array.isArray(rec.explanation) ? rec.explanation : []
              const riskNote = explanation.length > 0 ? explanation[explanation.length - 1] : null
              const reasoningChain = explanation.slice(0, -1)
              const canTakeAction = rec.status === 'pending' || rec.status === 'acknowledged'

              return (
                <div
                  key={rec.id}
                  className={clsx(
                    "bg-gray-800/50 border rounded-lg p-4 transition-colors",
                    rec.status === 'approved' && "border-green-700/50",
                    rec.status === 'rejected' && "border-red-700/30 opacity-75",
                    rec.status !== 'approved' && rec.status !== 'rejected' && isRecommendation && "border-emerald-700/50 hover:border-emerald-600",
                    rec.status !== 'approved' && rec.status !== 'rejected' && !isRecommendation && "border-gray-700 hover:border-gray-600"
                  )}
                >
                  {/* Header */}
                  <div className="flex items-start justify-between mb-3">
                    <div className={clsx('p-2 rounded-lg', config.color)}>
                      <Icon className="w-5 h-5" />
                    </div>
                    <div className="flex items-center gap-1">
                      <StatusBadge status={rec.status} />
                      {isRecommendation && rec.status === 'pending' && (
                        <span className="px-2 py-0.5 bg-emerald-500/20 text-emerald-400 rounded-full text-xs font-medium">
                          Suggestion
                        </span>
                      )}
                      <button
                        onClick={() => startEditingGovernance(rec)}
                        className="p-1 hover:bg-gray-700 rounded transition-colors text-gray-500 hover:text-indigo-400"
                        title="Edit governance tags"
                      >
                        <Tag className="w-4 h-4" />
                      </button>
                      <button
                        onClick={() => dismissRecommendation(rec.id)}
                        className="p-1 hover:bg-gray-700 rounded transition-colors text-gray-500 hover:text-gray-300"
                        title="Dismiss"
                      >
                        <XCircle className="w-4 h-4" />
                      </button>
                    </div>
                  </div>

                  {/* Type label */}
                  <p className="text-xs text-gray-500 mb-1">{config.label}</p>

                  {/* Summary */}
                  <h3 className="font-medium text-gray-200 mb-2">{rec.summary}</h3>

                  {/* Reasoning chain (for recommendations) */}
                  {isRecommendation && reasoningChain.length > 0 && (
                    <div className="mb-3">
                      <button
                        onClick={() => toggleCardExpanded(rec.id)}
                        className="flex items-center gap-1 text-xs text-gray-400 hover:text-gray-300 transition-colors"
                      >
                        {isExpanded ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
                        {isExpanded ? 'Hide reasoning' : 'Show reasoning'}
                      </button>
                      {isExpanded && (
                        <ul className="mt-2 space-y-1 text-xs text-gray-400 pl-3 border-l border-gray-700">
                          {reasoningChain.map((reason, idx) => (
                            <li key={idx}>• {String(reason)}</li>
                          ))}
                        </ul>
                      )}
                    </div>
                  )}

                  {/* Risk note (for recommendations) */}
                  {isRecommendation && riskNote && (
                    <div className="mb-3 px-2 py-1.5 bg-amber-500/10 border border-amber-500/20 rounded text-xs text-amber-400">
                      {String(riskNote)}
                    </div>
                  )}

                  {/* Feedback note (if provided) */}
                  {rec.feedback_note && (
                    <div className="mb-3 px-2 py-1.5 bg-blue-500/10 border border-blue-500/20 rounded text-xs text-blue-400 flex items-start gap-1">
                      <MessageSquare className="w-3 h-3 mt-0.5 flex-shrink-0" />
                      <span>{rec.feedback_note}</span>
                    </div>
                  )}

                  {/* Governance Tags Section (Phase 5.1) */}
                  {(rec.priority || rec.category || rec.risk_level || (rec.tags && rec.tags.length > 0)) && editingGovernance !== rec.id && (
                    <div className="mb-3 flex flex-wrap gap-1.5">
                      <PriorityBadge priority={rec.priority} />
                      <CategoryBadge category={rec.category} />
                      <RiskBadge riskLevel={rec.risk_level} />
                      {rec.tags && rec.tags.map((tag, idx) => (
                        <span key={idx} className="flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium text-gray-400 bg-gray-700/50">
                          <Tag className="w-3 h-3" />
                          {tag}
                        </span>
                      ))}
                    </div>
                  )}
                  {rec.governance_note && editingGovernance !== rec.id && (
                    <div className="mb-3 px-2 py-1.5 bg-purple-500/10 border border-purple-500/20 rounded text-xs text-purple-400 flex items-start gap-1">
                      <Edit3 className="w-3 h-3 mt-0.5 flex-shrink-0" />
                      <span>{rec.governance_note}</span>
                    </div>
                  )}

                  {/* Governance Edit Form (Phase 5.1) */}
                  {editingGovernance === rec.id && governanceOptions && (
                    <div className="mb-3 p-3 bg-gray-900/50 border border-gray-700 rounded-lg space-y-3">
                      <div className="flex items-center justify-between mb-2">
                        <span className="text-xs font-medium text-gray-300 flex items-center gap-1">
                          <Tag className="w-3 h-3" />
                          Edit Governance Tags
                        </span>
                        <button
                          onClick={cancelEditingGovernance}
                          className="p-1 hover:bg-gray-700 rounded text-gray-500 hover:text-gray-300"
                        >
                          <X className="w-3 h-3" />
                        </button>
                      </div>
                      <div className="grid grid-cols-2 gap-2">
                        <select
                          value={governanceForm.priority}
                          onChange={(e) => setGovernanceForm(f => ({ ...f, priority: e.target.value }))}
                          className="px-2 py-1 text-xs bg-gray-800 border border-gray-700 rounded text-gray-300"
                        >
                          <option value="">Priority...</option>
                          {governanceOptions.priorities.map(p => (
                            <option key={p.value} value={p.value}>{p.label}</option>
                          ))}
                        </select>
                        <select
                          value={governanceForm.category}
                          onChange={(e) => setGovernanceForm(f => ({ ...f, category: e.target.value }))}
                          className="px-2 py-1 text-xs bg-gray-800 border border-gray-700 rounded text-gray-300"
                        >
                          <option value="">Category...</option>
                          {governanceOptions.categories.map(c => (
                            <option key={c.value} value={c.value}>{c.label}</option>
                          ))}
                        </select>
                        <select
                          value={governanceForm.risk_level}
                          onChange={(e) => setGovernanceForm(f => ({ ...f, risk_level: e.target.value }))}
                          className="px-2 py-1 text-xs bg-gray-800 border border-gray-700 rounded text-gray-300"
                        >
                          <option value="">Risk Level...</option>
                          {governanceOptions.risk_levels.map(r => (
                            <option key={r.value} value={r.value}>{r.label}</option>
                          ))}
                        </select>
                        <input
                          type="text"
                          placeholder="Tags (comma-separated)"
                          value={governanceForm.tags}
                          onChange={(e) => setGovernanceForm(f => ({ ...f, tags: e.target.value }))}
                          className="px-2 py-1 text-xs bg-gray-800 border border-gray-700 rounded text-gray-300 placeholder-gray-500"
                        />
                      </div>
                      <textarea
                        placeholder="Governance note..."
                        value={governanceForm.governance_note}
                        onChange={(e) => setGovernanceForm(f => ({ ...f, governance_note: e.target.value }))}
                        className="w-full px-2 py-1 text-xs bg-gray-800 border border-gray-700 rounded text-gray-300 placeholder-gray-500 resize-none"
                        rows={2}
                      />
                      <div className="flex justify-end gap-2">
                        <button
                          onClick={cancelEditingGovernance}
                          className="px-2 py-1 text-xs text-gray-400 hover:text-gray-300"
                        >
                          Cancel
                        </button>
                        <button
                          onClick={() => saveGovernance(rec.id)}
                          disabled={savingGovernance}
                          className="flex items-center gap-1 px-2 py-1 text-xs bg-indigo-600 hover:bg-indigo-700 text-white rounded disabled:opacity-50"
                        >
                          {savingGovernance ? (
                            <Loader2 className="w-3 h-3 animate-spin" />
                          ) : (
                            <Save className="w-3 h-3" />
                          )}
                          Save
                        </button>
                      </div>
                    </div>
                  )}

                  {/* Confidence & time */}
                  <div className="flex items-center justify-between text-xs">
                    <ConfidenceBadge confidence={rec.confidence} />
                    <span className="text-gray-500 flex items-center gap-1">
                      <Clock className="w-3 h-3" />
                      {formatRelativeTime(rec.created_at)}
                    </span>
                  </div>

                  {/* Action buttons (Phase 4.1) */}
                  {isRecommendation && canTakeAction && (
                    <div className="mt-3 pt-3 border-t border-gray-700 flex items-center gap-2">
                      {rec.status === 'pending' && (
                        <button
                          onClick={() => acknowledgeRecommendation(rec.id)}
                          className="flex items-center gap-1 px-2 py-1 text-xs bg-blue-600/20 hover:bg-blue-600/30 text-blue-400 rounded transition-colors"
                          title="Mark as reviewed"
                        >
                          <Eye className="w-3 h-3" />
                          Review
                        </button>
                      )}
                      <button
                        onClick={() => approveRecommendation(rec.id)}
                        className="flex items-center gap-1 px-2 py-1 text-xs bg-green-600/20 hover:bg-green-600/30 text-green-400 rounded transition-colors"
                        title="Approve this suggestion"
                      >
                        <Check className="w-3 h-3" />
                        Approve
                      </button>
                      <button
                        onClick={() => rejectRecommendation(rec.id)}
                        className="flex items-center gap-1 px-2 py-1 text-xs bg-red-600/20 hover:bg-red-600/30 text-red-400 rounded transition-colors"
                        title="Reject this suggestion"
                      >
                        <X className="w-3 h-3" />
                        Reject
                      </button>
                    </div>
                  )}

                  {/* Generated by indicator (only if no actions) */}
                  {(!isRecommendation || !canTakeAction) && (
                    <div className="mt-3 pt-3 border-t border-gray-700 text-xs text-gray-500">
                      Generated by: {rec.generated_by}
                    </div>
                  )}
                </div>
              )
            })}
          </div>
        )}

        {/* Info card about AI system */}
        <div className="mt-8 bg-gray-800/30 border border-gray-700 rounded-lg p-6">
          <h2 className="text-lg font-semibold mb-4 flex items-center gap-2">
            <Lightbulb className="w-5 h-5 text-amber-400" />
            About AI Advisory System
          </h2>
          <div className="grid md:grid-cols-2 lg:grid-cols-4 gap-4 text-sm">
            <div className="flex items-start gap-3">
              <TrendingUp className="w-5 h-5 text-blue-400 flex-shrink-0 mt-0.5" />
              <div>
                <p className="font-medium text-gray-200">Demand Forecasting</p>
                <p className="text-gray-400">Predicts future demand based on sales patterns</p>
              </div>
            </div>
            <div className="flex items-start gap-3">
              <Package className="w-5 h-5 text-green-400 flex-shrink-0 mt-0.5" />
              <div>
                <p className="font-medium text-gray-200">Production Planning</p>
                <p className="text-gray-400">Recommends optimal production schedules</p>
              </div>
            </div>
            <div className="flex items-start gap-3">
              <AlertTriangle className="w-5 h-5 text-amber-400 flex-shrink-0 mt-0.5" />
              <div>
                <p className="font-medium text-gray-200">Waste Intelligence</p>
                <p className="text-gray-400">Identifies waste patterns and yield issues</p>
              </div>
            </div>
            <div className="flex items-start gap-3">
              <Users className="w-5 h-5 text-pink-400 flex-shrink-0 mt-0.5" />
              <div>
                <p className="font-medium text-gray-200">Sales Intelligence</p>
                <p className="text-gray-400">Agent performance and sales trends</p>
              </div>
            </div>
          </div>
          <p className="text-xs text-gray-500 mt-4 pt-4 border-t border-gray-700">
            🔒 Safety: AI reads from business data and writes ONLY to recommendations. 
            All actions require human approval.
          </p>
        </div>
        </div>
      </main>
    </div>
  )
}
