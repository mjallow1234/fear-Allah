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
  user?: { id: number; username: string; display_name: string | null } | null
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
  order?: {
    id: number
    has_sale: boolean
    // Add more fields if needed
  }
}

export interface TaskEvent {
  id: number
  task_id: number
  user_id: number | null
  event_type: string
  metadata: Record<string, unknown> | null
  created_at: string
  user?: { id: number; username: string; display_name: string | null } | null
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
  fetchMyAssignments: (filters?: { search?: string; order_type?: string }) => Promise<void>
  fetchMyTasks: () => Promise<void>
  fetchAvailableTasks: (role: string | null) => Promise<void>
  claimTask: (taskId: number) => Promise<boolean>
  fetchTaskDetails: (taskId: number) => Promise<void>
  fetchTaskEvents: (taskId: number) => Promise<void>
  completeAssignment: (taskId: number, notes?: string) => Promise<boolean>
  
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
  
  fetchMyAssignments: async (filters?: { search?: string; order_type?: string }) => {
    set({ loading: true, error: null })
    try {
      const params: Record<string, string> = {}
      if (filters?.search) params.search = filters.search
      if (filters?.order_type) params.order_type = filters.order_type
      const response = await api.get('/api/automation/my-assignments', { params })
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
      const response = await api.get('/api/automation/available-tasks', params)
      const data = response.data
      const tasks = Array.isArray(data) ? data : (data.tasks || [])
      set({ availableTasks: tasks, loading: false })
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
      // Find current user's assignment for this task
      const assignment = get().myAssignments.find(a => a.task_id === taskId)
      if (!assignment) {
        console.error('[TaskStore] No assignment found for task:', taskId)
        set({ error: 'No assignment found for this task', completingTaskId: null })
        return false
      }

      // Call assignment-level complete endpoint to avoid any ambiguity with task-level completion
      await api.post(`/api/automation/assignments/${assignment.id}/complete`, { notes })

      // Refresh data after completion - tasks, assignments, AND orders
      await get().fetchMyAssignments()
      await get().fetchMyTasks()

      // Also refetch orders to get updated status
      try {
        await useOrderStore.getState().fetchOrders()
      } catch (e) {
        console.warn('[TaskStore] Failed to refetch orders after assignment completion:', e)
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
  
  // Socket event handlers
  handleTaskAssigned: (_data) => {
    get().fetchMyAssignments()
  },
  
  handleTaskCompleted: (data) => {
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
