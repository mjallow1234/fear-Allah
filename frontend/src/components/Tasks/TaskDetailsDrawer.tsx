/**
 * TaskDetailsDrawer Component
 * Phase 7.2 - Task Inbox UI
 * 
 * Slide-out drawer showing task details, assignments, and audit events.
 */
import { useEffect } from 'react'
import { 
  X, 
  Package, 
  ShoppingCart, 
  Warehouse, 
  Tag, 
  Wrench,
  Clock,
  User,
  CheckCircle,
  XCircle,
  ArrowRight,
  FileText,
  Loader2
} from 'lucide-react'
import clsx from 'clsx'
import { 
  AutomationTask, 
  TaskEvent, 
  AutomationTaskType, 
  AutomationTaskStatus,
  AssignmentStatus,
  useTaskStore
} from '../../stores/taskStore'

interface TaskDetailsDrawerProps {
  task: AutomationTask | null
  events: TaskEvent[]
  loading: boolean
  onClose: () => void
}

// Task type icons
const taskTypeConfig: Record<AutomationTaskType, { icon: typeof Package; color: string; label: string }> = {
  'RESTOCK': { icon: Warehouse, color: 'bg-blue-600', label: 'Restock' },
  'RETAIL': { icon: ShoppingCart, color: 'bg-green-600', label: 'Retail' },
  'WHOLESALE': { icon: Package, color: 'bg-purple-600', label: 'Wholesale' },
  'SALE': { icon: Tag, color: 'bg-orange-600', label: 'Sale' },
  'CUSTOM': { icon: Wrench, color: 'bg-gray-600', label: 'Custom' },
}

// Status badge config
const statusConfig: Record<AutomationTaskStatus, { color: string; bgColor: string; icon: typeof CheckCircle; label: string }> = {
  'PENDING': { color: 'text-yellow-400', bgColor: 'bg-yellow-400/10', icon: Clock, label: 'Pending' },
  'IN_PROGRESS': { color: 'text-blue-400', bgColor: 'bg-blue-400/10', icon: ArrowRight, label: 'In Progress' },
  'COMPLETED': { color: 'text-green-400', bgColor: 'bg-green-400/10', icon: CheckCircle, label: 'Completed' },
  'CANCELLED': { color: 'text-red-400', bgColor: 'bg-red-400/10', icon: XCircle, label: 'Cancelled' },
}

const assignmentStatusConfig: Record<AssignmentStatus, { color: string; label: string }> = {
  'PENDING': { color: 'text-yellow-400', label: 'Pending' },
  'IN_PROGRESS': { color: 'text-blue-400', label: 'In Progress' },
  'DONE': { color: 'text-green-400', label: 'Done' },
  'SKIPPED': { color: 'text-gray-400', label: 'Skipped' },
}

