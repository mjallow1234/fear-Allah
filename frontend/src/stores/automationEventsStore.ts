/**
 * Automation Events Store
 * 
 * Tracks recent automation events from slash command responses.
 * Local only - resets on page refresh.
 * Keeps last 20 events.
 */
import { create } from 'zustand'

export interface AutomationEvent {
  id: string
  eventName: string
  tasksCreated: number
  taskTitles: string[]
  assignedTo: string[]
  notificationsQueued: number
  isDryRun: boolean
  triggeredBy: string
  timestamp: Date
  orderId?: number
  status: 'success' | 'dry-run' | 'error'
}

interface AutomationEventsState {
  events: AutomationEvent[]
  addEvent: (event: Omit<AutomationEvent, 'id' | 'timestamp'>) => void
  clearEvents: () => void
}

const MAX_EVENTS = 20

export const useAutomationEventsStore = create<AutomationEventsState>((set) => ({
  events: [],
  
  addEvent: (eventData) => {
    const newEvent: AutomationEvent = {
      ...eventData,
      id: `${Date.now()}-${Math.random().toString(36).substr(2, 9)}`,
      timestamp: new Date(),
    }
    
    set((state) => ({
      events: [newEvent, ...state.events].slice(0, MAX_EVENTS)
    }))
  },
  
  clearEvents: () => set({ events: [] }),
}))

/**
 * Parse a slash command response to extract automation event data
 */
export function parseAutomationEventFromResponse(
  content: string,
  username: string
): Omit<AutomationEvent, 'id' | 'timestamp'> | null {
  // Only parse responses with automation debug info
  if (!content.includes('Automation Debug') && !content.includes('Order created') && !content.includes('Sale recorded')) {
    return null
  }
  
  const isDryRun = content.toLowerCase().includes('dry-run') || content.toLowerCase().includes('dry_run')
  const isError = content.startsWith('❌')
  
  // Extract event name
  let eventName = 'unknown'
  const eventMatch = content.match(/Event:\s*`?([^`\n]+)`?/i)
  if (eventMatch) {
    eventName = eventMatch[1].trim()
  } else if (content.includes('Order created')) {
    eventName = 'order.created'
  } else if (content.includes('Sale recorded')) {
    eventName = 'sale.recorded'
  }
  
  // Extract tasks created count
  let tasksCreated = 0
  const tasksMatch = content.match(/Tasks(?:\s+created)?:\s*(\d+)/i)
  if (tasksMatch) {
    tasksCreated = parseInt(tasksMatch[1], 10)
  }
  
  // Extract task titles
  const taskTitles: string[] = []
  const titlesMatch = content.match(/Task titles?:\s*([^\n]+)/i)
  if (titlesMatch) {
    taskTitles.push(...titlesMatch[1].split(',').map(t => t.trim()).filter(Boolean))
  }
  
  // Extract assigned users
  const assignedTo: string[] = []
  const assignedMatch = content.match(/Assigned to:\s*([^\n]+)/i)
  if (assignedMatch) {
    assignedTo.push(...assignedMatch[1].split(',').map(u => u.trim()).filter(Boolean))
  }
  
  // Extract notifications count
  let notificationsQueued = 0
  const notifMatch = content.match(/Notifications?\s*queued?:\s*(\d+)/i)
  if (notifMatch) {
    notificationsQueued = parseInt(notifMatch[1], 10)
  }
  
  // Extract order ID if present
  let orderId: number | undefined
  const orderIdMatch = content.match(/Order\s+created\s*\(ID:\s*(\d+)\)/i) || content.match(/ID:\s*(\d+)/i)
  if (orderIdMatch) {
    orderId = parseInt(orderIdMatch[1], 10)
  }
  
  return {
    eventName,
    tasksCreated,
    taskTitles,
    assignedTo,
    notificationsQueued,
    isDryRun,
    triggeredBy: username,
    orderId,
    status: isError ? 'error' : isDryRun ? 'dry-run' : 'success',
  }
}
