/**
 * TaskCard Component
 * Phase 7.2 - Task Inbox UI
 * 
 * Displays a single task with status, type, and actions.
 */
import { useState } from 'react'
import { 
  Package, 
  ShoppingCart, 
  Warehouse, 
  Tag, 
  Wrench,
  Check,
  Clock,
  XCircle,
  Loader2,
  User
} from 'lucide-react'
import clsx from 'clsx'
import { 
  AutomationTask, 
  TaskAssignment
} from '../../stores/taskStore'

interface TaskCardProps {
  task: AutomationTask
  assignment?: TaskAssignment
  currentUserId: number
  isCompleting: boolean
  onComplete: (taskId: number) => void
  onClick: () => void
}

// Helper to normalize status to uppercase for config lookup
const normalizeStatus = (status: string): string => status?.toUpperCase() || 'PENDING'
const normalizeType = (type: string): string => type?.toUpperCase() || 'CUSTOM'

// Task type icons and colors
const taskTypeConfig: Record<string, { icon: typeof Package; color: string; label: string }> = {
  'RESTOCK': { icon: Warehouse, color: 'bg-blue-600', label: 'Restock' },
  'RETAIL': { icon: ShoppingCart, color: 'bg-green-600', label: 'Retail' },
  'WHOLESALE': { icon: Package, color: 'bg-purple-600', label: 'Wholesale' },
  'SALE': { icon: Tag, color: 'bg-orange-600', label: 'Sale' },
  'CUSTOM': { icon: Wrench, color: 'bg-gray-600', label: 'Custom' },
}

// Status badge config
const statusConfig: Record<string, { color: string; bgColor: string; label: string }> = {
  'PENDING': { color: 'text-yellow-400', bgColor: 'bg-yellow-400/10', label: 'Pending' },
  'IN_PROGRESS': { color: 'text-blue-400', bgColor: 'bg-blue-400/10', label: 'In Progress' },
  'COMPLETED': { color: 'text-green-400', bgColor: 'bg-green-400/10', label: 'Completed' },
  'CANCELLED': { color: 'text-red-400', bgColor: 'bg-red-400/10', label: 'Cancelled' },
}

const assignmentStatusConfig: Record<string, { color: string; label: string }> = {
  'PENDING': { color: 'text-yellow-400', label: 'Pending' },
  'IN_PROGRESS': { color: 'text-blue-400', label: 'In Progress' },
  'DONE': { color: 'text-green-400', label: 'Done' },
  'SKIPPED': { color: 'text-gray-400', label: 'Skipped' },
}

