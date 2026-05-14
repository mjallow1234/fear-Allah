import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuthStore } from '../stores/authStore'
import { useTaskStore } from '../stores/taskStore'
import { useOrderStore } from '../stores/orderStore'
import useOperationalPermissions from '../permissions/useOperationalPermissions'
import { useUICapabilities } from '../permissions/uiPermissions'

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
  const { canViewSystemConsole } = useUICapabilities()
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
        {/* Left: hamburger (mobile) + channel name */}
        <div className="flex items-center gap-2 min-w-0">
          {onMenuClick && (
            <button
              onClick={onMenuClick}
              className="md:hidden p-2 transition-colors icon-button flex-shrink-0"
              style={{ color: 'var(--text-secondary)' }}
              aria-label="Open menu"
            >
              <Menu size={20} />
            </button>
          )}
          <Hash size={20} className="flex-shrink-0" style={{ color: 'var(--text-secondary)' }} />
          <span className="font-semibold truncate" style={{ color: 'var(--text-primary)' }}>{channelName}</span>
          {channelId && (
            <button
              onClick={() => setSettingsOpen(true)}
              className="p-1 transition-colors flex-shrink-0"
              style={{ color: 'var(--text-secondary)' }}
              title="Channel Settings"
            >
              <Settings size={16} />
            </button>
          )}
        </div>

        {/* Right: action icons */}
        <div className="flex items-center gap-1 flex-shrink-0">
          {/* Search — icon-only on mobile, text label on md+ */}
          <button
            onClick={() => setSearchOpen(true)}
            className="flex items-center gap-2 px-2 md:px-3 py-1 rounded transition-colors"
            style={{ backgroundColor: 'var(--input-bg)', color: 'var(--text-secondary)' }}
            onMouseEnter={(e) => e.currentTarget.style.backgroundColor = 'var(--input-hover)'}
            onMouseLeave={(e) => e.currentTarget.style.backgroundColor = 'var(--input-bg)'}
            aria-label="Search"
          >
            <Search size={16} />
            <span className="hidden md:inline text-sm">Search</span>
            <kbd className="hidden md:inline text-xs px-1 rounded" style={{ backgroundColor: 'var(--topbar-bg)' }}>Ctrl+K</kbd>
          </button>
          
          {/* Notification Bell */}
          <NotificationBell />
          
          {/* Task Inbox */}
          {perms.tabs.includes('tasks') && (
            <button
              onClick={() => handleTabNavigate('/tasks', 'tasks')}
              className="relative p-2 transition-colors icon-button"
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
              className="relative p-2 transition-colors icon-button"
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
              className="p-2 transition-colors icon-button"
              style={{ color: 'var(--text-secondary)' }}
              title="Sales & Inventory"
            >
              <DollarSign size={20} />
            </button>
          )}
          
          {/* Audit Log — desktop only */}
          {canViewSystemConsole && (
            <button
              onClick={() => navigate('/system/audit')}
              className="hidden md:flex p-2 transition-colors icon-button"
              style={{ color: 'var(--text-secondary)' }}
              title="Audit Log"
            >
              <FileText size={20} />
            </button>
          )}
          
          {/* System Console — desktop only */}
          {canViewSystemConsole && (
            <button
              onClick={() => navigate('/system')}
              className="hidden md:flex p-2 text-purple-400 hover:text-purple-300 transition-colors icon-button"
              title="System Console"
            >
              <Cog size={20} />
            </button>
          )}

          {/* Online count — desktop only */}
          {onlineCount !== undefined && (
            <div className="hidden md:flex items-center gap-1 text-sm ml-1" style={{ color: 'var(--text-secondary)' }}>
              <Users size={16} />
              <span>{onlineCount} online</span>
            </div>
          )}

          {/* Role label — desktop only */}
          {(() => {
            const roleLabel = currentUser?.is_system_admin
              ? 'Admin'
              : currentUser?.operational_roles?.length
                ? currentUser.operational_roles.join(', ')
                : 'Member'
            return (
              <span
                className="hidden md:inline"
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

          {/* Username — desktop only */}
          <span className="hidden md:inline text-sm ml-1" style={{ color: 'var(--text-secondary)' }}>
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
