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
    return () => {}
  }
  
  const store = useTaskStore.getState()
  
  const unsubAssigned = onSocketEvent<TaskAssignedEvent>('task:assigned', (data) => {
    store.handleTaskAssigned(data)
  })
  
  const unsubCompleted = onSocketEvent<TaskCompletedEvent>('task:completed', (data) => {
    store.handleTaskCompleted(data)
  })
  
  const unsubAutoClosed = onSocketEvent<TaskAutoClosedEvent>('task:auto_closed', (data) => {
    store.handleTaskAutoClosed(data)
  })
  
  taskSubscribed = true
  
  return () => {
    unsubAssigned()
    unsubCompleted()
    unsubAutoClosed()
    taskSubscribed = false
  }
}

/**
 * Reset task subscription state (for logout/disconnect).
 */
export function resetTaskSubscription(): void {
  taskSubscribed = false
  useTaskStore.getState().reset()
}
