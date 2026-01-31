/**
 * TaskDetailsDrawer Component
 * Phase 7.2 - Task Inbox UI
 * 
 * Slide-out drawer showing task details, assignments, and audit events.
 */
import { useEffect, useState } from 'react'
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
  useTaskStore
} from '../../stores/taskStore'
import { useAuthStore } from '../../stores/authStore'
import api from '../../services/api'



interface TaskDetailsDrawerProps {
  task: AutomationTask | null
  events: TaskEvent[]
  loading: boolean
  onClose: () => void
}

// Helper to normalize to uppercase for config lookup
const normalizeType = (type: string): string => type?.toUpperCase() || 'CUSTOM'
const normalizeStatus = (status: string): string => status?.toUpperCase() || 'PENDING'

// Task type icons
const taskTypeConfig: Record<string, { icon: typeof Package; color: string; label: string }> = {
  'RESTOCK': { icon: Warehouse, color: 'bg-blue-600', label: 'Restock' },
  'RETAIL': { icon: ShoppingCart, color: 'bg-green-600', label: 'Retail' },
  'WHOLESALE': { icon: Package, color: 'bg-purple-600', label: 'Wholesale' },
  'SALE': { icon: Tag, color: 'bg-orange-600', label: 'Sale' },
  'CUSTOM': { icon: Wrench, color: 'bg-gray-600', label: 'Custom' },
}

// Status badge config
const statusConfig: Record<string, { color: string; bgColor: string; icon: typeof CheckCircle; label: string }> = {
  'PENDING': { color: 'text-yellow-400', bgColor: 'bg-yellow-400/10', icon: Clock, label: 'Pending' },
  'IN_PROGRESS': { color: 'text-blue-400', bgColor: 'bg-blue-400/10', icon: ArrowRight, label: 'In Progress' },
  'COMPLETED': { color: 'text-green-400', bgColor: 'bg-green-400/10', icon: CheckCircle, label: 'Completed' },
  'CANCELLED': { color: 'text-red-400', bgColor: 'bg-red-400/10', icon: XCircle, label: 'Cancelled' },
}

const assignmentStatusConfig: Record<string, { color: string; label: string }> = {
  'PENDING': { color: 'text-yellow-400', label: 'Pending' },
  'IN_PROGRESS': { color: 'text-blue-400', label: 'In Progress' },
  'DONE': { color: 'text-green-400', label: 'Done' },
  'SKIPPED': { color: 'text-gray-400', label: 'Skipped' },
}