export default function TaskCard({ 
  task, 
  assignment, 
  currentUserId, 
  isCompleting, 
  onComplete, 
  onClick 
}: TaskCardProps) {
  const [showConfirm, setShowConfirm] = useState(false)
  
  // Normalize status/type to uppercase for config lookup (backend may return lowercase)
  const normalizedTaskType = normalizeType(task.task_type)
  const normalizedTaskStatus = normalizeStatus(task.status)
  const normalizedAssignmentStatus = assignment ? normalizeStatus(assignment.status) : null
  
  const typeConfig = taskTypeConfig[normalizedTaskType] || taskTypeConfig['CUSTOM']
  const status = statusConfig[normalizedTaskStatus] || statusConfig['PENDING']
  const TypeIcon = typeConfig.icon
  
  // Check if user can complete this task (compare normalized values)
  const canComplete = assignment && 
    assignment.user_id === currentUserId && 
    normalizedAssignmentStatus !== 'DONE' && 
    normalizedAssignmentStatus !== 'SKIPPED' &&
    normalizedTaskStatus !== 'COMPLETED' &&
    normalizedTaskStatus !== 'CANCELLED'
  
  const formatTime = (dateStr: string) => {
    const date = new Date(dateStr)
    const now = new Date()
    const diff = now.getTime() - date.getTime()
    const minutes = Math.floor(diff / 60000)
    const hours = Math.floor(minutes / 60)
    const days = Math.floor(hours / 24)

    if (minutes < 1) return 'Just now'
    if (minutes < 60) return `${minutes}m ago`
    if (hours < 24) return `${hours}h ago`
    if (days < 7) return `${days}d ago`
    return date.toLocaleDateString()
  }

  const handleCompleteClick = (e: React.MouseEvent) => {
    e.stopPropagation()
    setShowConfirm(true)
  }

  const handleConfirmComplete = (e: React.MouseEvent) => {
    e.stopPropagation()
    setShowConfirm(false)
    onComplete(task.id)
  }

  const handleCancelComplete = (e: React.MouseEvent) => {
    e.stopPropagation()
    setShowConfirm(false)
  }

  return (
    <div
      onClick={onClick}
      className={clsx(
        'p-4 rounded-lg cursor-pointer transition-all border',
        normalizedTaskStatus === 'COMPLETED' || normalizedTaskStatus === 'CANCELLED'
          ? 'bg-[#2b2d31] border-[#1f2023] opacity-75'
          : 'bg-[#2b2d31] border-[#1f2023] hover:bg-[#35373c] hover:border-[#35373c]'
      )}
    >
      <div className="flex items-start gap-4">
        {/* Type Icon */}
        <div className={clsx(
          'w-10 h-10 rounded-lg flex items-center justify-center text-white',
          typeConfig.color
        )}>
          <TypeIcon size={20} />
        </div>
        
        {/* Content */}
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <span className="text-white font-medium truncate">{task.title}</span>
            <span className={clsx(
              'text-xs px-2 py-0.5 rounded-full',
              status.bgColor,
              status.color
            )}>
              {status.label}
            </span>
          </div>
          
          {task.description && (
            <p className="text-sm text-[#949ba4] truncate mb-2">{task.description}</p>
          )}
          
          <div className="flex items-center gap-4 text-xs text-[#72767d]">
            <span className="flex items-center gap-1">
              <Clock size={12} />
              {formatTime(task.created_at)}
            </span>
            <span className={clsx('px-1.5 py-0.5 rounded', typeConfig.color + '/20', 'text-white/80')}>
              {typeConfig.label}
            </span>
            {task.assignments.length > 0 && (
              <span className="flex items-center gap-1">
                <User size={12} />
                {task.assignments.length} assigned
              </span>
            )}
          </div>
          
          {/* Assignment status if viewing from My Tasks */}
          {assignment && (
            <div className="mt-2 pt-2 border-t border-[#1f2023]">
              <div className="flex items-center gap-2 text-xs">
                <span className="text-[#72767d]">Your assignment:</span>
                <span className={assignmentStatusConfig[normalizedAssignmentStatus || 'PENDING']?.color || 'text-gray-400'}>
                  {assignmentStatusConfig[normalizedAssignmentStatus || 'PENDING']?.label || assignment.status}
                </span>
                {assignment.role_hint && (
                  <span className="text-[#72767d]">({assignment.role_hint})</span>
                )}
              </div>
            </div>
          )}
        </div>
        
        {/* Action Button */}
        <div className="flex-shrink-0">
          {canComplete && !showConfirm && (
            <button
              onClick={handleCompleteClick}
              disabled={isCompleting}
              className={clsx(
                'flex items-center gap-2 px-3 py-2 rounded-lg transition-colors',
                isCompleting
                  ? 'bg-[#1f2023] text-[#72767d] cursor-not-allowed'
                  : 'bg-green-600 hover:bg-green-700 text-white'
              )}
            >
              {isCompleting ? (
                <Loader2 size={16} className="animate-spin" />
              ) : (
                <Check size={16} />
              )}
              Complete
            </button>
          )}
          
          {showConfirm && (
            <div className="flex items-center gap-2">
              <button
                onClick={handleConfirmComplete}
                className="p-2 bg-green-600 hover:bg-green-700 text-white rounded-lg transition-colors"
                title="Confirm completion"
              >
                <Check size={16} />
              </button>
              <button
                onClick={handleCancelComplete}
                className="p-2 bg-[#1f2023] hover:bg-[#35373c] text-[#949ba4] rounded-lg transition-colors"
                title="Cancel"
              >
                <XCircle size={16} />
              </button>
            </div>
          )}
          
          {!canComplete && normalizedAssignmentStatus === 'DONE' && (
            <span className="flex items-center gap-1 text-green-400 text-sm">
              <Check size={16} />
              Done
            </span>
          )}
        </div>
      </div>
    </div>
  )
}
