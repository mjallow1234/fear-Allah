/**
 * Recent Automation Events Panel
 * 
 * Displays last 10-20 automation events from slash commands.
 * Local only - resets on page refresh.
 */
import { useState } from 'react'
import { 
  Activity, 
  ChevronDown, 
  ChevronRight, 
  Zap, 
  CheckCircle, 
  Search, 
  AlertCircle,
  Clock,
  User,
  ListTodo,
  Bell,
  Trash2
} from 'lucide-react'
import { useAutomationEventsStore, AutomationEvent } from '../stores/automationEventsStore'

const statusConfig = {
  'success': { 
    color: 'text-green-400', 
    bg: 'bg-green-500/10', 
    border: 'border-green-500/30',
    icon: CheckCircle,
    label: 'Committed'
  },
  'dry-run': { 
    color: 'text-blue-400', 
    bg: 'bg-blue-500/10', 
    border: 'border-blue-500/30',
    icon: Search,
    label: 'Dry-Run'
  },
  'error': { 
    color: 'text-red-400', 
    bg: 'bg-red-500/10', 
    border: 'border-red-500/30',
    icon: AlertCircle,
    label: 'Error'
  },
}

function formatTimeAgo(date: Date): string {
  const now = new Date()
  const diff = now.getTime() - date.getTime()
  const minutes = Math.floor(diff / 60000)
  const hours = Math.floor(minutes / 60)
  
  if (minutes < 1) return 'Just now'
  if (minutes < 60) return `${minutes}m ago`
  if (hours < 24) return `${hours}h ago`
  return date.toLocaleDateString()
}

function EventCard({ event }: { event: AutomationEvent }) {
  const [expanded, setExpanded] = useState(false)
  const config = statusConfig[event.status]
  // StatusIcon is available from config but not currently rendered directly
  // const StatusIcon = config.icon
  
  return (
    <div className={`rounded-lg border ${config.border} ${config.bg} overflow-hidden`}>
      {/* Header - always visible */}
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full px-3 py-2 flex items-center gap-2 hover:bg-white/5 transition-colors text-left"
      >
        {expanded ? <ChevronDown size={14} className="text-gray-400" /> : <ChevronRight size={14} className="text-gray-400" />}
        <Zap size={14} className={config.color} />
        <span className="flex-1 text-sm font-medium text-gray-200 truncate">
          {event.eventName}
        </span>
        <span className={`text-xs px-1.5 py-0.5 rounded ${config.bg} ${config.color} border ${config.border}`}>
          {config.label}
        </span>
      </button>
      
      {/* Expanded details */}
      {expanded && (
        <div className="px-3 pb-3 pt-1 space-y-2 text-xs border-t border-gray-700/50">
          {/* Timestamp & User */}
          <div className="flex items-center gap-4 text-gray-400">
            <span className="flex items-center gap-1">
              <Clock size={12} />
              {formatTimeAgo(event.timestamp)}
            </span>
            <span className="flex items-center gap-1">
              <User size={12} />
              {event.triggeredBy}
            </span>
          </div>
          
          {/* Order ID */}
          {event.orderId && (
            <div className="text-gray-300">
              Order ID: <span className="text-white font-medium">#{event.orderId}</span>
            </div>
          )}
          
          {/* Tasks */}
          <div className="flex items-start gap-2">
            <ListTodo size={12} className="text-blue-400 mt-0.5" />
            <div>
              <span className="text-gray-400">Tasks: </span>
              <span className="text-white">{event.tasksCreated}</span>
              {event.taskTitles.length > 0 && (
                <div className="text-gray-500 mt-0.5">
                  {event.taskTitles.slice(0, 3).map((title, i) => (
                    <div key={i} className="truncate">• {title}</div>
                  ))}
                  {event.taskTitles.length > 3 && (
                    <div className="text-gray-600">+{event.taskTitles.length - 3} more</div>
                  )}
                </div>
              )}
            </div>
          </div>
          
          {/* Assigned users */}
          {event.assignedTo.length > 0 && (
            <div className="flex items-center gap-2">
              <User size={12} className="text-green-400" />
              <span className="text-gray-400">Assigned: </span>
              <span className="text-white">{event.assignedTo.join(', ')}</span>
            </div>
          )}
          
          {/* Notifications */}
          {event.notificationsQueued > 0 && (
            <div className="flex items-center gap-2">
              <Bell size={12} className="text-yellow-400" />
              <span className="text-gray-400">Notifications: </span>
              <span className="text-white">{event.notificationsQueued}</span>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

export default function RecentAutomationEvents() {
  const { events, clearEvents } = useAutomationEventsStore()
  const [collapsed, setCollapsed] = useState(false)
  
  if (events.length === 0) {
    return (
      <div className="bg-[#2b2d31] rounded-lg border border-[#1f2023] p-4">
        <div className="flex items-center gap-2 text-gray-400 mb-3">
          <Activity size={16} />
          <span className="font-medium">Recent Automation Events</span>
        </div>
        <div className="text-sm text-gray-500 text-center py-4">
          No automation events yet.<br />
          <span className="text-xs">Use slash commands to see events here.</span>
        </div>
      </div>
    )
  }
  
  return (
    <div className="bg-[#2b2d31] rounded-lg border border-[#1f2023] overflow-hidden">
      {/* Header */}
      <div className="px-4 py-3 border-b border-[#1f2023] flex items-center justify-between">
        <button
          onClick={() => setCollapsed(!collapsed)}
          className="flex items-center gap-2 text-gray-300 hover:text-white transition-colors"
        >
          {collapsed ? <ChevronRight size={16} /> : <ChevronDown size={16} />}
          <Activity size={16} className="text-purple-400" />
          <span className="font-medium">Recent Automation Events</span>
          <span className="text-xs text-gray-500 bg-gray-700 px-1.5 py-0.5 rounded">
            {events.length}
          </span>
        </button>
        
        {!collapsed && events.length > 0 && (
          <button
            onClick={clearEvents}
            className="text-gray-500 hover:text-gray-300 p-1 rounded hover:bg-gray-700 transition-colors"
            title="Clear all events"
          >
            <Trash2 size={14} />
          </button>
        )}
      </div>
      
      {/* Events list */}
      {!collapsed && (
        <div className="p-3 space-y-2 max-h-96 overflow-y-auto">
          {events.map((event) => (
            <EventCard key={event.id} event={event} />
          ))}
        </div>
      )}
    </div>
  )
}
