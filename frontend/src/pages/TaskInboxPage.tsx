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
  AlertCircle
} from 'lucide-react'
import clsx from 'clsx'
import { useAuthStore } from '../stores/authStore'
import { useTaskStore, AutomationTask } from '../stores/taskStore'
import { subscribeToTasks } from '../realtime/tasks'
import TaskCard from '../components/Tasks/TaskCard'
import TaskDetailsDrawer from '../components/Tasks/TaskDetailsDrawer'

type TabType = 'my-tasks' | 'created' | 'completed' | 'available'

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
  
  const [activeTab, setActiveTab] = useState<TabType>('my-tasks')
  
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
  
  // Fetch data on mount and tab change
  useEffect(() => {
    if (activeTab === 'my-tasks') {
      fetchMyAssignments()
    } else if (activeTab === 'available') {
      // Use operational role name from currentUser (UI header) and normalize to backend enum (lowercase, underscores)
      const role = operationalRoleName ? operationalRoleName.toLowerCase().replace(/\s+/g, '_') : null
      fetchAvailableTasks(role)
    } else {
      fetchMyTasks()
    }
  }, [activeTab, fetchMyAssignments, fetchMyTasks, fetchAvailableTasks, operationalRoleName])
  
  // Get tasks based on active tab
  const getFilteredTasks = (): AutomationTask[] => {
    if (activeTab === 'my-tasks') {
      // Get tasks where user has assignments
      const taskIds = new Set(myAssignments.map(a => a.task_id))
      // For now, we show assignment info directly - tasks list will need API update
      // Return empty until we have full task objects
      return tasks.filter(t => taskIds.has(t.id))
    } else if (activeTab === 'created') {
      return tasks.filter(t => t.created_by_id === user?.id)
    } else {
      // Completed tab
      return tasks.filter(t => t.status === 'COMPLETED')
    }
  }
  
  const filteredTasks = getFilteredTasks()
  
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
    <div className="h-screen flex flex-col bg-[#313338] overflow-hidden">
      {/* Header */}
      <div className="flex-shrink-0 bg-[#2b2d31] border-b border-[#1f2023] px-6 py-4">
        <div className="max-w-4xl mx-auto flex items-center justify-between">
          <div className="flex items-center gap-4">
            <button
              onClick={() => navigate(-1)}
              className="p-2 text-[#949ba4] hover:text-white transition-colors"
            >
              <ArrowLeft size={20} />
            </button>
            <div>
              <h1 className="text-xl font-semibold text-white flex items-center gap-2">
                <ClipboardList size={24} />
                Task Inbox
              </h1>
              <p className="text-sm text-[#949ba4]">
                {pendingCount} pending task{pendingCount !== 1 ? 's' : ''}
              </p>
            </div>
          </div>
          <button
            onClick={handleRefresh}
            disabled={loading}
            className={clsx(
              'flex items-center gap-2 px-3 py-2 rounded-lg transition-colors',
              loading
                ? 'bg-[#1f2023] text-[#72767d] cursor-not-allowed'
                : 'bg-[#5865f2] hover:bg-[#4752c4] text-white'
            )}
          >
            <RefreshCw size={16} className={loading ? 'animate-spin' : ''} />
            Refresh
          </button>
        </div>
      </div>
      
      {/* Tabs */}
      <div className="bg-[#2b2d31] border-b border-[#1f2023] px-6">
        <div className="max-w-4xl mx-auto flex gap-1">
          <button
            onClick={() => setActiveTab('my-tasks')}
            className={clsx(
              'flex items-center gap-2 px-4 py-3 text-sm font-medium transition-colors border-b-2',
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
          <button
            onClick={() => setActiveTab('available')}
            className={clsx(
              'flex items-center gap-2 px-4 py-3 text-sm font-medium transition-colors border-b-2',
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
              'flex items-center gap-2 px-4 py-3 text-sm font-medium transition-colors border-b-2',
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
              'flex items-center gap-2 px-4 py-3 text-sm font-medium transition-colors border-b-2',
              activeTab === 'completed'
                ? 'text-white border-[#5865f2]'
                : 'text-[#949ba4] border-transparent hover:text-white'
            )}
          >
            Completed
          </button>
        </div>
      </div>
      
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
      
      {/* Task List - Scrollable */}
      <div className="flex-1 overflow-y-auto">
        <div className="max-w-4xl mx-auto py-6 px-6">
          {loading ? (
            <div className="py-12 text-center">
              <Loader2 className="animate-spin mx-auto mb-4 text-[#5865f2]" size={32} />
              <p className="text-[#949ba4]">Loading tasks...</p>
            </div>
          ) : activeTab === 'my-tasks' && myAssignments.length === 0 ? (
            <div className="py-12 text-center">
              <ClipboardList size={48} className="mx-auto mb-4 text-[#949ba4] opacity-50" />
              <p className="text-[#949ba4]">No tasks assigned to you</p>
              <p className="text-[#72767d] text-sm mt-1">
                Tasks will appear here when you're assigned to them
              </p>
            </div>
          ) : activeTab === 'available' && availableTasks.length === 0 ? (
          <div className="py-12 text-center">
            <ClipboardList size={48} className="mx-auto mb-4 text-[#949ba4] opacity-50" />
            <p className="text-[#949ba4]">No available tasks</p>
            <p className="text-[#72767d] text-sm mt-1">Tasks matching your active role will appear here</p>
          </div>
        ) : activeTab !== 'my-tasks' && filteredTasks.length === 0 ? (
          <div className="py-12 text-center">
            <ClipboardList size={48} className="mx-auto mb-4 text-[#949ba4] opacity-50" />
            <p className="text-[#949ba4]">
              {activeTab === 'created' ? 'No tasks created by you' : 'No available tasks'}
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
        ) : activeTab === 'available' ? (
          <div className="space-y-3">
            {availableTasks.map((task) => (
              <TaskCard
                key={task.id}
                task={task}
                isAvailableView={true}
                onClaim={() => claimTask(task.id)}
              />
            ))}
          </div>
        ) : (
          <div className="space-y-3">
            {filteredTasks.map((task) => (
              <TaskCard
                key={task.id}
                task={task}
                assignment={getAssignment(task.id)}
                currentUserId={user?.id || 0}
                isCompleting={completingTaskId === task.id}
                onComplete={handleComplete}
                onClick={() => setSelectedTask(task)}
              />
            ))}
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
