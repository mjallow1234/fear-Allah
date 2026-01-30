/**
 * Task Store for automation workflows.
 * Phase 7.2 - Task Inbox UI
 * 
 * Manages tasks and assignments state.
 * Socket.IO only, no polling.
 */
import { create } from 'zustand'
import api from '../services/api'
import { useOrderStore } from './orderStore'
import { useAuthStore } from './authStore'

// Enums matching backend (supports both cases for compatibility)
export type AutomationTaskType = 'RESTOCK' | 'RETAIL' | 'WHOLESALE' | 'SALE' | 'CUSTOM' | 'restock' | 'retail' | 'wholesale' | 'sale' | 'custom'
export type AutomationTaskStatus = 'PENDING' | 'IN_PROGRESS' | 'COMPLETED' | 'CANCELLED' | 'pending' | 'in_progress' | 'completed' | 'cancelled'
export type AssignmentStatus = 'PENDING' | 'IN_PROGRESS' | 'DONE' | 'SKIPPED' | 'pending' | 'in_progress' | 'done' | 'skipped'

export interface TaskAssignment {
  id: number
  task_id: number
  user_id: number
  role_hint: string | null
  status: AssignmentStatus
  notes: string | null
  assigned_at: string
  completed_at: string | null
}

export interface AutomationTask {
  id: number
  task_type: AutomationTaskType
  status: AutomationTaskStatus
  title: string
  description: string | null
  created_by_id: number
  related_order_id: number | null
  metadata: Record<string, unknown> | null
  order_details?: Record<string, unknown> | null
  created_at: string
  updated_at: string | null
  assignments: TaskAssignment[]
  required_role?: string | null
}

export interface TaskEvent {
  id: number
  task_id: number
  user_id: number | null
  event_type: string
  metadata: Record<string, unknown> | null
  created_at: string
}

interface TaskState {
  // Data
  tasks: AutomationTask[]
  myAssignments: TaskAssignment[]
  availableTasks: AutomationTask[]
  selectedTask: AutomationTask | null
  taskEvents: TaskEvent[]
  
  // Loading states
  loading: boolean
  loadingTask: boolean
  completingTaskId: number | null
  
  // Error state
  error: string | null
  
  // Actions
  fetchMyAssignments: () => Promise<void>
  fetchMyTasks: () => Promise<void>
  fetchAvailableTasks: (role: string | null) => Promise<void>
  claimTask: (taskId: number) => Promise<boolean>
  fetchTaskDetails: (taskId: number) => Promise<void>
  fetchTaskEvents: (taskId: number) => Promise<void>
  completeAssignment: (taskId: number, notes?: string) => Promise<boolean>
  completeWorkflowStep: (taskId: number, notes?: string) => Promise<boolean>
  
  // Socket event handlers
  handleTaskAssigned: (data: { task_id: number; user_id: number; assignment: TaskAssignment }) => void
  handleTaskCompleted: (data: { task_id: number }) => void
  handleTaskAutoClosed: (data: { task_id: number }) => void
  
  // UI helpers
  setSelectedTask: (task: AutomationTask | null) => void
  clearError: () => void
  reset: () => void
}

