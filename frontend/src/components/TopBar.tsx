import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuthStore } from '../stores/authStore'
import { useTaskStore } from '../stores/taskStore'
import { useOrderStore } from '../stores/orderStore'
import { Hash, Users, Search, Settings, ClipboardList, ShoppingCart, DollarSign, FileText, Cog } from 'lucide-react'
import SearchModal from './SearchModal'
import NotificationBell from './NotificationBell'
import ChannelSettings from './ChannelSettings'

interface TopBarProps {
  channelName?: string
  channelId?: number
  onlineCount?: number
}

export default function TopBar({ channelName = 'general', channelId, onlineCount }: TopBarProps) {
  const user = useAuthStore((state) => state.user)
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
  
  // Fetch assignments on mount
  useEffect(() => {
    fetchMyAssignments()
  }, [fetchMyAssignments])

  const handleSearchResultClick = (channelId: number, _messageId: number) => {
    navigate(`/channel/${channelId}`)
    // TODO: Scroll to specific message
  }

  return (
    <>
      <div className="h-12 bg-[#313338] border-b border-[#1f2023] flex items-center px-4 justify-between">
        <div className="flex items-center gap-2">
          <Hash size={20} className="text-[#949ba4]" />
          <span className="text-white font-semibold">{channelName}</span>
          {channelId && (
            <button
              onClick={() => setSettingsOpen(true)}
              className="p-1 text-[#949ba4] hover:text-white transition-colors"
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
            className="flex items-center gap-2 px-3 py-1 bg-[#1e1f22] rounded text-[#949ba4] hover:bg-[#2e3035] transition-colors"
          >
            <Search size={16} />
            <span className="text-sm">Search</span>
            <kbd className="text-xs bg-[#313338] px-1 rounded">Ctrl+K</kbd>
          </button>
          
          {/* Notification Bell */}
          <NotificationBell />
          
          {/* Task Inbox */}
          <button
            onClick={() => navigate('/tasks')}
            className="relative p-2 text-[#949ba4] hover:text-white transition-colors"
            title="Task Inbox"
          >
            <ClipboardList size={20} />
            {pendingTaskCount > 0 && (
              <span className="absolute -top-1 -right-1 w-5 h-5 bg-[#5865f2] text-white text-xs font-bold rounded-full flex items-center justify-center">
                {pendingTaskCount > 9 ? '9+' : pendingTaskCount}
              </span>
            )}
          </button>
          
          {/* Orders - ONLY system_admin, agent, storekeeper can see */}
          {(() => {
            const role = user?.role ?? localStorage.getItem('user_role')
            const canSeeOrders = user?.is_system_admin || ['agent', 'storekeeper'].includes(role ?? '')
            return canSeeOrders ? (
              <button
                onClick={() => navigate('/orders')}
                className="relative p-2 text-[#949ba4] hover:text-white transition-colors"
                title="Orders"
              >
                <ShoppingCart size={20} />
                {activeOrderCount > 0 && (
                  <span className="absolute -top-1 -right-1 w-5 h-5 bg-orange-500 text-white text-xs font-bold rounded-full flex items-center justify-center">
                    {activeOrderCount > 9 ? '9+' : activeOrderCount}
                  </span>
                )}
              </button>
            ) : null
          })()}
          
          {/* Sales & Inventory - ONLY admin, storekeeper, agent can see */}
          {(() => {
            const role = user?.role ?? localStorage.getItem('user_role')
            const canSeeSales = user?.is_system_admin || ['admin', 'storekeeper', 'agent'].includes(role ?? '')
            return canSeeSales ? (
              <button
                onClick={() => navigate('/sales')}
                className="p-2 text-[#949ba4] hover:text-white transition-colors"
                title="Sales & Inventory"
              >
                <DollarSign size={20} />
              </button>
            ) : null
          })()}
          
          {/* Audit Log - admin only, navigates to /system/audit */}
          {user?.is_system_admin && (
            <button
              onClick={() => navigate('/system/audit')}
              className="p-2 text-[#949ba4] hover:text-white transition-colors"
              title="Audit Log"
            >
              <FileText size={20} />
            </button>
          )}
          
          {/* System Console (admin only) */}
          {user?.is_system_admin && (
            <button
              onClick={() => navigate('/system')}
              className="p-2 text-purple-400 hover:text-purple-300 transition-colors"
              title="System Console"
            >
              <Cog size={20} />
            </button>
          )}
          
          {onlineCount !== undefined && (
            <div className="flex items-center gap-1 text-sm text-[#949ba4]">
              <Users size={16} />
              <span>{onlineCount} online</span>
            </div>
          )}
          <span className="text-sm text-[#949ba4]">
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
