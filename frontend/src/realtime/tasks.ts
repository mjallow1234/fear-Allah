/**
 * Task event subscriptions.
 * Phase 7.2 - Task Inbox UI
 * 
 * Subscribes to Socket.IO task events and updates the task store.
 */
import { onSocketEvent } from './socket'
import { useTaskStore, TaskAssignment } from '../stores/taskStore'

let taskSubscribed = false

interface TaskAssignedEvent {
  task_id: number
  user_id: number
  assignment: TaskAssignment
}

interface TaskCompletedEvent {
  task_id: number
}

interface TaskAutoClosedEvent {
  task_id: number
}

/**
 * Subscribe to task events from Socket.IO.
 * Should be called once after socket connects.
 */
export function subscribeToTasks(): () => void {
  if (taskSubscribed) {
    console.log('[Tasks] Already subscribed to task events')
    return () => {}
  }
  
  const store = useTaskStore.getState()
  
  // Listen for task assignment
  const unsubAssigned = onSocketEvent<TaskAssignedEvent>('task:assigned', (data) => {
    console.log('[Tasks] Received task:assigned', data)
    store.handleTaskAssigned(data)
  })
  
  // Listen for task completion
  const unsubCompleted = onSocketEvent<TaskCompletedEvent>('task:completed', (data) => {
    console.log('[Tasks] Received task:completed', data)
    store.handleTaskCompleted(data)
  })
  
  // Listen for task auto-close
  const unsubAutoClosed = onSocketEvent<TaskAutoClosedEvent>('task:auto_closed', (data) => {
    console.log('[Tasks] Received task:auto_closed', data)
    store.handleTaskAutoClosed(data)
  })
  
  taskSubscribed = true
  console.log('[Tasks] Subscribed to task events')
  
  // Return cleanup function
  return () => {
    unsubAssigned()
    unsubCompleted()
    unsubAutoClosed()
    taskSubscribed = false
    console.log('[Tasks] Unsubscribed from task events')
  }
}

/**
 * Reset task subscription state (for logout/disconnect).
 */
export function resetTaskSubscription(): void {
  taskSubscribed = false
  useTaskStore.getState().reset()
}