export const useTaskStore = create<TaskState>((set, get) => ({
  // Initial state
  tasks: [],
  myAssignments: [],
  availableTasks: [],
  selectedTask: null,
  taskEvents: [],
  loading: false,
  loadingTask: false,
  completingTaskId: null,
  error: null,
  
  fetchMyAssignments: async () => {
    set({ loading: true, error: null })
    try {
      const response = await api.get('/api/automation/my-assignments')
      const assignments = Array.isArray(response.data) ? response.data : []
      set({ myAssignments: assignments, loading: false })
    } catch (error: unknown) {
      const err = error as { response?: { data?: { detail?: string } } }
      console.error('[TaskStore] Failed to fetch my assignments:', error)
      set({ 
        error: err.response?.data?.detail || 'Failed to fetch assignments',
        loading: false 
      })
    }
  },

  fetchAvailableTasks: async (role: string | null) => {
    set({ loading: true, error: null })
    try {
      const params = role ? { params: { role } } : {}
      console.log('[TaskStore] GET /api/automation/available-tasks', params)
      const response = await api.get('/api/automation/available-tasks', params)
      const data = response.data
      const tasks = Array.isArray(data) ? data : (data.tasks || [])
      set({ availableTasks: tasks, loading: false })
      console.log('[TaskStore] available_tasks_count:', tasks.length)
    } catch (error: unknown) {
      const err = error as { response?: { data?: { detail?: string } } }
      console.error('[TaskStore] Failed to fetch available tasks:', error)
      set({ 
        error: err.response?.data?.detail || 'Failed to fetch available tasks',
        loading: false 
      })
    }
  },

  claimTask: async (taskId: number) => {
    set({ error: null })
    // Optimistic remove from availableTasks
    const prevAvail = get().availableTasks
    set({ availableTasks: prevAvail.filter(t => t.id !== taskId) })
    try {
      console.log('[TaskStore] POST /api/automation/tasks/${taskId}/claim')
      await api.post(`/api/automation/tasks/${taskId}/claim`, {})
      // Refresh my assignments and available tasks (role-based)
      await get().fetchMyAssignments()
      const currentUser = useAuthStore.getState().currentUser
      const roleRaw = currentUser?.operational_role_name ?? useAuthStore.getState().user?.role ?? null
      const role = roleRaw ? roleRaw.toLowerCase().replace(/\s+/g, '_') : null
      await get().fetchAvailableTasks(role)
      // Also refresh general tasks list to reflect status change
      await get().fetchMyTasks()
      return true
    } catch (error: unknown) {
      console.error('[TaskStore] Failed to claim task:', error)
      set({ availableTasks: prevAvail, error: 'Failed to claim task' })
      return false
    }
  },
  
  fetchMyTasks: async () => {
    set({ loading: true, error: null })
    try {
      const response = await api.get('/api/automation/tasks')
      const data = response.data
      const tasks = Array.isArray(data) ? data : (data.tasks || [])
      set({ tasks, loading: false })

      // Temporary debug log: user_id from JWT and number of tasks returned
      try {
        let userId: string | number | null = useAuthStore.getState().user?.id ?? null
        const token = useAuthStore.getState().token
        if (!userId && token) {
          try {
            const parts = token.split('.')
            if (parts.length > 1) {
              const payloadBase64 = parts[1].replace(/-/g, '+').replace(/_/g, '/')
              const json = decodeURIComponent(atob(payloadBase64).split('').map((c) => '%'+('00'+c.charCodeAt(0).toString(16)).slice(-2)).join(''))
              const payload = JSON.parse(json)
              userId = payload.sub ?? payload.user_id ?? payload.uid ?? null
            }
          } catch (e) {}
        }
        console.log('[TaskStore] fetchMyTasks user_id_from_jwt:', userId ?? 'unknown', 'tasks_count:', tasks.length)
      } catch (e) {
        // ignore logging errors
      }
    } catch (error: unknown) {
      const err = error as { response?: { data?: { detail?: string } } }
      console.error('[TaskStore] Failed to fetch tasks:', error)
      set({ 
        error: err.response?.data?.detail || 'Failed to fetch tasks',
        loading: false 
      })
    }
  },
  
  fetchTaskDetails: async (taskId: number) => {
    set({ loadingTask: true, error: null })
    try {
      const response = await api.get(`/api/automation/tasks/${taskId}`)
      set({ selectedTask: response.data, loadingTask: false })
    } catch (error: unknown) {
      const err = error as { response?: { data?: { detail?: string } } }
      console.error('[TaskStore] Failed to fetch task details:', error)
      set({ 
        error: err.response?.data?.detail || 'Failed to fetch task details',
        loadingTask: false 
      })
    }
  },
  
  fetchTaskEvents: async (taskId: number) => {
    try {
      const response = await api.get(`/api/automation/tasks/${taskId}/events`)
      const events = Array.isArray(response.data) ? response.data : []
      set({ taskEvents: events })
    } catch (error) {
      console.error('[TaskStore] Failed to fetch task events:', error)
      set({ taskEvents: [] })
    }
  },
  
  completeAssignment: async (taskId: number, notes?: string) => {
    set({ completingTaskId: taskId, error: null })
    
    // Optimistic update
    const prevAssignments = get().myAssignments
    const prevTasks = get().tasks
    
    set((state) => ({
      myAssignments: state.myAssignments.map(a => 
        a.task_id === taskId 
          ? { ...a, status: 'DONE' as AssignmentStatus, completed_at: new Date().toISOString() } 
          : a
      ),
    }))
    
    try {
      await api.post(`/api/automation/tasks/${taskId}/complete`, { notes })
      
      // Refresh data after completion - tasks, assignments, AND orders
      await get().fetchMyAssignments()
      await get().fetchMyTasks()
      
      // Also refetch orders to get updated status
      try {
        await useOrderStore.getState().fetchOrders()
      } catch (e) {
        console.warn('[TaskStore] Failed to refetch orders after task completion:', e)
      }
      
      set({ completingTaskId: null })
      return true
    } catch (error: unknown) {
      const err = error as { response?: { data?: { detail?: string } } }
      console.error('[TaskStore] Failed to complete assignment:', error)
      
      // Rollback
      set({ 
        myAssignments: prevAssignments,
        tasks: prevTasks,
        error: err.response?.data?.detail || 'Failed to complete assignment',
        completingTaskId: null 
      })
      return false
    }
  },

  // New: complete the active workflow step for the given automation task.
  // This endpoint specifically targets workflow-step completion and should be
  // used for steps like `deliver_items` where workflow semantics differ from
  // assignment completion. Returns true on success.
  completeWorkflowStep: async (taskId: number, notes?: string) => {
    set({ completingTaskId: taskId, error: null })
    try {
      await api.post(`/api/automation/tasks/${taskId}/workflow-step/complete`, { notes })

      // Refresh relevant data
      await get().fetchMyAssignments()
      await get().fetchMyTasks()
      try {
        await useOrderStore.getState().fetchOrders()
      } catch (e) {
        console.warn('[TaskStore] Failed to refetch orders after workflow step completion:', e)
      }

      set({ completingTaskId: null })
      return true
    } catch (error: unknown) {
      const err = error as { response?: { data?: { detail?: string } } }
      console.error('[TaskStore] Failed to complete workflow step:', error)
      set({ error: err.response?.data?.detail || 'Failed to complete workflow step', completingTaskId: null })
      return false
    }
  },
  
  // Socket event handlers
  handleTaskAssigned: (data) => {
    console.log('[TaskStore] Task assigned event:', data)
    // Refresh assignments when a task is assigned to user
    get().fetchMyAssignments()
  },
  
  handleTaskCompleted: (data) => {
    console.log('[TaskStore] Task completed event:', data)
    // Update task status in local state
    set((state) => ({
      tasks: state.tasks.map(t => 
        t.id === data.task_id ? { ...t, status: 'COMPLETED' as AutomationTaskStatus } : t
      ),
      selectedTask: state.selectedTask?.id === data.task_id 
        ? { ...state.selectedTask, status: 'COMPLETED' as AutomationTaskStatus }
        : state.selectedTask,
    }))
    // Also refetch orders to update their status
    useOrderStore.getState().fetchOrders().catch(console.warn)
  },
  
  handleTaskAutoClosed: (data) => {
    console.log('[TaskStore] Task auto-closed event:', data)
    // Update task status in local state
    set((state) => ({
      tasks: state.tasks.map(t => 
        t.id === data.task_id ? { ...t, status: 'COMPLETED' as AutomationTaskStatus } : t
      ),
      myAssignments: state.myAssignments.filter(a => a.task_id !== data.task_id),
      selectedTask: state.selectedTask?.id === data.task_id 
        ? { ...state.selectedTask, status: 'COMPLETED' as AutomationTaskStatus }
        : state.selectedTask,
    }))
    // Also refetch orders to update their status
    useOrderStore.getState().fetchOrders().catch(console.warn)
  },
  
  // UI helpers
  setSelectedTask: (task) => {
    set({ selectedTask: task, taskEvents: [] })
    if (task) {
      get().fetchTaskEvents(task.id)
    }
  },
  
  clearError: () => set({ error: null }),
  
  reset: () => set({
    tasks: [],
    myAssignments: [],
    availableTasks: [],
    selectedTask: null,
    taskEvents: [],
    loading: false,
    loadingTask: false,
    completingTaskId: null,
    error: null,
  }),
}))
