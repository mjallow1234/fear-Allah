/**
 * Task Inbox Page
 * Phase 7.2 - Task Inbox UI
 * 
 * Main inbox view for automation tasks.
 * Shows user's assignments and created tasks.
 */
import { useEffect, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { 
  ArrowLeft, 
  ClipboardList, 
  User, 
  Plus,
  Loader2,
  RefreshCw,
  AlertCircle,
  Search
} from 'lucide-react'
import clsx from 'clsx'
import { useAuthStore } from '../stores/authStore'
import { useTaskStore, AutomationTask } from '../stores/taskStore'
import { subscribeToTasks } from '../realtime/tasks'
import TaskCard from '../components/Tasks/TaskCard'
import TaskDetailsDrawer from '../components/Tasks/TaskDetailsDrawer'

type TabType = 'my-tasks' | 'created' | 'completed' | 'available' | 'all'

export default function TaskInboxPage() {
  const navigate = useNavigate()
  const [searchParams, setSearchParams] = useSearchParams()
  const user = useAuthStore((state) => state.user)
  // Read the active business/operational role from the authoritative currentUser (used by the UI header)
  const operationalRoleName = useAuthStore((state) => state.currentUser?.operational_role_name ?? state.user?.role)

  const {
    tasks,
    myAssignments,
    availableTasks,
    selectedTask,
    taskEvents,
    loading,
    loadingTask,
    completingTaskId,
    error,
    fetchMyAssignments,
    fetchMyTasks,
    fetchAvailableTasks,
    claimTask,
    fetchTaskDetails,
    completeAssignment,
    setSelectedTask,
    clearError,
  } = useTaskStore()
  
  // Admins default to 'all' to see every task; frontend must respect backend as source-of-truth
  const [activeTab, setActiveTab] = useState<TabType>(user?.is_system_admin ? 'all' : 'my-tasks')
  
  // Search and filter state
  const [searchValue, setSearchValue] = useState('')
  const [orderTypeFilter, setOrderTypeFilter] = useState('')
  const [debouncedSearch, setDebouncedSearch] = useState('')
  
  // Debounce search input
  useEffect(() => {
    const timer = setTimeout(() => {
      setDebouncedSearch(searchValue)
    }, 400)
    return () => clearTimeout(timer)
  }, [searchValue])
  
  // Subscribe to task events on mount
  useEffect(() => {
    const unsubscribe = subscribeToTasks()
    return () => unsubscribe()
  }, [])
  
  // Handle URL query param to open a specific task
  useEffect(() => {
    const taskId = searchParams.get('task')
    if (taskId) {
      const id = parseInt(taskId, 10)
      if (!isNaN(id)) {
        // Fetch and select the task
        fetchTaskDetails(id)
      }
      // Clear the search param after reading it
      searchParams.delete('task')
      setSearchParams(searchParams, { replace: true })
    }
  }, [searchParams, setSearchParams, fetchTaskDetails])
  
  // Fetch data on mount and tab change (with filters)
  useEffect(() => {
    if (activeTab === 'my-tasks') {
      const filters: { search?: string; order_type?: string } = {}
      if (debouncedSearch) filters.search = debouncedSearch
      if (orderTypeFilter) filters.order_type = orderTypeFilter
      fetchMyAssignments(Object.keys(filters).length > 0 ? filters : undefined)
    } else if (activeTab === 'available') {
      // Use operational role name from currentUser (UI header) and normalize to backend enum (lowercase, underscores)
      const role = operationalRoleName ? operationalRoleName.toLowerCase().replace(/\s+/g, '_') : null
      fetchAvailableTasks(role)
    } else {
      fetchMyTasks()
    }
  }, [activeTab, fetchMyAssignments, fetchMyTasks, fetchAvailableTasks, operationalRoleName, debouncedSearch, orderTypeFilter])
  
  // Canonical task filter helpers (single source of truth)
  const normalizeStatus = (s?: string) => (s || '').toString().toLowerCase()

  const isAvailable = (task: AutomationTask) => {
    // Some backends may expose `claimed_by_user_id` on the task; if present, respect it
    const claimedBy = (task as any).claimed_by_user_id
    return normalizeStatus(task.status) === 'open' && !claimedBy && !(task.assignments?.length)
  }

  const isMyTask = (task: AutomationTask, userId?: number) => {
    const s = normalizeStatus(task.status)
    if (!userId) return false
    return (s === 'claimed' || s === 'in_progress') && !!task.assignments?.some(a => a.user_id === userId)
  }

  const isCompleted = (task: AutomationTask, userId?: number) => {
    const s = normalizeStatus(task.status)
    if (!userId) return false
    return s === 'completed' && !!task.assignments?.some(a => a.user_id === userId)
  }

  const isAll = (task: AutomationTask, userId?: number) => {
    return task.created_by_id === userId || !!task.assignments?.some(a => a.user_id === userId)
  }

  // Get tasks based on active tab using canonical helpers
  const getFilteredTasks = (): AutomationTask[] => {
    const userId = user?.id || 0

    if (activeTab === 'my-tasks') {
      const fromTasks = tasks.filter(t => isMyTask(t, userId))
      if (fromTasks.length > 0) return fromTasks
      // Fallback: when detailed task objects are not yet loaded, return placeholder entries derived from myAssignments
      if (myAssignments && myAssignments.length > 0) {
        return myAssignments.map(a => ({ __assignmentOnly: true, assignment: a } as any)) as unknown as AutomationTask[]
      }
      return []
    } else if (activeTab === 'created') {
      return tasks.filter(t => t.created_by_id === user?.id)
    } else if (activeTab === 'all') {
      return tasks.filter(t => isAll(t, user?.id || 0))
    } else if (activeTab === 'available') {
      // Use server-provided availableTasks but apply canonical filter as a safety check
      return (availableTasks || []).filter(isAvailable)
    } else {
      // completed
      return tasks.filter(t => isCompleted(t, user?.id))
    }
  }

  const filteredTasks = getFilteredTasks()
  const tasksToRender = filteredTasks
  
  // Get assignment for a task
  const getAssignment = (taskId: number) => {
    return myAssignments.find(a => a.task_id === taskId)
  }
  
  const handleComplete = async (taskId: number) => {
    const success = await completeAssignment(taskId)
    if (success) {
      // Toast would be nice here
      console.log('[TaskInbox] Task completed successfully')
    }
  }
  
  const handleRefresh = () => {
    if (activeTab === 'my-tasks') {
      fetchMyAssignments()
    } else {
      fetchMyTasks()
    }
  }
  
  // Count pending assignments
  const pendingCount = myAssignments.filter(a => a.status === 'PENDING' || a.status === 'IN_PROGRESS').length

  console.log('[DEBUG][TaskInbox]', {
    activeTab,
    availableTasksCount: availableTasks?.length,
    tasksCount: tasks?.length,
    filteredTasksCount: filteredTasks?.length,
  });

  return (
    <div className="page-container flex flex-col h-full overflow-hidden" style={{ backgroundColor: 'var(--main-bg)' }}>
      {/* Header */}
      <div className="flex-shrink-0 px-6 py-4" style={{ backgroundColor: 'var(--panel-bg)', borderBottom: '1px solid var(--sidebar-border)' }}>
        <div className="max-w-4xl mx-auto flex items-center justify-between">
          <div className="flex items-center gap-4">
            <button
              onClick={() => navigate(-1)}
              className="p-2 transition-colors"
              style={{ color: 'var(--text-secondary)' }}
            >
              <ArrowLeft size={20} />
            </button>
            <div>
              <h1 className="text-xl font-semibold flex items-center gap-2" style={{ color: 'var(--text-primary)' }}>
                <ClipboardList size={24} />
                Task Inbox
              </h1>
              <p className="text-sm" style={{ color: 'var(--text-secondary)' }}>
                {pendingCount} pending task{pendingCount !== 1 ? 's' : ''}
              </p>
            </div>
          </div>
          <button
            onClick={handleRefresh}
            disabled={loading}
            className={clsx('flex items-center gap-2 px-3 py-2 rounded-lg transition-colors')}
            style={loading ? { backgroundColor: 'var(--input-bg)', color: 'var(--text-muted)', cursor: 'not-allowed' } : { backgroundColor: 'var(--accent)', color: 'var(--text-primary)' }}
          >
            <RefreshCw size={16} className={loading ? 'animate-spin' : ''} />
            Refresh
          </button>
        </div>
      </div>
      
      {/* Tabs */}
      <div className="page-tabs flex-shrink-0 min-h-12 bg-[#2b2d31] border-b border-[#1f2023] px-6 relative z-10 overflow-visible">
        <div className="max-w-4xl mx-auto flex flex-wrap gap-2 overflow-x-auto sm:overflow-visible py-2">
          {!user?.is_system_admin && (
            <button
              onClick={() => setActiveTab('my-tasks')}
              className={clsx(
                'shrink-0 whitespace-nowrap flex items-center gap-2 px-4 py-2 text-sm font-medium transition-colors border-b-2',
                activeTab === 'my-tasks'
                  ? 'text-white border-[#5865f2]'
                  : 'text-[#949ba4] border-transparent hover:text-white'
              )}
            >
              <User size={16} />
              My Tasks
              {pendingCount > 0 && (
                <span className="ml-1 px-1.5 py-0.5 bg-red-500 text-white text-xs rounded-full">
                  {pendingCount}
                </span>
              )}
            </button>
          )}

          <button
            onClick={() => setActiveTab('all')}
            className={clsx(
              'shrink-0 whitespace-nowrap flex items-center gap-2 px-4 py-2 text-sm font-medium transition-colors border-b-2',
              activeTab === 'all'
                ? 'text-white border-[#5865f2]'
                : 'text-[#949ba4] border-transparent hover:text-white'
            )}
          >
            <ClipboardList size={16} />
            All Tasks
          </button>

          <button
            onClick={() => setActiveTab('available')}
            className={clsx(
              'shrink-0 whitespace-nowrap flex items-center gap-2 px-4 py-2 text-sm font-medium transition-colors border-b-2',
              activeTab === 'available'
                ? 'text-white border-[#5865f2]'
                : 'text-[#949ba4] border-transparent hover:text-white'
            )}
          >
            <User size={16} />
            Available
          </button>

          <button
            onClick={() => setActiveTab('created')}
            className={clsx(
              'shrink-0 whitespace-nowrap flex items-center gap-2 px-4 py-2 text-sm font-medium transition-colors border-b-2',
              activeTab === 'created'
                ? 'text-white border-[#5865f2]'
                : 'text-[#949ba4] border-transparent hover:text-white'
            )}
          >
            <Plus size={16} />
            Created by Me
          </button>
          <button
            onClick={() => setActiveTab('completed')}
            className={clsx(
              'shrink-0 whitespace-nowrap flex items-center gap-2 px-4 py-2 text-sm font-medium transition-colors border-b-2',
              activeTab === 'completed'
                ? 'text-white border-[#5865f2]'
                : 'text-[#949ba4] border-transparent hover:text-white'
            )}
          >
            Completed
          </button>
        </div>
      </div>
      
      {/* Search and Filter Bar - only show on My Tasks tab */}
      {activeTab === 'my-tasks' && (
        <div className="flex-shrink-0 bg-[#2b2d31] border-b border-[#1f2023] px-6 py-3">
          <div className="max-w-4xl mx-auto flex gap-4 items-center">
            {/* Search Input */}
            <div className="relative flex-1 max-w-xs">
              <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-[#949ba4]" />
              <input
                type="text"
                placeholder="Search by Order ID"
                value={searchValue}
                onChange={(e) => setSearchValue(e.target.value)}
                className="w-full pl-9 pr-3 py-2 bg-[#1e1f22] border border-[#1f2023] rounded-lg text-white placeholder-[#72767d] text-sm focus:outline-none focus:border-[#5865f2]"
              />
            </div>
            
            {/* Order Type Dropdown */}
            <select
              value={orderTypeFilter}
              onChange={(e) => setOrderTypeFilter(e.target.value)}
              className="px-3 py-2 bg-[#1e1f22] border border-[#1f2023] rounded-lg text-white text-sm focus:outline-none focus:border-[#5865f2] cursor-pointer"
            >
              <option value="">All Order Types</option>
              <option value="agent_retail">Agent Retail</option>
              <option value="agent_restock">Agent Restock</option>
              <option value="customer_wholesale">Customer Wholesale</option>
              <option value="store_keeper_restock">Storekeeper Restock</option>
            </select>
            
            {/* Clear Filters */}
            {(searchValue || orderTypeFilter) && (
              <button
                onClick={() => { setSearchValue(''); setOrderTypeFilter(''); }}
                className="text-sm text-[#949ba4] hover:text-white transition-colors"
              >
                Clear
              </button>
            )}
          </div>
        </div>
      )}
      
      {/* Error Banner */}
      {error && (
        <div className="flex-shrink-0 max-w-4xl mx-auto px-6 py-4">
          <div className="bg-red-500/10 border border-red-500/20 rounded-lg p-4 flex items-center gap-3">
            <AlertCircle className="text-red-400" size={20} />
            <span className="text-red-400 flex-1">{error}</span>
            <button
              onClick={clearError}
              className="text-red-400 hover:text-red-300 text-sm"
            >
              Dismiss
            </button>
          </div>
        </div>
      )}
      
      {/* Task List */}
      <div className="page-content flex-1 overflow-y-auto">
        <div className="max-w-4xl mx-auto py-6 px-6 pb-12">
          {loading ? (
            <div className="py-12 text-center">
              <Loader2 className="animate-spin mx-auto mb-4 text-[#5865f2]" size={32} />
              <p className="text-[#949ba4]">Loading tasks...</p>
            </div>
          ) : activeTab === 'my-tasks' && myAssignments.length === 0 ? (
            <div className="py-12 text-center">
              <ClipboardList size={48} className="mx-auto mb-4 text-[#949ba4] opacity-50" />
              <p className="text-[#949ba4]">No pending tasks</p>
              <p className="text-[#72767d] text-sm mt-1">
                Tasks will appear here when you're assigned to them
              </p>
            </div> 
  ) : activeTab === 'my-tasks' ? (
          // Show assignments directly when we don't have full task data
          <div className="space-y-3">
            {myAssignments.map((assignment) => {
              const task = tasks.find(t => t.id === assignment.task_id)
              if (!task) {
                // Show minimal assignment card when task isn't loaded
                return (
                  <div
                    key={assignment.id}
                    onClick={() => {
                      // Fetch and show task details
                      useTaskStore.getState().fetchTaskDetails(assignment.task_id).then(() => {
                        const t = useTaskStore.getState().selectedTask
                        if (t) setSelectedTask(t)
                      })
                    }}
                    className="p-4 rounded-lg cursor-pointer bg-[#2b2d31] border border-[#1f2023] hover:bg-[#35373c] transition-colors"
                  >
                    <div className="flex items-center justify-between">
                      <div>
                        <span className="text-white font-medium">Task #{assignment.task_id}</span>
                        {assignment.role_hint && (
                          <span className="text-[#72767d] text-sm ml-2">({assignment.role_hint})</span>
                        )}
                      </div>
                      <span className={clsx(
                        'text-sm',
                        assignment.status === 'DONE' ? 'text-green-400' :
                        assignment.status === 'PENDING' ? 'text-yellow-400' : 'text-blue-400'
                      )}>
                        {assignment.status}
                      </span>
                    </div>
                  </div>
                )
              }
              return (
                <TaskCard
                  key={task.id}
                  task={task}
                  assignment={assignment}
                  currentUserId={user?.id || 0}
                  isCompleting={completingTaskId === task.id}
                  onComplete={handleComplete}
                  onClick={() => setSelectedTask(task)}
                />
              )
            })}
          </div>
        ) : tasksToRender.length === 0 ? (
          <div className="py-12 text-center">
            <ClipboardList size={48} className="mx-auto mb-4 text-[#949ba4] opacity-50" />
            <p className="text-[#949ba4]">
              {activeTab === 'created' ? 'No tasks created by you' : activeTab === 'available' ? 'No available tasks' : 'No completed tasks'}
            </p>
            {activeTab === 'available' && (
              <p className="text-[#72767d] text-sm mt-1">Tasks matching your active role will appear here</p>
            )}
          </div>
        ) : (
          <div className="space-y-3">
            {tasksToRender.map((item: any) => {
              if (item && item.__assignmentOnly) {
                const assignment = item.assignment
                return (
                  <div
                    key={`assign-${assignment.id}`}
                    onClick={() => {
                      useTaskStore.getState().fetchTaskDetails(assignment.task_id).then(() => {
                        const t = useTaskStore.getState().selectedTask
                        if (t) setSelectedTask(t)
                      })
                    }}
                    className="p-4 rounded-lg cursor-pointer bg-[#2b2d31] border border-[#1f2023] hover:bg-[#35373c] transition-colors"
                  >
                    <div className="flex items-center justify-between">
                      <div>
                        <span className="text-white font-medium">Task #{assignment.task_id}</span>
                        {assignment.role_hint && (
                          <span className="text-[#72767d] text-sm ml-2">({assignment.role_hint})</span>
                        )}
                      </div>
                      <span className={clsx(
                        'text-sm',
                        assignment.status === 'DONE' ? 'text-green-400' :
                        assignment.status === 'PENDING' ? 'text-yellow-400' : 'text-blue-400'
                      )}>
                        {assignment.status}
                      </span>
                    </div>
                  </div>
                )
              }

              const task: AutomationTask = item
              const assignment = getAssignment(task.id)
              return (
                <TaskCard
                  key={task.id}
                  task={task}
                  assignment={assignment}
                  currentUserId={user?.id || 0}
                  isCompleting={completingTaskId === task.id}
                  onComplete={handleComplete}
                  onClick={() => setSelectedTask(task)}
                  isAvailableView={activeTab === 'available'}
                  onClaim={activeTab === 'available' ? async (taskId: number) => { await claimTask(taskId) } : undefined}
                />
              )
            })}
          </div>
        )}
        </div>
      </div>
      
      {/* Task Details Drawer */}
      <TaskDetailsDrawer
        task={selectedTask}
        events={taskEvents}
        loading={loadingTask}
        onClose={() => setSelectedTask(null)}
      />
    </div>
  )
}
