import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuthStore } from '../stores/authStore'
import { Hash, Users, Search, Settings } from 'lucide-react'
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
