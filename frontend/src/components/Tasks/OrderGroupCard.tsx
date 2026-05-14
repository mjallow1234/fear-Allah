/**
 * OrderGroupCard Component
 * Groups multiple AutomationTasks belonging to the same order
 * into a single card to eliminate duplicates in Completed / All tabs.
 */
import { Clock, Package, ShoppingCart, Warehouse, User } from 'lucide-react'
import clsx from 'clsx'
import { AutomationTask } from '../../stores/taskStore'

interface OrderGroupCardProps {
  orderId: number
  tasks: AutomationTask[]
  onClick: (task: AutomationTask) => void
  canConvert?: boolean
  onConvert?: () => void
}

const typeIconMap: Record<string, typeof Package> = {
  RESTOCK: Warehouse,
  RETAIL: ShoppingCart,
  WHOLESALE: Package,
}
const typeColorMap: Record<string, string> = {
  RESTOCK: 'bg-blue-600',
  RETAIL: 'bg-green-600',
  WHOLESALE: 'bg-purple-600',
}
const typeLabelMap: Record<string, string> = {
  RESTOCK: 'Restock',
  RETAIL: 'Retail',
  WHOLESALE: 'Wholesale',
}

function deriveOrderStatus(tasks: AutomationTask[]): { label: string; color: string; bgColor: string } {
  const statuses = tasks.map(t => (t.status || '').toString().toLowerCase())
  if (statuses.every(s => s === 'completed')) {
    return { label: 'Completed', color: 'text-green-400', bgColor: 'bg-green-400/10' }
  }
  if (statuses.some(s => s === 'in_progress' || s === 'claimed')) {
    return { label: 'In Progress', color: 'text-blue-400', bgColor: 'bg-blue-400/10' }
  }
  return { label: 'Pending', color: 'text-yellow-400', bgColor: 'bg-yellow-400/10' }
}

function formatTime(dateStr: string) {
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

export default function OrderGroupCard({ orderId, tasks, onClick, canConvert, onConvert }: OrderGroupCardProps) {
  // Use the root task (is_order_root) as the primary; fallback to first task

  // STEP 2: Aggregate sale_status across all tasks — active > reversed > none
  const saleStatuses = tasks
    .map(t => t.order_details?.sale_status)
    .filter(Boolean);

  let saleStatus = 'none';
  if (saleStatuses.includes('active')) {
    saleStatus = 'active';
  } else if (saleStatuses.includes('reversed')) {
    saleStatus = 'reversed';
  }
  const rootTask = tasks.find(t => (t as any).is_order_root) || tasks[0]
  const orderStatus = deriveOrderStatus(tasks)

  const taskType = (rootTask.task_type || 'CUSTOM').toString().toUpperCase()
  const TypeIcon = typeIconMap[taskType] || Package
  const typeColor = typeColorMap[taskType] || 'bg-gray-600'
  const typeLabel = typeLabelMap[taskType] || taskType

  // Collect unique roles across all tasks
  const roleEntries = tasks
    .filter(t => t.required_role)
    .map(t => {
      const s = (t.status || '').toString().toLowerCase()
      return {
        role: t.required_role!,
        status: s === 'completed' ? 'Done' : s === 'in_progress' || s === 'claimed' ? 'In Progress' : 'Pending',
        statusColor: s === 'completed' ? 'text-green-400' : s === 'in_progress' || s === 'claimed' ? 'text-blue-400' : 'text-yellow-400',
      }
    })

  return (
    <div
      onClick={() => onClick(rootTask)}
      className={clsx(
        'task-item rounded-lg cursor-pointer transition-all border',
        rootTask.status === 'completed'
          ? 'bg-[#2b2d31] border-[#1f2023] opacity-75'
          : 'bg-[#2b2d31] border-[#1f2023] hover:bg-[#35373c] hover:border-[#35373c]'
      )}
    >
      <div className="flex items-start gap-4">
        {/* Type Icon */}
        <div className={clsx('w-10 h-10 rounded-lg flex items-center justify-center text-white', typeColor)}>
          <TypeIcon size={20} />
        </div>

        {/* Content */}
        <div className="flex-1 min-w-0">
          {/* Header */}
          <div className="flex items-center gap-2 mb-1">
            <span className="text-white font-medium truncate">Order #{orderId}</span>
            <span className={clsx('text-xs px-2 py-0.5 rounded-full', orderStatus.bgColor, orderStatus.color)}>
              {orderStatus.label}
            </span>
          </div>

          {rootTask.description && (
            <p className="text-sm text-[#949ba4] truncate mb-2">{rootTask.description}</p>
          )}

          {/* Meta row */}
          <div className="flex items-center gap-4 text-xs text-[#72767d]">
            <span className="flex items-center gap-1">
              <Clock size={12} />
              {formatTime(rootTask.created_at)}
            </span>
            <span className={clsx('px-1.5 py-0.5 rounded', typeColor + '/20', 'text-white/80')}>
              {typeLabel}
            </span>
            {tasks.length > 1 && (
              <span className="flex items-center gap-1">
                <User size={12} />
                {tasks.length} roles
              </span>
            )}
          </div>

          {/* Role breakdown */}
          {roleEntries.length > 0 && (
            <div className="mt-2 pt-2 border-t border-[#1f2023] flex flex-wrap gap-x-4 gap-y-1">
              {roleEntries.map((r) => (
                <div key={r.role} className="flex items-center gap-1.5 text-xs">
                  <span className="text-[#72767d] capitalize">{r.role}</span>
                  <span className={r.statusColor}>{r.status}</span>
                </div>
              ))}
            </div>
          )}
        </div>

        <div className="flex-shrink-0 flex flex-col items-end gap-2">

          {/* ACTIVE SALE */}
          {saleStatus === 'active' && (
            <span className="text-green-500 text-xs font-medium">
              ✔ Converted to Sale
            </span>
          )}

          {/* REVERSED SALE */}
          {saleStatus === 'reversed' && (
            <>
              <span className="text-yellow-500 text-xs font-medium">
                ↺ Sale Reversed
              </span>
            </>
          )}

          {/* NO SALE */}
          {saleStatus === 'none' && canConvert && rootTask.status === 'completed' && (
            <button
              onClick={(e) => { e.stopPropagation(); onConvert?.() }}
              className="px-2 py-1 text-xs rounded bg-[#5865f2] hover:bg-[#4752c4] text-white transition-colors"
            >
              Convert to Sale
            </button>
          )}

        </div>
      </div>
    </div>
  )
}
