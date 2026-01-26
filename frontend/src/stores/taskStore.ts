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

// Enums matching backend (supports both cases for compatibility)
export type AutomationTaskType = 'RESTOCK' | 'RETAIL' | 'WHOLESALE' | 'SALE' | 'CUSTOM' | 'restock' | 'retail' | 'wholesale' | 'sale' | 'custom'
// Added OPEN and CLAIMED to match backend Phase 4.2
export type AutomationTaskStatus = 'PENDING' | 'OPEN' | 'CLAIMED' | 'IN_PROGRESS' | 'COMPLETED' | 'CANCELLED' | 'pending' | 'open' | 'claimed' | 'in_progress' | 'completed' | 'cancelled'
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
  created_at: string
  updated_at: string | null
  assignments: TaskAssignment[]
  // Claimable task fields (nullable)
  required_role?: string | null
  claimed_by_user_id?: number | null
  claimed_by?: {
    id: number
    username?: string
    display_name?: string | null
  } | null
  claimed_at?: string | null
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
  selectedTask: AutomationTask | null
  taskEvents: TaskEvent[]
  
  // Loading states
  loading: boolean
  loadingTask: boolean
  completingTaskId: number | null
  claimTaskId: number | null
  
  // Error state
  error: string | null
  
  // Actions
  fetchMyAssignments: () => Promise<void>
  fetchMyTasks: () => Promise<void>
  fetchTaskDetails: (taskId: number) => Promise<void>
  fetchTaskEvents: (taskId: number) => Promise<void>
  completeAssignment: (taskId: number, notes?: string) => Promise<boolean>
  claimTask: (taskId: number, override?: boolean) => Promise<boolean>
  
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
  selectedTask: null,
  taskEvents: [],
  loading: false,
  loadingTask: false,
  completingTaskId: null,
  claimTaskId: null,
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

  claimTask: async (taskId: number, override = false) => {
    set({ claimTaskId: taskId, error: null })
    try {
      await api.post(`/api/automation/tasks/${taskId}/claim`, { override })

      // Refresh tasks and details to get authoritative state
      await get().fetchMyTasks()
      if (get().selectedTask?.id === taskId) {
        await get().fetchTaskDetails(taskId)
      }

      set({ claimTaskId: null })
      console.log('[TaskStore] Claimed task successfully', taskId)
      return true
    } catch (error: unknown) {
      const err = error as { response?: { status?: number; data?: { detail?: string } } }
      console.error('[TaskStore] Failed to claim task:', error)
      if (err.response?.status === 409) {
        // Conflict - task already claimed
        const errMsg = err.response.data?.detail || 'Task already claimed by another user'
        // Refetch to sync authoritative state, then set error so it isn't wiped by fetch's loading state
        try { await get().fetchMyTasks() } catch (e) { console.warn('[TaskStore] Failed to refetch tasks after claim conflict', e) }
        set({ error: errMsg })
      } else {
        set({ error: err.response?.data?.detail || 'Failed to claim task' })
      }
      set({ claimTaskId: null })
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
    selectedTask: null,
    taskEvents: [],
    loading: false,
    loadingTask: false,
    completingTaskId: null,
    claimTaskId: null,
    error: null,
  }),
}))
