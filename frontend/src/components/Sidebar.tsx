import { useEffect, useState, useRef, useCallback } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import { Hash, Settings, User, MessageSquare, Circle, ChevronDown, Plus } from 'lucide-react'
import { useAuthStore } from '../stores/authStore'
import api from '../services/api'
import clsx from 'clsx'
import NewDMModal from './NewDMModal'
import { pushNotification } from './NotificationBell'

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

interface OnlineUser {
  user_id: string
  username: string
  status: 'online' | 'away' | 'offline'
}

interface DMChannel {
  id: number
  name: string
  display_name: string
  other_user_id: number
  other_username: string
}

export default function Sidebar() {
  const location = useLocation()
  const navigate = useNavigate()
  const user = useAuthStore((state) => state.user)
  const token = useAuthStore((state) => state.token)
  const [teams, setTeams] = useState<Team[]>([])
  const [selectedTeam, setSelectedTeam] = useState<Team | null>(null)
  const [channels, setChannels] = useState<Channel[]>([])
  const [showTeamMenu, setShowTeamMenu] = useState(false)
  const [onlineUsers, setOnlineUsers] = useState<OnlineUser[]>([])
  const [dmChannels, setDmChannels] = useState<DMChannel[]>([])
  const [myStatus, setMyStatus] = useState<'online' | 'away' | 'offline'>('offline')
  const [showNewDMModal, setShowNewDMModal] = useState(false)
  const wsRef = useRef<WebSocket | null>(null)
  const reconnectTimeoutRef = useRef<ReturnType<typeof setTimeout>>()

  // Fetch teams
  const fetchTeams = useCallback(async () => {
    if (!token) return
    try {
      const response = await api.get('/api/teams/')
      const teamsData = response.data
      setTeams(teamsData)
      // Auto-select first team if none selected
      if (teamsData.length > 0 && !selectedTeam) {
        setSelectedTeam(teamsData[0])
      }
    } catch (error) {
      console.error('Failed to fetch teams:', error)
    }
  }, [token, selectedTeam])

  // Fetch channels for selected team
  const fetchChannels = useCallback(async () => {
    if (!token || !selectedTeam) return
    try {
      const response = await api.get(`/api/channels/?team_id=${selectedTeam.id}`)
      setChannels(response.data)
    } catch (error) {
      console.error('Failed to fetch channels:', error)
    }
  }, [token, selectedTeam])

  const connectPresence = useCallback(() => {
    if (!token || wsRef.current?.readyState === WebSocket.OPEN) return

    const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const wsHost = window.location.host
    const ws = new WebSocket(`${wsProtocol}//${wsHost}/ws/presence?token=${token}`)

    ws.onopen = () => {
      setMyStatus('online')
    }

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data)
        if (data.type === 'presence_list') {
          // Deduplicate users by user_id
          const users = data.users || []
          const uniqueUsers = Array.from(
            new Map(users.map((u: OnlineUser) => [u.user_id, u])).values()
          ) as OnlineUser[]
          setOnlineUsers(uniqueUsers)
        } else if (data.type === 'presence_update') {
          setOnlineUsers((prev) => {
            const existing = prev.find((u) => u.user_id === data.user_id)
            if (data.status === 'offline') {
              return prev.filter((u) => u.user_id !== data.user_id)
            }
            if (existing) {
              return prev.map((u) =>
                u.user_id === data.user_id ? { ...u, status: data.status } : u
              )
            }
            // Add new user (already not in list)
            return [...prev, { user_id: data.user_id, username: data.username, status: data.status }]
          })
        } else if (data.type === 'notification') {
          // Handle real-time notification
          pushNotification({
            id: data.notification_id,
            type: data.notification_type,
            title: data.title,
            content: data.content,
            channel_id: data.channel_id,
            message_id: data.message_id,
            sender_id: data.sender_id,
            sender_username: data.sender_username,
            is_read: false,
            created_at: data.created_at || new Date().toISOString()
          })
        }
      } catch (err) {
        console.error('Presence parse error:', err)
      }
    }

    ws.onclose = () => {
      setMyStatus('offline')
      reconnectTimeoutRef.current = setTimeout(connectPresence, 3000)
    }

    ws.onerror = () => {
      ws.close()
    }

    wsRef.current = ws
  }, [token])

  // Fetch DM channels
  const fetchDMChannels = useCallback(async () => {
    if (!token) return
    try {
      const response = await api.get('/api/channels/direct/list')
      setDmChannels(response.data)
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
      navigate(`/channels/${dmChannel.id}`)
    } catch (error) {
      console.error('Failed to start DM:', error)
    }
  }

  useEffect(() => {
    fetchTeams()
    connectPresence()
    fetchDMChannels()
    return () => {
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current)
      }
      wsRef.current?.close()
    }
  }, [connectPresence, fetchDMChannels, fetchTeams])

  // Fetch channels when team changes
  useEffect(() => {
    if (selectedTeam) {
      fetchChannels()
    }
  }, [selectedTeam, fetchChannels])

  const handleSelectTeam = (team: Team) => {
    setSelectedTeam(team)
    setShowTeamMenu(false)
  }

  const getStatusColor = (status: 'online' | 'away' | 'offline') => {
    switch (status) {
      case 'online':
        return 'text-green-500'
      case 'away':
        return 'text-yellow-500'
      default:
        return 'text-gray-500'
    }
  }

  return (
    <div className="w-60 bg-[#2b2d31] flex flex-col">
      {/* Team selector */}
      <div className="relative">
        <button
          onClick={() => setShowTeamMenu(!showTeamMenu)}
          className="w-full h-12 flex items-center justify-between px-4 border-b border-[#1f2023] shadow-sm hover:bg-[#35373c] transition-colors"
        >
          <div className="flex items-center gap-2">
            <div className="w-6 h-6 rounded bg-[#5865f2] flex items-center justify-center text-white text-xs font-bold">
              {selectedTeam?.display_name?.charAt(0) || selectedTeam?.name?.charAt(0) || 'T'}
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
            {teams.map((team) => (
              <button
                key={team.id}
                onClick={() => handleSelectTeam(team)}
                className={clsx(
                  'w-full flex items-center gap-2 px-4 py-2 hover:bg-[#35373c] transition-colors text-left',
                  selectedTeam?.id === team.id && 'bg-[#35373c]'
                )}
              >
                <div className="w-6 h-6 rounded bg-[#5865f2] flex items-center justify-center text-white text-xs font-bold">
                  {team.display_name?.charAt(0) || team.name.charAt(0)}
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
            className="p-1 text-[#949ba4] hover:text-white transition-colors"
            title="Add Channel"
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
          channels.map((channel) => (
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
          dmChannels.map((dm) => (
            <Link
              key={dm.id}
              to={`/channels/${dm.id}`}
              className={clsx(
                'flex items-center gap-2 px-2 py-1 mx-2 rounded text-[#949ba4] hover:text-[#dbdee1] hover:bg-[#35373c] transition-colors',
                location.pathname === `/channels/${dm.id}` &&
                  'bg-[#35373c] text-white'
              )}
            >
              <div className="w-6 h-6 rounded-full bg-[#5865f2] flex items-center justify-center text-white text-xs font-medium">
                {dm.other_username.charAt(0).toUpperCase()}
              </div>
              <span className="truncate">{dm.display_name}</span>
            </Link>
          ))
        )}

        {/* Online Users */}
        <div className="px-2 mt-6 mb-2">
          <span className="text-xs font-semibold text-[#949ba4] uppercase tracking-wide px-2">
            Online — {onlineUsers.filter(u => u.user_id !== String(user?.id)).length}
          </span>
        </div>
        {onlineUsers.filter(u => u.user_id !== String(user?.id)).length === 0 ? (
          <div className="flex items-center gap-2 px-2 py-1 mx-2 text-[#949ba4] text-sm">
            <MessageSquare size={16} />
            <span>No one online</span>
          </div>
        ) : (
          onlineUsers
            .filter(u => u.user_id !== String(user?.id))
            .map((onlineUser) => (
            <button
              key={onlineUser.user_id}
              onClick={() => startDM(onlineUser.user_id)}
              className="w-full flex items-center gap-2 px-2 py-1 mx-2 text-[#949ba4] text-sm hover:bg-[#35373c] rounded transition-colors text-left"
              title="Click to start a DM"
            >
              <div className="relative">
                <div className="w-8 h-8 rounded-full bg-[#5865f2] flex items-center justify-center text-white text-xs font-medium">
                  {onlineUser.username.charAt(0).toUpperCase()}
                </div>
                <Circle
                  size={10}
                  className={clsx('absolute -bottom-0.5 -right-0.5 fill-current', getStatusColor(onlineUser.status))}
                />
              </div>
              <span className="truncate">{onlineUser.username}</span>
            </button>
          ))
        )}
      </div>

      {/* User area */}
      <div className="h-14 bg-[#232428] flex items-center px-2 gap-2">
        <div className="relative">
          <div className="w-8 h-8 rounded-full bg-[#5865f2] flex items-center justify-center text-white text-sm font-medium">
            {user?.display_name?.charAt(0) || user?.username?.charAt(0) || 'U'}
          </div>
          <Circle
            size={10}
            className={clsx('absolute -bottom-0.5 -right-0.5 fill-current', getStatusColor(myStatus))}
          />
        </div>
        <div className="flex-1 min-w-0">
          <div className="text-sm font-medium text-white truncate">
            {user?.display_name || user?.username}
          </div>
          <div className="text-xs text-[#949ba4] truncate capitalize">{myStatus}</div>
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
          navigate(`/channels/${channelId}`)
        }}
      />
    </div>
  )
}