export default function TaskDetailsDrawer({ task, events, loading, onClose }: TaskDetailsDrawerProps) {
  const { fetchTaskDetails, fetchTaskEvents, completeAssignment } = useTaskStore()
  const user = useAuthStore((state) => state.user)
  const [completingStepId, setCompletingStepId] = useState<number | null>(null)
  const [expandedStepId, setExpandedStepId] = useState<number | null>(null)  // For showing notes input
  const [stepNotes, setStepNotes] = useState<string>('')  // Notes for current step
  // Admin form state
  const [reassignUserId, setReassignUserId] = useState<string>('')
  const [assignmentReassign, setAssignmentReassign] = useState<Record<number, { user?: string; role?: string }>>({})
  
  // Refresh task details when drawer opens
  useEffect(() => {
    if (task) {
      fetchTaskDetails(task.id)
      fetchTaskEvents(task.id)
    }
  }, [task?.id, fetchTaskDetails, fetchTaskEvents])

  // Helper: get assignments belonging to current user for this task
  const myAssignmentsForTask = task?.assignments?.filter(a => a.user_id === user?.id) ?? []
  
  if (!task) return null
  
  const typeConfig = taskTypeConfig[normalizeType(task.task_type)] || taskTypeConfig['CUSTOM']
  const status = statusConfig[normalizeStatus(task.status)] || statusConfig['PENDING']
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
            
            {/* My Tasks Checklist - Shows user's assigned assignments (hidden for admins) */}
            {myAssignmentsForTask.length > 0 && !user?.is_system_admin && (
              <div className="bg-[#1e1f22] rounded-lg p-4">
                <h4 className="text-sm font-semibold text-white mb-3 flex items-center gap-2">
                  <CheckCircle size={16} className="text-[#5865f2]" />
                  My Tasks ({myAssignmentsForTask.filter(a => a.status === 'DONE').length}/{myAssignmentsForTask.length} completed)
                </h4>
                <div className="space-y-3">
                  {myAssignmentsForTask.map((assignment) => {
                    const canComplete = assignment.status !== 'DONE' && (assignment.user_id === user?.id || user?.is_system_admin)
                    const isCompleting = completingStepId === assignment.id
                    const isExpanded = expandedStepId === assignment.id

                    const handleComplete = async () => {
                      if (!canComplete || isCompleting) return
                      setCompletingStepId(assignment.id)
                      try {
                        const notes = stepNotes.trim() || (assignment.notes || `Completed assignment`)
                        const success = await completeAssignment(task.id, notes)
                        if (success) {
                          fetchTaskDetails(task.id)
                          fetchTaskEvents(task.id)
                          setExpandedStepId(null)
                          setStepNotes('')
                        }
                      } finally {
                        setCompletingStepId(null)
                      }
                    }

                    return (
                      <div 
                        key={assignment.id}
                        className={clsx(
                          "p-3 rounded-lg transition-all",
                          assignment.status === 'DONE' && "bg-green-600/10",
                          assignment.status !== 'DONE' && "bg-[#2b2d31]",
                        )}
                      >
                        <div className="flex items-start gap-3">
                          {/* Checkbox */}
                          <button
                            onClick={() => {
                              if (!canComplete || isCompleting) return
                              if (isExpanded) {
                                // If already expanded, complete it
                                handleComplete()
                              } else {
                                // Expand to show notes input
                                setExpandedStepId(assignment.id)
                                setStepNotes('')
                              }
                            }}
                            disabled={!canComplete || isCompleting}
                            className={clsx(
                              "w-6 h-6 rounded border-2 flex items-center justify-center flex-shrink-0 mt-0.5 transition-all",
                              assignment.status === 'DONE' && "bg-green-600 border-green-600 text-white",
                              canComplete && !isCompleting && "border-[#5865f2] hover:bg-[#5865f2]/20 cursor-pointer",
                              !canComplete && assignment.status !== 'DONE' && "border-[#4e5058] cursor-not-allowed",
                              isCompleting && "border-[#5865f2] animate-pulse"
                            )}
                          >
                            {assignment.status === 'DONE' && <CheckCircle size={14} />}
                            {isCompleting && <Loader2 size={14} className="animate-spin text-[#5865f2]" />}
                          </button>
                          
                          <div className="flex-1">
                            <div className="flex items-center gap-2">
                              <span className={clsx(
                                "text-sm font-medium",
                                assignment.status === 'DONE' && "text-green-400 line-through",
                                assignment.status !== 'DONE' && "text-white",
                              )}>
                                {assignment.role_hint ? assignment.role_hint : 'Task'}
                              </span>
                            </div>

                            {assignment.status === 'DONE' && (
                              <span className="text-xs text-green-400 block mt-1">
                                ✓ Completed
                              </span>
                            )}

                            {assignment.status !== 'DONE' && (
                              <span className="text-xs text-[#72767d] block mt-1">
                                {assignment.notes || 'Click checkbox to mark done'}
                              </span>
                            )}
                          </div>
                        </div>

                        {/* Expanded notes input */}
                        {isExpanded && canComplete && (
                          <div className="mt-3 pt-3 border-t border-[#3f4147] space-y-2">
                            <textarea
                              placeholder="Add a note (optional)..."
                              value={stepNotes}
                              onChange={(e) => setStepNotes(e.target.value)}
                              className="w-full px-3 py-2 bg-[#1e1f22] border border-[#3f4147] rounded-lg text-white text-sm placeholder-[#72767d] focus:outline-none focus:ring-1 focus:ring-[#5865f2] resize-none"
                              rows={2}
                              autoFocus
                            />
                            <div className="flex gap-2">
                              <button
                                onClick={handleComplete}
                                disabled={isCompleting}
                                className="flex-1 px-4 py-2 bg-green-600 hover:bg-green-700 disabled:bg-green-800 text-white text-sm font-medium rounded-lg transition-colors flex items-center justify-center gap-2"
                              >
                                {isCompleting ? (
                                  <>
                                    <Loader2 size={16} className="animate-spin" />
                                    Processing...
                                  </>
                                ) : (
                                  <>
                                    <CheckCircle size={16} />
                                    Complete assignment
                                  </>
                                )}
                              </button>
                              <button
                                onClick={() => {
                                  setExpandedStepId(null)
                                  setStepNotes('')
                                }}
                                className="px-4 py-2 bg-[#4e5058] hover:bg-[#6d6f78] text-white text-sm font-medium rounded-lg transition-colors"
                              >
                                Cancel
                              </button>
                            </div>
                          </div>
                        )}
                      </div>
                    )
                  })}
                </div>

                {/* Show message when all assignments done */}
                {myAssignmentsForTask.length > 0 && myAssignmentsForTask.every(a => a.status === 'DONE') && (
                  <div className="mt-3 p-3 bg-green-600/20 rounded-lg text-center">
                    <CheckCircle size={20} className="text-green-400 mx-auto mb-1" />
                    <span className="text-sm text-green-400 font-medium">All your tasks completed!</span>
                  </div>
                )}
              </div>
            )}
            
            
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

            {/* Order details (readonly, admin may view) */}
            {task.order_details && Object.keys(task.order_details).length > 0 && (
              <div>
                <h4 className="text-sm font-semibold text-white mb-3 flex items-center gap-2">
                  <Package size={16} />
                  Order Details
                </h4>
                <div className="bg-[#2b2d31] rounded-lg p-3">
                  <pre className="text-xs text-[#949ba4] whitespace-pre-wrap overflow-x-auto">
                    {JSON.stringify(task.order_details, null, 2)}
                  </pre>
                </div>
              </div>
            )}
            
            {/* Admin Controls */}
            {user?.is_system_admin && (
              <div className="bg-[#2b2d31] rounded-lg p-3 mb-4">
                <h4 className="text-sm font-semibold text-white mb-3">Admin Controls</h4>
                <div className="flex items-center gap-2">
                  <input
                    placeholder="New user id"
                    type="number"
                    value={reassignUserId}
                    onChange={(e) => setReassignUserId(e.target.value)}
                    className="px-3 py-2 bg-[#1e1f22] border border-[#3f4147] rounded-lg text-white text-sm w-36"
                  />
                  <button
                    onClick={async () => {
                      const v = parseInt(reassignUserId, 10)
                      if (!v) return alert('Enter a valid user id')
                      if (!confirm(`Reassign task #${task.id} to user ${v}?`)) return
                      try {
                        await api.post(`/api/automation/tasks/${task.id}/reassign`, { new_user_id: v })
                        setReassignUserId('')
                        await fetchTaskDetails(task.id)
                        await fetchTaskEvents(task.id)
                        alert('Task reassigned')
                      } catch (e) {
                        console.error(e)
                        alert('Failed to reassign task')
                      }
                    }}
                    className="px-3 py-2 bg-[#5865f2] hover:bg-[#4752c4] text-white rounded-lg"
                  >
                    Reassign Task
                  </button>

                  <button
                    onClick={async () => {
                      if (!confirm(`Force complete task #${task.id}? This will mark all assignments DONE and close the task.`)) return
                      try {
                        await api.post(`/api/automation/tasks/${task.id}/complete`, { notes: 'admin force complete' })
                        await fetchTaskDetails(task.id)
                        await fetchTaskEvents(task.id)
                        alert('Task force-completed')
                      } catch (e) {
                        console.error(e)
                        alert('Failed to force-complete task')
                      }
                    }}
                    className="px-3 py-2 bg-green-600 hover:bg-green-700 text-white rounded-lg"
                  >
                    Complete Task
                  </button>

                  <button
                    onClick={async () => {
                      if (!confirm(`Soft-delete (cancel) task #${task.id}?`)) return
                      try {
                        await api.post(`/api/automation/tasks/${task.id}/delete`)
                        await fetchTaskDetails(task.id)
                        await fetchTaskEvents(task.id)
                        alert('Task cancelled')
                      } catch (e) {
                        console.error(e)
                        alert('Failed to delete task')
                      }
                    }}
                    className="px-3 py-2 bg-red-600 hover:bg-red-700 text-white rounded-lg"
                  >
                    Cancel Task
                  </button>
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
                  {task.assignments.map((assignment) => {
                    const isMyAssignment = assignment.user_id === user?.id
                    const assignmentStatus = normalizeStatus(assignment.status)
                    const effectiveAssignmentStatus = normalizeStatus(task.status) === 'COMPLETED' ? 'DONE' : assignmentStatus
                    
                    return (
                      <div 
                        key={assignment.id}
                        className={clsx(
                          "bg-[#2b2d31] rounded-lg p-3",
                          isMyAssignment && "ring-1 ring-[#5865f2]"
                        )}
                      >
                        <div className="flex items-center justify-between">
                          <div>
                            <span className="text-white font-medium">
                              {isMyAssignment ? 'You' : `User #${assignment.user_id}`}
                            </span>
                            {assignment.role_hint && (
                              <span className="text-[#72767d] text-sm ml-2">({assignment.role_hint})</span>
                            )}
                            {assignment.notes && (
                              <p className="text-[#949ba4] text-sm mt-1">{assignment.notes}</p>
                            )}
                          </div>
                          <span className={clsx(
                            'text-sm font-medium',
                            assignmentStatusConfig[effectiveAssignmentStatus]?.color || 'text-gray-400'
                          )}>
                            {assignmentStatusConfig[effectiveAssignmentStatus]?.label || effectiveAssignmentStatus}
                          </span>
                        </div>
                        
                        {/* Show completed status */}
                        {(isMyAssignment && effectiveAssignmentStatus === 'DONE') && (
                          <div className="mt-3 pt-3 border-t border-[#1f2023] text-green-400 text-sm flex items-center gap-2">
                            <CheckCircle size={16} />
                            Assignment completed
                            {assignment.completed_at && (
                              <span className="text-[#72767d]">
                                ({formatDate(assignment.completed_at)})
                              </span>
                            )}
                          </div>
                        )}

                        {/* Admin: reassignment controls per assignment */}
                        {user?.is_system_admin && (
                          <div className="mt-3 pt-3 border-t border-[#1f2023] flex items-center gap-2">
                            <input
                              placeholder="New user id"
                              type="number"
                              value={assignmentReassign[assignment.id]?.user || ''}
                              onChange={(e) => setAssignmentReassign(prev => ({ ...prev, [assignment.id]: { ...(prev[assignment.id] || {}), user: e.target.value } }))}
                              className="px-3 py-2 bg-[#1e1f22] border border-[#3f4147] rounded-lg text-white text-sm w-32"
                            />
                            <input
                              placeholder="New role (optional)"
                              type="text"
                              value={assignmentReassign[assignment.id]?.role || ''}
                              onChange={(e) => setAssignmentReassign(prev => ({ ...prev, [assignment.id]: { ...(prev[assignment.id] || {}), role: e.target.value } }))}
                              className="px-3 py-2 bg-[#1e1f22] border border-[#3f4147] rounded-lg text-white text-sm w-36"
                            />
                            <button
                              onClick={async () => {
                                const tmp = assignmentReassign[assignment.id] || {}
                                const newUser = parseInt(tmp.user || '', 10)
                                const newRole = tmp.role || null
                                if (!newUser) return alert('Enter a valid user id')
                                if (!confirm(`Reassign assignment #${assignment.id} to user ${newUser}?`)) return
                                try {
                                  await api.post(`/api/automation/assignments/${assignment.id}/reassign`, { new_user_id: newUser, new_role_hint: newRole })
                                  setAssignmentReassign(prev => ({ ...prev, [assignment.id]: {} }))
                                  await fetchTaskDetails(task.id)
                                  await fetchTaskEvents(task.id)
                                  alert('Assignment reassigned')
                                } catch (e) {
                                  console.error(e)
                                  alert('Failed to reassign assignment')
                                }
                              }}
                              className="px-3 py-2 bg-[#5865f2] hover:bg-[#4752c4] text-white rounded-lg"
                            >
                              Reassign
                            </button>
                          </div>
                        )}
                      </div>
                    )
                  })}
                </div>
              )}
            </div>
            
            {/* Timeline / Events */}
            <div>
              <h4 className="text-sm font-semibold text-white mb-3 flex items-center gap-2">
                <Clock size={16} />
                Activity Timeline ({events.length})
              </h4>
              {user?.is_system_admin && (
                <div className="text-xs text-[#72767d] mb-2">🔒 Admin audit entries are shown here.</div>
              )}
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
