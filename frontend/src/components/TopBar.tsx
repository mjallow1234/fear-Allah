import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuthStore } from '../stores/authStore'
import { useTaskStore } from '../stores/taskStore'
import { useOrderStore } from '../stores/orderStore'
import useOperationalPermissions from '../permissions/useOperationalPermissions'

import { Hash, Users, Search, Settings, ClipboardList, ShoppingCart, DollarSign, FileText, Cog, Menu } from 'lucide-react'
import SearchModal from './SearchModal'
import NotificationBell from './NotificationBell'
import ChannelSettings from './ChannelSettings'

interface TopBarProps {
  channelName?: string
  channelId?: number
  onlineCount?: number
  onMenuClick?: () => void
}

export default function TopBar({ channelName = 'general', channelId, onlineCount, onMenuClick }: TopBarProps) {
  const user = useAuthStore((state) => state.user)
  const currentUser = useAuthStore((state) => state.currentUser)
  const navigate = useNavigate()
  const [searchOpen, setSearchOpen] = useState(false)
  const [settingsOpen, setSettingsOpen] = useState(false)
  
  // Task inbox badge count
  const myAssignments = useTaskStore((state) => state.myAssignments)
  const fetchMyAssignments = useTaskStore((state) => state.fetchMyAssignments)
  const pendingTaskCount = myAssignments.filter(a => a.status === 'PENDING' || a.status === 'IN_PROGRESS').length
  
  // Orders count (active orders with automation)
  const orders = useOrderStore((state) => state.orders)
  const activeOrderCount = orders.filter(o => 
    o.status !== 'COMPLETED' && o.status !== 'CANCELLED' && o.automation?.has_automation
  ).length

  // Permissions based on operational role
  // Use authoritative `currentUser` to determine operational tab visibility.
  
  // Fetch assignments on mount
  useEffect(() => {
    fetchMyAssignments()
  }, [fetchMyAssignments])

  // Permissions for click-time checks — authoritative single source
  const perms = useOperationalPermissions()
  const isSystemAdmin = currentUser?.is_system_admin === true
  const handleTabNavigate = (path: string, tabKey: 'orders' | 'sales' | 'tasks') => {
    // Only allow navigation when tab is explicitly permitted
    if (!perms.tabs.includes(tabKey)) {
      navigate('/unauthorized')
      return
    }
    navigate(path)
  }

  const handleSearchResultClick = (channelId: number, _messageId: number) => {
    navigate(`/channel/${channelId}`)
    // TODO: Scroll to specific message
  }

  return (
    <>
      <div className="topbar h-12 flex items-center px-4 justify-between" style={{ backgroundColor: 'var(--topbar-bg)', borderBottom: '1px solid var(--topbar-border)' }}>
        <div className="flex items-center gap-2">
          {/* Mobile menu button */}
          {onMenuClick && (
            <button
              onClick={onMenuClick}
              className="md:hidden p-2 transition-colors icon-button"
              style={{ color: 'var(--text-secondary)' }}
              aria-label="Open menu"
            >
              <Menu size={20} />
            </button>
          )}
          <Hash size={20} style={{ color: 'var(--text-secondary)' }} />
          <span className="font-semibold" style={{ color: 'var(--text-primary)' }}>{channelName}</span>
          {channelId && (
            <button
              onClick={() => setSettingsOpen(true)}
              className="p-1 transition-colors"
              style={{ color: 'var(--text-secondary)' }}
              title="Channel Settings"
            >
              <Settings size={16} />
            </button>
          )}
        </div>
        <div className="flex items-center gap-4">
          {/* Search button */}
          <button
            onClick={() => setSearchOpen(true)}
            className="flex items-center gap-2 px-3 py-1 rounded transition-colors"
            style={{ backgroundColor: 'var(--input-bg)', color: 'var(--text-secondary)' }}
            onMouseEnter={(e) => e.currentTarget.style.backgroundColor = 'var(--input-hover)'}
            onMouseLeave={(e) => e.currentTarget.style.backgroundColor = 'var(--input-bg)'}
          >
            <Search size={16} />
            <span className="text-sm">Search</span>
            <kbd className="text-xs px-1 rounded" style={{ backgroundColor: 'var(--topbar-bg)' }}>Ctrl+K</kbd>
          </button>
          
          {/* Notification Bell */}
          <NotificationBell />
          
          {/* Operational tabs — visibility controlled *only* by permissions */}
          {/* Task Inbox */}
          {perms.tabs.includes('tasks') && (
            <button
              onClick={() => handleTabNavigate('/tasks', 'tasks')}
              className="relative p-2 transition-colors"
              style={{ color: 'var(--text-secondary)' }}
              title="Task Inbox"
            >
              <ClipboardList size={20} />
              {pendingTaskCount > 0 && (
                <span className="absolute -top-1 -right-1 w-5 h-5 text-white text-xs font-bold rounded-full flex items-center justify-center" style={{ backgroundColor: 'var(--accent)' }}>
                  {pendingTaskCount > 9 ? '9+' : pendingTaskCount}
                </span>
              )}
            </button>
          )}

          {/* Orders */}
          {perms.tabs.includes('orders') && (
            <button
              onClick={() => handleTabNavigate('/orders', 'orders')}
              className="relative p-2 transition-colors"
              style={{ color: 'var(--text-secondary)' }}
              title="Orders"
            >
              <ShoppingCart size={20} />
              {activeOrderCount > 0 && (
                <span className="absolute -top-1 -right-1 w-5 h-5 bg-orange-500 text-white text-xs font-bold rounded-full flex items-center justify-center">
                  {activeOrderCount > 9 ? '9+' : activeOrderCount}
                </span>
              )}
            </button>
          )}

          {/* Sales & Inventory */}
          {perms.tabs.includes('sales') && (
            <button
              onClick={() => handleTabNavigate('/sales', 'sales')}
              className="p-2 transition-colors"
              style={{ color: 'var(--text-secondary)' }}
              title="Sales & Inventory"
            >
              <DollarSign size={20} />
            </button>
          )}
          
          {/* Audit Log - admin only, navigates to /system/audit */}
          {isSystemAdmin && (
            <button
              onClick={() => navigate('/system/audit')}
              className="p-2 transition-colors"
              style={{ color: 'var(--text-secondary)' }}
              title="Audit Log"
            >
              <FileText size={20} />
            </button>
          )}
          
          {/* System Console (admin only) */}
          {isSystemAdmin && (
            <button
              onClick={() => navigate('/system')}
              className="p-2 text-purple-400 hover:text-purple-300 transition-colors"
              title="System Console"
            >
              <Cog size={20} />
            </button>
          )} 
          
          {onlineCount !== undefined && (
            <div className="flex items-center gap-1 text-sm" style={{ color: 'var(--text-secondary)' }}>
              <Users size={16} />
              <span>{onlineCount} online</span>
            </div>
          )}

          {/* Operational role label (informational only) */}
          {(() => {
            const roleLabel = currentUser?.is_system_admin
              ? 'Admin'
              : currentUser?.operational_roles?.length
                ? currentUser.operational_roles.join(', ')
                : 'Member'
            return (
              <span
                style={{
                  fontSize: "12px",
                  opacity: 0.8,
                  padding: "4px 8px",
                  borderRadius: "6px",
                  backgroundColor: "var(--input-bg)",
                  color: "var(--text-primary)",
                  textTransform: "capitalize",
                }}
              >
                Role: {roleLabel}
              </span>
            )
          })()}

          <span className="text-sm" style={{ color: 'var(--text-secondary)' }}>
            {user?.display_name || user?.username}
          </span>
        </div>
      </div>

      <SearchModal
        isOpen={searchOpen}
        onClose={() => setSearchOpen(false)}
        onResultClick={handleSearchResultClick}
      />
      
      {channelId && (
        <ChannelSettings
          isOpen={settingsOpen}
          onClose={() => setSettingsOpen(false)}
          channelId={channelId}
          channelName={channelName}
        />
      )}
    </>
  )
}
