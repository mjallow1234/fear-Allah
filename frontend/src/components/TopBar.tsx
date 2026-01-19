import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuthStore } from '../stores/authStore'
import { Hash, Users, Search, Settings, FileText, Cog } from 'lucide-react'
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
  const currentUser = useAuthStore((state) => state.currentUser)
  const navigate = useNavigate()
  const [searchOpen, setSearchOpen] = useState(false)
  const [settingsOpen, setSettingsOpen] = useState(false)
  




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

          {/* Operational role label (informational only) */}
          {currentUser?.operational_role_name && (
            <span
              style={{
                fontSize: "12px",
                opacity: 0.8,
                padding: "4px 8px",
                borderRadius: "6px",
                background: "#1f2937",
                color: "#e5e7eb",
                textTransform: "capitalize",
              }}
            >
              Role: {currentUser.operational_role_name.replace("_", " ")}
            </span>
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
