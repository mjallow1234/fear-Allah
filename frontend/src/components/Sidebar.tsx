import { useEffect, useState, useCallback } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import { Hash, Settings, User, MessageSquare, Circle, ChevronDown, Plus, FileText, Brain } from 'lucide-react'
import { useAuthStore } from '../stores/authStore'
import { usePresenceStore } from '../stores/presenceStore'
import { usePresence } from '../services/useWebSocket'
import api from '../services/api'
import clsx from 'clsx'
import NewDMModal from './NewDMModal'
import CreateChannelModal from './CreateChannelModal'
import { onSocketEvent } from '../realtime'


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
  // optional activity/unread fields (populated by server or realtime updates)
  last_activity_at?: string
  unread_count?: number
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

  // Fetch DM channels (use new direct-conversations API)
  const fetchDMChannels = useCallback(async () => {
    if (!token || !user) return
    try {
      const response = await api.get('/api/direct-conversations/')
      const convs = Array.isArray(response.data) ? response.data : []

      // Map conversations to DMChannel shape by resolving other participant info
      const dmData: DMChannel[] = await Promise.all(convs.map(async (conv: any) => {
        const otherId = conv.participant_ids.find((id: number) => id !== user.id)
        try {
          const r = await api.get(`/api/users/${otherId}`)
          const other = r.data
          return {
            id: conv.id,
            name: `dm-${conv.id}`,
            display_name: other.display_name || other.username,
            other_user_id: other.id,
            other_username: other.username
          }
        } catch (e) {
          return {
            id: conv.id,
            name: `dm-${conv.id}`,
            display_name: `DM ${conv.id}`,
            other_user_id: otherId,
            other_username: `user${otherId}`
          }
        }
      }))

      setDmChannels(dmData)
    } catch (error) {
      console.error('Failed to fetch DM channels:', error)
    }
  }, [token, user])

  // Start a DM with a user
  const startDM = async (userId: string) => {
    try {
      const response = await api.post('/api/direct-conversations/', { other_user_id: parseInt(userId) })
      const dmChannel = response.data
      // Refresh DM list and navigate to the direct conversation
      await fetchDMChannels()
      navigateAndClose(`/direct/${dmChannel.id}`)
    } catch (error) {
      console.error('Failed to start DM:', error)
    }
  }

  useEffect(() => {
    fetchTeams()
    fetchChannels()
    fetchDMChannels()
  }, [fetchChannels, fetchDMChannels, fetchTeams])

  // Real-time sidebar updates: listen for message:new and thread:reply to update channel activity/unread state
  useEffect(() => {
    const handleMessageNew = (msg: any) => {
      try {
        if (!msg || !msg.channel_id) return
        const incomingChannelId = Number(msg.channel_id)

        // If the incoming message is for the currently-open channel, ignore
        const path = location.pathname || ''
        const activeChannelId = path.startsWith('/channels/') ? Number(path.split('/')[2]) : null
        if (incomingChannelId === activeChannelId) return

        // Server now provides authoritative unread_count — refetch the channels list
        fetchChannels().catch((err) => console.error('Sidebar: failed to refetch channels after message:new', err))
      } catch (err) {
        console.error('Sidebar: failed to handle message:new', err)
      }
    }

    const handleThreadReply = (data: any) => {
      try {
        if (!data || !data.channel_id) return
        const incomingChannelId = Number(data.channel_id)

        // If user is viewing the channel, ignore
        const path = location.pathname || ''
        const activeChannelId = path.startsWith('/channels/') ? Number(path.split('/')[2]) : null
        if (incomingChannelId === activeChannelId) return

        // Server provides authoritative unread_count and last_activity — refetch channels
        fetchChannels().catch((err) => console.error('Sidebar: failed to refetch channels after thread:reply', err))
      } catch (err) {
        console.error('Sidebar: failed to handle thread:reply', err)
      }
    }

    const handleMarkRead = (data: any) => {
      try {
        // Server is authoritative for unread counts — refresh the channel list
        fetchChannels().catch((err) => console.error('Sidebar: failed to refetch channels after read update', err))
      } catch (err) {
        console.error('Sidebar: failed to handle receipt:update', err)
      }
    }

    const unsubMsg = onSocketEvent<any>('message:new', handleMessageNew)
    const unsubThread = onSocketEvent<any>('thread:reply', handleThreadReply)
    // Backend emits `receipt:update` (Socket.IO) for read receipts — listen and refetch channels.
    const unsubReceipt = onSocketEvent<any>('receipt:update', handleMarkRead)

    return () => {
      try { unsubMsg && unsubMsg() } catch (e) { /* ignore */ }
      try { unsubThread && unsubThread() } catch (e) { /* ignore */ }
      try { unsubReceipt && unsubReceipt() } catch (e) { /* ignore */ }
    }
  }, [location.pathname, user?.id, fetchChannels])

  // Register presence event handler so Sidebar can react to events like channel_created
  const presence = usePresence()
  useEffect(() => {
    if (!presence) return
    const unsub = presence.onEvent((data: any) => {
      if (!data) return

      // Channel created -> append to sidebar list
      if (data.type === 'channel_created') {
        const channel = data.channel
        if (!channel) return
        setChannels((prev) => {
          if (prev.some((c) => c.id === channel.id)) return prev
          if (selectedTeam && channel.team_id !== selectedTeam.id) return prev
          return [...prev, channel]
        })
        return
      }

      // Unread update (per-user) -> server is authoritative for unread_count; refetch
      if (data.type === 'unread_update') {
        try {
          fetchChannels().catch((err) => console.error('Sidebar: failed to refetch channels after unread_update', err))
        } catch (err) {
          console.error('Sidebar: failed to handle unread_update', err)
        }
        return
      }
    })
    return () => { unsub && unsub() }
  }, [presence, selectedTeam, fetchChannels])

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

  // Listen for imperative refetch requests (e.g. mark-read completed)
  useEffect(() => {
    const handler = (ev: any) => {
      try {
        fetchChannels().catch((err) => console.error('Sidebar: channels:refetch handler failed', err))
      } catch (err) {
        console.error('Sidebar: channels:refetch handler failed', err)
      }
    }
    window.addEventListener('channels:refetch', handler)
    return () => { window.removeEventListener('channels:refetch', handler) }
  }, [fetchChannels])

  const handleSelectTeam = (team: Team) => {
    setSelectedTeam(team)
    setShowTeamMenu(false)
  }

  return (
    <div className={`sidebar w-60 h-full flex-shrink-0 flex flex-col overflow-hidden md:relative md:transform-none ${isOpen ? 'open' : ''}`} style={{ backgroundColor: 'var(--sidebar-bg)' }}>
      {/* Team selector */}
      <div className="relative">
        <button
          onClick={() => setShowTeamMenu(!showTeamMenu)}
          className="w-full h-12 flex items-center justify-between px-4 shadow-sm transition-colors"
          style={{ borderBottom: '1px solid var(--sidebar-border)', backgroundColor: 'transparent' }}
          onMouseEnter={(e) => e.currentTarget.style.backgroundColor = 'var(--sidebar-hover)'}
          onMouseLeave={(e) => e.currentTarget.style.backgroundColor = 'transparent'}
        >
          <div className="flex items-center gap-2">
            <div className="w-6 h-6 rounded flex items-center justify-center text-white text-xs font-bold" style={{ backgroundColor: 'var(--accent)' }}>
              {(() => {
                const name = selectedTeam?.display_name ?? selectedTeam?.name ?? ''
                return name ? name.charAt(0) : 'T'
              })()}
            </div>
            <span className="font-bold truncate" style={{ color: 'var(--text-primary)' }}>
              {selectedTeam?.display_name || selectedTeam?.name || 'Select Team'}
            </span>
          </div>
          <ChevronDown size={18} className={clsx('transition-transform', showTeamMenu && 'rotate-180')} style={{ color: 'var(--text-secondary)' }} />
        </button>

        {/* Team dropdown */}
        {showTeamMenu && (
          <div className="absolute top-12 left-0 right-0 rounded-b shadow-lg z-50 max-h-64 overflow-y-auto" style={{ backgroundColor: 'var(--dropdown-bg)', border: '1px solid var(--sidebar-border)' }}>
            {Array.isArray(teams) && teams.map((team) => (
              <button
                key={team.id}
                onClick={() => handleSelectTeam(team)}
                className={clsx(
                  'w-full flex items-center gap-2 px-4 py-2 transition-colors text-left',
                  selectedTeam?.id === team.id && 'bg-[var(--sidebar-hover)]'
                )}
                style={{ backgroundColor: selectedTeam?.id === team.id ? 'var(--sidebar-hover)' : 'transparent' }}
                onMouseEnter={(e) => e.currentTarget.style.backgroundColor = 'var(--sidebar-hover)'}
                onMouseLeave={(e) => e.currentTarget.style.backgroundColor = selectedTeam?.id === team.id ? 'var(--sidebar-hover)' : 'transparent'}
              >
                <div className="w-6 h-6 rounded flex items-center justify-center text-white text-xs font-bold" style={{ backgroundColor: 'var(--accent)' }}>
                  {(() => { const name = team.display_name ?? team.name ?? ''; return name ? name.charAt(0) : 'T' })()}
                </div>
                <div className="flex-1 min-w-0">
                  <div className="text-sm font-medium truncate" style={{ color: 'var(--text-primary)' }}>{team.display_name || team.name}</div>
                  {team.description && (
                    <div className="text-xs truncate" style={{ color: 'var(--text-secondary)' }}>{team.description}</div>
                  )}
                </div>
                {selectedTeam?.id === team.id && (
                  <div className="w-2 h-2 rounded-full bg-green-500" />
                )}
              </button>
            ))}
            {teams.length === 0 && (
              <div className="px-4 py-3 text-sm" style={{ color: 'var(--text-secondary)' }}>
                No teams available
              </div>
            )}
          </div>
        )}
      </div>

      {/* Channels */}
      <div className="flex-1 overflow-y-auto py-4">
        <div className="px-2 mb-2 flex items-center justify-between">
          <span className="text-xs font-semibold uppercase tracking-wide px-2" style={{ color: 'var(--text-secondary)' }}>
            Channels
          </span>
          <button 
            onClick={() => setShowCreateChannelModal(true)}
            className={clsx('p-1 transition-colors', isSystemAdmin ? 'hover:opacity-100' : 'opacity-50 cursor-not-allowed')}
            style={{ color: 'var(--text-secondary)' }}
            title={isSystemAdmin ? 'Add Channel' : 'Only admins can create channels'}
            disabled={!isSystemAdmin}
          >
            <Plus size={14} />
          </button>
        </div>
        {channels.length === 0 ? (
          <div className="flex items-center" style={{ color: 'var(--text-secondary)', padding: 'var(--sidebar-item-padding)' }}>
            <Hash size={16} />
            <span>No channels yet</span>
          </div>
        ) : (
          Array.isArray(channels) && channels.map((channel) => (
            <Link
              key={channel.id}
              to={`/channels/${channel.id}`}
              className={clsx(
                'flex items-center sidebar-item rounded transition-colors',
                location.pathname === `/channels/${channel.id}` && 'font-medium'
              )}
              style={{
                color: location.pathname === `/channels/${channel.id}` ? 'var(--text-primary)' : 'var(--text-secondary)',
                backgroundColor: location.pathname === `/channels/${channel.id}` ? 'var(--sidebar-active)' : 'transparent'
              }}
              onMouseEnter={(e) => {
                if (location.pathname !== `/channels/${channel.id}`) {
                  e.currentTarget.style.backgroundColor = 'var(--sidebar-hover)'
                  e.currentTarget.style.color = 'var(--text-primary)'
                }
              }}
              onMouseLeave={(e) => {
                if (location.pathname !== `/channels/${channel.id}`) {
                  e.currentTarget.style.backgroundColor = 'transparent'
                  e.currentTarget.style.color = 'var(--text-secondary)'
                }
              }}
            >
              <Hash size={18} />
              <span>{channel.display_name || channel.name}</span>
              {channel.unread_count && channel.unread_count > 0 && (
                <span data-testid={`channel-unread-${channel.id}`} className="ml-2 rounded-full bg-red-500 text-white text-xs px-2 py-0.5">
                  {channel.unread_count}
                </span>
              )}
            </Link>
          ))
        )}

        {/* Direct Messages */}
        <div className="px-2 mt-6 mb-2 flex items-center justify-between">
          <span className="text-xs font-semibold uppercase tracking-wide px-2" style={{ color: 'var(--text-secondary)' }}>
            Direct Messages
          </span>
          <button 
            onClick={() => setShowNewDMModal(true)}
            className="p-1 transition-colors hover:opacity-100"
            style={{ color: 'var(--text-secondary)' }}
            title="New Direct Message"
          >
            <Plus size={14} />
          </button>
        </div>
        {dmChannels.length === 0 ? (
          <div className="flex items-center gap-2 px-2 py-1 mx-2 text-sm" style={{ color: 'var(--text-secondary)' }}>
            <MessageSquare size={16} />
            <span>No DMs yet</span>
          </div>
        ) : (
          Array.isArray(dmChannels) && dmChannels.map((dm) => (
            <Link
              key={dm.id}
              to={`/direct/${dm.id}`}
              className={clsx(
                'flex items-center sidebar-item rounded transition-colors',
                location.pathname === `/direct/${dm.id}` && 'font-medium'
              )}
              style={{
                color: location.pathname === `/direct/${dm.id}` ? 'var(--text-primary)' : 'var(--text-secondary)',
                backgroundColor: location.pathname === `/direct/${dm.id}` ? 'var(--sidebar-active)' : 'transparent'
              }}
              onMouseEnter={(e) => {
                if (location.pathname !== `/direct/${dm.id}`) {
                  e.currentTarget.style.backgroundColor = 'var(--sidebar-hover)'
                  e.currentTarget.style.color = 'var(--text-primary)'
                }
              }}
              onMouseLeave={(e) => {
                if (location.pathname !== `/direct/${dm.id}`) {
                  e.currentTarget.style.backgroundColor = 'transparent'
                  e.currentTarget.style.color = 'var(--text-secondary)'
                }
              }}
            >
              <div className="relative">
                <div className="w-6 h-6 rounded-full flex items-center justify-center text-white text-xs font-medium" style={{ backgroundColor: 'var(--accent)' }}>
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
          <span className="text-xs font-semibold uppercase tracking-wide px-2" style={{ color: 'var(--text-secondary)' }}>
            Online — {teamMembers.filter(m => m.user_id !== user?.id && isUserOnline(m.user_id)).length}
          </span>
        </div>
        {teamMembers.filter(m => m.user_id !== user?.id && isUserOnline(m.user_id)).length === 0 ? (
          <div className="flex items-center gap-2 px-2 py-1 mx-2 text-sm" style={{ color: 'var(--text-secondary)' }}>
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
                  className="w-full flex items-center sidebar-item text-sm rounded transition-colors text-left"
                  style={{ color: 'var(--text-secondary)' }}
                  onMouseEnter={(e) => e.currentTarget.style.backgroundColor = 'var(--sidebar-hover)'}
                  onMouseLeave={(e) => e.currentTarget.style.backgroundColor = 'transparent'}
                  title="Click to start a DM"
                >
                  <div className="relative">
                    <div className="w-8 h-8 rounded-full flex items-center justify-center text-white text-xs font-medium" style={{ backgroundColor: 'var(--accent)' }}>
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
              <span className="text-xs font-semibold uppercase tracking-wide px-2" style={{ color: 'var(--text-secondary)' }}>
                Administration
              </span>
            </div>
            <Link
              to="/admin/forms"
              className={clsx(
                'flex items-center sidebar-item rounded transition-colors',
                location.pathname.startsWith('/admin/forms') && 'font-medium'
              )}
              style={{
                color: location.pathname.startsWith('/admin/forms') ? 'var(--text-primary)' : 'var(--text-secondary)',
                backgroundColor: location.pathname.startsWith('/admin/forms') ? 'var(--sidebar-active)' : 'transparent'
              }}
              onMouseEnter={(e) => {
                if (!location.pathname.startsWith('/admin/forms')) {
                  e.currentTarget.style.backgroundColor = 'var(--sidebar-hover)'
                  e.currentTarget.style.color = 'var(--text-primary)'
                }
              }}
              onMouseLeave={(e) => {
                if (!location.pathname.startsWith('/admin/forms')) {
                  e.currentTarget.style.backgroundColor = 'transparent'
                  e.currentTarget.style.color = 'var(--text-secondary)'
                }
              }}
            >
              <FileText size={18} />
              <span>Form Builder</span>
            </Link>
            <Link
              to="/admin/ai"
              className={clsx(
                'flex items-center gap-2 px-2 py-1 mx-2 rounded transition-colors',
                location.pathname === '/admin/ai' && 'font-medium'
              )}
              style={{
                color: location.pathname === '/admin/ai' ? 'var(--text-primary)' : 'var(--text-secondary)',
                backgroundColor: location.pathname === '/admin/ai' ? 'var(--sidebar-active)' : 'transparent'
              }}
              onMouseEnter={(e) => {
                if (location.pathname !== '/admin/ai') {
                  e.currentTarget.style.backgroundColor = 'var(--sidebar-hover)'
                  e.currentTarget.style.color = 'var(--text-primary)'
                }
              }}
              onMouseLeave={(e) => {
                if (location.pathname !== '/admin/ai') {
                  e.currentTarget.style.backgroundColor = 'transparent'
                  e.currentTarget.style.color = 'var(--text-secondary)'
                }
              }}
            >
              <Brain size={18} />
              <span>AI Insights</span>
            </Link>
          </>
        )}
      </div>

      {/* User area */}
      <div className="h-14 flex items-center px-2 gap-2" style={{ backgroundColor: 'var(--sidebar-user-bg)' }}>
        <div className="relative">
          <div className="w-8 h-8 rounded-full flex items-center justify-center text-white text-sm font-medium" style={{ backgroundColor: 'var(--accent)' }}>
            {(() => { const name = user?.display_name ?? user?.username ?? ''; return name ? name.charAt(0) : 'U' })()}
          </div>
          <Circle
            size={10}
            className={clsx('absolute -bottom-0.5 -right-0.5 fill-current', isUserOnline(user?.id) ? 'text-green-500' : 'text-gray-500')}
          />
        </div>
        <div className="flex-1 min-w-0">
          <div className="text-sm font-medium truncate" style={{ color: 'var(--text-primary)' }}>
            {user?.display_name || user?.username}
          </div>
          <div className="text-xs truncate capitalize" style={{ color: 'var(--text-secondary)' }}>{isUserOnline(user?.id) ? 'online' : 'offline'}</div>
        </div>
        <Link
          to="/settings"
          className="p-1 transition-colors"
          style={{ color: 'var(--text-secondary)' }}
        >
          <Settings size={18} />
        </Link>
        <Link
          to="/profile"
          className="p-1 transition-colors"
          style={{ color: 'var(--text-secondary)' }}
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
          navigateAndClose(`/direct/${channelId}`)
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
