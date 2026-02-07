import { useEffect, useState, useCallback } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import { Hash, Settings, User, MessageSquare, Circle, ChevronDown, Plus, FileText, Brain } from 'lucide-react'
import { useAuthStore } from '../stores/authStore'
import { usePresenceStore } from '../stores/presenceStore'
import api from '../services/api'
import clsx from 'clsx'
import NewDMModal from './NewDMModal'
import CreateChannelModal from './CreateChannelModal'


interface Team {
  id: number
  name: string
  display_name: string | null
  description: string | null
  icon_url: string | null
}

interface Channel {
  id: number
  name: string
  display_name: string | null
  description: string | null
  type: string
  team_id: number | null
}


interface DMChannel {
  id: number
  name: string
  display_name: string
  other_user_id: number
  other_username: string
}

interface SidebarProps {
  isOpen?: boolean
  onClose?: () => void
}

export default function Sidebar({ isOpen = false, onClose }: SidebarProps) {
  const location = useLocation()
  const navigate = useNavigate()
  const user = useAuthStore((state) => state.user)
  const token = useAuthStore((state) => state.token)
  // System admins only for administration UI in sidebar
  const isSystemAdmin = user?.is_system_admin === true
  const [teams, setTeams] = useState<Team[]>([])
  const [selectedTeam, setSelectedTeam] = useState<Team | null>(null)
  const [channels, setChannels] = useState<Channel[]>([])
  const [showTeamMenu, setShowTeamMenu] = useState(false)
  
  // Helper to navigate and close sidebar on mobile
  const navigateAndClose = (path: string) => {
    navigate(path)
    onClose?.()
  }
  
  // New Socket.IO presence from store
  const onlineUserIds = usePresenceStore((state) => state.onlineUserIds)
  const isUserOnline = (userId: number | undefined | null) => userId ? onlineUserIds.has(Number(userId)) : false

  // Team members for online display (user_id from API, not id)
  const [teamMembers, setTeamMembers] = useState<{ user_id: number; username: string; display_name?: string }[]>([])
  
  const [dmChannels, setDmChannels] = useState<DMChannel[]>([])

  const [showNewDMModal, setShowNewDMModal] = useState(false)
  const [showCreateChannelModal, setShowCreateChannelModal] = useState(false)

  // Fetch teams
  const fetchTeams = useCallback(async () => {
    if (!token) return
    try {
      const response = await api.get('/api/teams/')
      // Normalize to array to prevent .map() crashes if API returns unexpected shape
      const fetchedTeams = Array.isArray(response.data)
        ? response.data
        : Array.isArray(response.data?.teams)
          ? response.data.teams
          : []
      setTeams(fetchedTeams)
      // Auto-select first team if none selected
      if (fetchedTeams.length > 0 && !selectedTeam) {
        setSelectedTeam(fetchedTeams[0])
      }
    } catch (error) {
      console.error('Failed to fetch teams:', error)
    }
  }, [token, selectedTeam])

  // Fetch channels (global list)
  const fetchChannels = useCallback(async () => {
    if (!token) return
    try {
      // Use trailing slash to match backend route exactly and avoid 405
      const response = await api.get('/api/channels/')
      // Normalize to array to prevent .map() crashes if API returns unexpected shape
      const fetchedChannels = Array.isArray(response.data)
        ? response.data
        : Array.isArray(response.data?.channels)
          ? response.data.channels
          : []
      setChannels(fetchedChannels)
    } catch (error) {
      console.error('Failed to fetch channels:', error)
    }
  }, [token])

  // Presence is enabled via `usePresence()` and will connect once auth/user is ready.
  // The hook ensures it only starts once and manages reconnection; do not reconnect on every render.

  // Fetch DM channels
  const fetchDMChannels = useCallback(async () => {
    if (!token) return
    try {
      const response = await api.get('/api/channels/direct/list')
      // Normalize to array to prevent .map() crashes if API returns unexpected shape
      const dmData = Array.isArray(response.data)
        ? response.data
        : Array.isArray(response.data?.dm_channels)
          ? response.data.dm_channels
          : []
      setDmChannels(dmData)
    } catch (error) {
      console.error('Failed to fetch DM channels:', error)
    }
  }, [token])

  // Start a DM with a user
  const startDM = async (userId: string) => {
    try {
      const response = await api.post('/api/channels/direct', { user_id: parseInt(userId) })
      const dmChannel = response.data
      // Refresh DM list and navigate to the channel
      await fetchDMChannels()
      navigateAndClose(`/channels/${dmChannel.id}`)
    } catch (error) {
      console.error('Failed to start DM:', error)
    }
  }

  useEffect(() => {
    fetchTeams()
    fetchChannels()
    fetchDMChannels()
  }, [fetchChannels, fetchDMChannels, fetchTeams])

  // Fetch channels when team changes
  useEffect(() => {
    if (selectedTeam) {
      fetchChannels()
    }
  }, [selectedTeam, fetchChannels])

  // Fetch team members for presence display
  const fetchTeamMembers = useCallback(async () => {
    if (!token || !selectedTeam) return
    try {
      const response = await api.get(`/api/teams/${selectedTeam.id}/members`)
      const members = Array.isArray(response.data) ? response.data : []
      setTeamMembers(members)
    } catch (error) {
      console.error('Failed to fetch team members:', error)
    }
  }, [token, selectedTeam])

  useEffect(() => {
    fetchTeamMembers()
  }, [fetchTeamMembers])

  const handleSelectTeam = (team: Team) => {
    setSelectedTeam(team)
    setShowTeamMenu(false)
  }

  return (
    <div className={`sidebar w-60 h-full flex-shrink-0 bg-[#2b2d31] flex flex-col overflow-hidden md:relative md:transform-none ${isOpen ? 'open' : ''}`}>
      {/* Team selector */}
      <div className="relative">
        <button
          onClick={() => setShowTeamMenu(!showTeamMenu)}
          className="w-full h-12 flex items-center justify-between px-4 border-b border-[#1f2023] shadow-sm hover:bg-[#35373c] transition-colors"
        >
          <div className="flex items-center gap-2">
            <div className="w-6 h-6 rounded bg-[#5865f2] flex items-center justify-center text-white text-xs font-bold">
              {(() => {
                const name = selectedTeam?.display_name ?? selectedTeam?.name ?? ''
                return name ? name.charAt(0) : 'T'
              })()}
            </div>
            <span className="font-bold text-white truncate">
              {selectedTeam?.display_name || selectedTeam?.name || 'Select Team'}
            </span>
          </div>
          <ChevronDown size={18} className={clsx('text-[#949ba4] transition-transform', showTeamMenu && 'rotate-180')} />
        </button>

        {/* Team dropdown */}
        {showTeamMenu && (
          <div className="absolute top-12 left-0 right-0 bg-[#111214] border border-[#1f2023] rounded-b shadow-lg z-50 max-h-64 overflow-y-auto">
            {Array.isArray(teams) && teams.map((team) => (
              <button
                key={team.id}
                onClick={() => handleSelectTeam(team)}
                className={clsx(
                  'w-full flex items-center gap-2 px-4 py-2 hover:bg-[#35373c] transition-colors text-left',
                  selectedTeam?.id === team.id && 'bg-[#35373c]'
                )}
              >
                <div className="w-6 h-6 rounded bg-[#5865f2] flex items-center justify-center text-white text-xs font-bold">
                  {(() => { const name = team.display_name ?? team.name ?? ''; return name ? name.charAt(0) : 'T' })()}
                </div>
                <div className="flex-1 min-w-0">
                  <div className="text-white text-sm font-medium truncate">{team.display_name || team.name}</div>
                  {team.description && (
                    <div className="text-[#949ba4] text-xs truncate">{team.description}</div>
                  )}
                </div>
                {selectedTeam?.id === team.id && (
                  <div className="w-2 h-2 rounded-full bg-green-500" />
                )}
              </button>
            ))}
            {teams.length === 0 && (
              <div className="px-4 py-3 text-[#949ba4] text-sm">
                No teams available
              </div>
            )}
          </div>
        )}
      </div>

      {/* Channels */}
      <div className="flex-1 overflow-y-auto py-4">
        <div className="px-2 mb-2 flex items-center justify-between">
          <span className="text-xs font-semibold text-[#949ba4] uppercase tracking-wide px-2">
            Channels
          </span>
          <button 
            onClick={() => setShowCreateChannelModal(true)}
            className={clsx('p-1 transition-colors', isSystemAdmin ? 'text-[#949ba4] hover:text-white' : 'text-[#949ba4] opacity-50 cursor-not-allowed')}
            title={isSystemAdmin ? 'Add Channel' : 'Only admins can create channels'}
            disabled={!isSystemAdmin}
          >
            <Plus size={14} />
          </button>
        </div>
        {channels.length === 0 ? (
          <div className="flex items-center gap-2 px-4 py-2 text-[#949ba4] text-sm">
            <Hash size={16} />
            <span>No channels yet</span>
          </div>
        ) : (
          Array.isArray(channels) && channels.map((channel) => (
            <Link
              key={channel.id}
              to={`/channels/${channel.id}`}
              className={clsx(
                'flex items-center gap-2 px-2 py-1 mx-2 rounded text-[#949ba4] hover:text-[#dbdee1] hover:bg-[#35373c] transition-colors',
                location.pathname === `/channels/${channel.id}` &&
                  'bg-[#35373c] text-white'
              )}
            >
              <Hash size={18} />
              <span>{channel.display_name || channel.name}</span>
            </Link>
          ))
        )}

        {/* Direct Messages */}
        <div className="px-2 mt-6 mb-2 flex items-center justify-between">
          <span className="text-xs font-semibold text-[#949ba4] uppercase tracking-wide px-2">
            Direct Messages
          </span>
          <button 
            onClick={() => setShowNewDMModal(true)}
            className="p-1 text-[#949ba4] hover:text-white transition-colors"
            title="New Direct Message"
          >
            <Plus size={14} />
          </button>
        </div>
        {dmChannels.length === 0 ? (
          <div className="flex items-center gap-2 px-2 py-1 mx-2 text-[#949ba4] text-sm">
            <MessageSquare size={16} />
            <span>No DMs yet</span>
          </div>
        ) : (
          Array.isArray(dmChannels) && dmChannels.map((dm) => (
            <Link
              key={dm.id}
              to={`/channels/${dm.id}`}
              className={clsx(
                'flex items-center gap-2 px-2 py-1 mx-2 rounded text-[#949ba4] hover:text-[#dbdee1] hover:bg-[#35373c] transition-colors',
                location.pathname === `/channels/${dm.id}` &&
                  'bg-[#35373c] text-white'
              )}
            >
              <div className="relative">
                <div className="w-6 h-6 rounded-full bg-[#5865f2] flex items-center justify-center text-white text-xs font-medium">
                  {dm.other_username ? dm.other_username.charAt(0).toUpperCase() : '?'}
                </div>
                {isUserOnline(dm.other_user_id) && (
                  <Circle
                    size={10}
                    className="absolute -bottom-0.5 -right-0.5 fill-current text-green-500"
                  />
                )}
              </div>
              <span className="truncate">{dm.display_name}</span>
            </Link>
          ))
        )}

        {/* Online Users (presence) */}
        <div className="px-2 mt-6 mb-2">
          <span className="text-xs font-semibold text-[#949ba4] uppercase tracking-wide px-2">
            Online — {teamMembers.filter(m => m.user_id !== user?.id && isUserOnline(m.user_id)).length}
          </span>
        </div>
        {teamMembers.filter(m => m.user_id !== user?.id && isUserOnline(m.user_id)).length === 0 ? (
          <div className="flex items-center gap-2 px-2 py-1 mx-2 text-[#949ba4] text-sm">
            <Circle size={16} className="text-gray-500" />
            <span>No one else online</span>
          </div>
        ) : (
          teamMembers
            .filter(m => m.user_id !== user?.id && isUserOnline(m.user_id))
            .map((member) => {
              const displayName = member.display_name || member.username
              return (
                <button
                  key={member.user_id}
                  onClick={() => startDM(String(member.user_id))}
                  className="w-full flex items-center gap-2 px-2 py-1 mx-2 text-[#949ba4] text-sm hover:bg-[#35373c] rounded transition-colors text-left"
                  title="Click to start a DM"
                >
                  <div className="relative">
                    <div className="w-8 h-8 rounded-full bg-[#5865f2] flex items-center justify-center text-white text-xs font-medium">
                      {displayName ? displayName.charAt(0).toUpperCase() : '?'}
                    </div>
                    <Circle
                      size={10}
                      className="absolute -bottom-0.5 -right-0.5 fill-current text-green-500"
                    />
                  </div>
                  <span className="truncate">{displayName}</span>
                </button>
              )
            })
        )}

        {/* Admin Section - Only visible to system admins */}
        {isSystemAdmin && (
          <>
            <div className="px-2 mt-6 mb-2">
              <span className="text-xs font-semibold text-[#949ba4] uppercase tracking-wide px-2">
                Administration
              </span>
            </div>
            <Link
              to="/admin/forms"
              className={clsx(
                'flex items-center gap-2 px-2 py-1 mx-2 rounded text-[#949ba4] hover:text-[#dbdee1] hover:bg-[#35373c] transition-colors',
                location.pathname.startsWith('/admin/forms') && 'bg-[#35373c] text-white'
              )}
            >
              <FileText size={18} />
              <span>Form Builder</span>
            </Link>
            <Link
              to="/admin/ai"
              className={clsx(
                'flex items-center gap-2 px-2 py-1 mx-2 rounded text-[#949ba4] hover:text-[#dbdee1] hover:bg-[#35373c] transition-colors',
                location.pathname === '/admin/ai' && 'bg-[#35373c] text-white'
              )}
            >
              <Brain size={18} />
              <span>AI Insights</span>
            </Link>
          </>
        )}
      </div>

      {/* User area */}
      <div className="h-14 bg-[#232428] flex items-center px-2 gap-2">
        <div className="relative">
          <div className="w-8 h-8 rounded-full bg-[#5865f2] flex items-center justify-center text-white text-sm font-medium">
            {(() => { const name = user?.display_name ?? user?.username ?? ''; return name ? name.charAt(0) : 'U' })()}
          </div>
          <Circle
            size={10}
            className={clsx('absolute -bottom-0.5 -right-0.5 fill-current', isUserOnline(user?.id) ? 'text-green-500' : 'text-gray-500')}
          />
        </div>
        <div className="flex-1 min-w-0">
          <div className="text-sm font-medium text-white truncate">
            {user?.display_name || user?.username}
          </div>
          <div className="text-xs text-[#949ba4] truncate capitalize">{isUserOnline(user?.id) ? 'online' : 'offline'}</div>
        </div>
        <Link
          to="/settings"
          className="p-1 text-[#949ba4] hover:text-white transition-colors"
        >
          <Settings size={18} />
        </Link>
        <Link
          to="/profile"
          className="p-1 text-[#949ba4] hover:text-white transition-colors"
        >
          <User size={18} />
        </Link>
      </div>

      {/* New DM Modal */}
      <NewDMModal
        isOpen={showNewDMModal}
        onClose={() => setShowNewDMModal(false)}
        onDMCreated={(channelId) => {
          fetchDMChannels()
          navigateAndClose(`/channels/${channelId}`)
        }}
      />

      <CreateChannelModal
        isOpen={showCreateChannelModal}
        onClose={() => setShowCreateChannelModal(false)}
        onCreated={(channel) => {
          // Insert into channel list if not present
          setChannels((prev) => {
            if (prev.some((c) => c.id === channel.id)) return prev
            return [...prev, channel]
          })
          // Navigate to newly created channel
          navigateAndClose(`/channels/${channel.id}`)
        }}
      />
    </div>
  )
}