export default function TaskDetailsDrawer({ task, events, loading, onClose }: TaskDetailsDrawerProps) {
  const { fetchTaskDetails, fetchTaskEvents } = useTaskStore()
  
  // Refresh task details when drawer opens
  useEffect(() => {
    if (task) {
      fetchTaskDetails(task.id)
      fetchTaskEvents(task.id)
    }
  }, [task?.id, fetchTaskDetails, fetchTaskEvents])
  
  if (!task) return null
  
  const typeConfig = taskTypeConfig[task.task_type] || taskTypeConfig['CUSTOM']
  const status = statusConfig[task.status] || statusConfig['PENDING']
  const TypeIcon = typeConfig.icon
  const StatusIcon = status.icon
  
  const formatDate = (dateStr: string) => {
    return new Date(dateStr).toLocaleString()
  }
  
  const formatEventType = (eventType: string) => {
    return eventType.replace(/_/g, ' ').toLowerCase().replace(/\b\w/g, c => c.toUpperCase())
  }

  return (
    <>
      {/* Backdrop */}
      <div
        className="fixed inset-0 bg-black/50 z-40"
        onClick={onClose}
      />
      
      {/* Drawer */}
      <div className="fixed right-0 top-0 h-full w-full max-w-lg bg-[#313338] border-l border-[#1f2023] z-50 overflow-y-auto">
        {/* Header */}
        <div className="sticky top-0 bg-[#313338] border-b border-[#1f2023] px-6 py-4 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className={clsx(
              'w-10 h-10 rounded-lg flex items-center justify-center text-white',
              typeConfig.color
            )}>
              <TypeIcon size={20} />
            </div>
            <div>
              <h2 className="text-lg font-semibold text-white">Task Details</h2>
              <span className={clsx(
                'text-xs px-2 py-0.5 rounded-full',
                status.bgColor,
                status.color
              )}>
                <StatusIcon size={12} className="inline mr-1" />
                {status.label}
              </span>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-2 text-[#949ba4] hover:text-white hover:bg-[#35373c] rounded-lg transition-colors"
          >
            <X size={20} />
          </button>
        </div>
        
        {loading ? (
          <div className="flex items-center justify-center py-12">
            <Loader2 className="animate-spin text-[#5865f2]" size={32} />
          </div>
        ) : (
          <div className="p-6 space-y-6">
            {/* Title & Description */}
            <div>
              <h3 className="text-xl font-semibold text-white mb-2">{task.title}</h3>
              {task.description ? (
                <p className="text-[#949ba4]">{task.description}</p>
              ) : (
                <p className="text-[#72767d] italic">No description</p>
              )}
            </div>
            
            {/* Metadata Grid */}
            <div className="grid grid-cols-2 gap-4">
              <div className="bg-[#2b2d31] rounded-lg p-3">
                <span className="text-xs text-[#72767d] block mb-1">Type</span>
                <span className="text-white font-medium">{typeConfig.label}</span>
              </div>
              <div className="bg-[#2b2d31] rounded-lg p-3">
                <span className="text-xs text-[#72767d] block mb-1">Status</span>
                <span className={clsx('font-medium', status.color)}>{status.label}</span>
              </div>
              <div className="bg-[#2b2d31] rounded-lg p-3">
                <span className="text-xs text-[#72767d] block mb-1">Created</span>
                <span className="text-white text-sm">{formatDate(task.created_at)}</span>
              </div>
              {task.updated_at && (
                <div className="bg-[#2b2d31] rounded-lg p-3">
                  <span className="text-xs text-[#72767d] block mb-1">Updated</span>
                  <span className="text-white text-sm">{formatDate(task.updated_at)}</span>
                </div>
              )}
              {task.related_order_id && (
                <div className="bg-[#2b2d31] rounded-lg p-3">
                  <span className="text-xs text-[#72767d] block mb-1">Related Order</span>
                  <span className="text-white font-medium">#{task.related_order_id}</span>
                </div>
              )}
            </div>
            
            {/* Metadata (if any) */}
            {task.metadata && Object.keys(task.metadata).length > 0 && (
              <div>
                <h4 className="text-sm font-semibold text-white mb-3 flex items-center gap-2">
                  <FileText size={16} />
                  Additional Info
                </h4>
                <div className="bg-[#2b2d31] rounded-lg p-3">
                  <pre className="text-xs text-[#949ba4] whitespace-pre-wrap overflow-x-auto">
                    {JSON.stringify(task.metadata, null, 2)}
                  </pre>
                </div>
              </div>
            )}
            
            {/* Assignments */}
            <div>
              <h4 className="text-sm font-semibold text-white mb-3 flex items-center gap-2">
                <User size={16} />
                Assignments ({task.assignments.length})
              </h4>
              {task.assignments.length === 0 ? (
                <p className="text-[#72767d] text-sm italic">No assignments yet</p>
              ) : (
                <div className="space-y-2">
                  {task.assignments.map((assignment) => (
                    <div 
                      key={assignment.id}
                      className="bg-[#2b2d31] rounded-lg p-3 flex items-center justify-between"
                    >
                      <div>
                        <span className="text-white font-medium">User #{assignment.user_id}</span>
                        {assignment.role_hint && (
                          <span className="text-[#72767d] text-sm ml-2">({assignment.role_hint})</span>
                        )}
                        {assignment.notes && (
                          <p className="text-[#949ba4] text-sm mt-1">{assignment.notes}</p>
                        )}
                      </div>
                      <span className={clsx(
                        'text-sm font-medium',
                        assignmentStatusConfig[assignment.status]?.color || 'text-gray-400'
                      )}>
                        {assignmentStatusConfig[assignment.status]?.label || assignment.status}
                      </span>
                    </div>
                  ))}
                </div>
              )}
            </div>
            
            {/* Timeline / Events */}
            <div>
              <h4 className="text-sm font-semibold text-white mb-3 flex items-center gap-2">
                <Clock size={16} />
                Activity Timeline ({events.length})
              </h4>
              {events.length === 0 ? (
                <p className="text-[#72767d] text-sm italic">No events recorded</p>
              ) : (
                <div className="relative">
                  {/* Timeline line */}
                  <div className="absolute left-3 top-0 bottom-0 w-0.5 bg-[#1f2023]" />
                  
                  <div className="space-y-4">
                    {events.map((event) => (
                      <div key={event.id} className="relative pl-8">
                        {/* Timeline dot */}
                        <div className="absolute left-1.5 top-1.5 w-3 h-3 rounded-full bg-[#5865f2]" />
                        
                        <div className="bg-[#2b2d31] rounded-lg p-3">
                          <div className="flex items-center justify-between mb-1">
                            <span className="text-white font-medium text-sm">
                              {formatEventType(event.event_type)}
                            </span>
                            <span className="text-xs text-[#72767d]">
                              {formatDate(event.created_at)}
                            </span>
                          </div>
                          {event.user_id && (
                            <span className="text-xs text-[#949ba4]">by User #{event.user_id}</span>
                          )}
                          {event.metadata && Object.keys(event.metadata).length > 0 && (
                            <pre className="text-xs text-[#72767d] mt-2 whitespace-pre-wrap">
                              {JSON.stringify(event.metadata, null, 2)}
                            </pre>
                          )}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </div>
        )}
      </div>
    </>
  )
}
