import { useState, useEffect, useCallback } from 'react'
import { X, UserPlus, UserMinus, Shield, Users } from 'lucide-react'
import api from '../services/api'

interface ChannelMember {
  id: number
  user_id: number
  channel_id: number
  username: string
  display_name: string | null
  role: string
}

interface User {
  id: number
  username: string
  display_name: string | null
}

interface ChannelSettingsProps {
  isOpen: boolean
  onClose: () => void
  channelId: number
  channelName: string
}

export default function ChannelSettings({ isOpen, onClose, channelId, channelName }: ChannelSettingsProps) {
  const [members, setMembers] = useState<ChannelMember[]>([])
  const [loading, setLoading] = useState(false)
  const [showAddUser, setShowAddUser] = useState(false)
  const [allUsers, setAllUsers] = useState<User[]>([])
  const [searchQuery, setSearchQuery] = useState('')

  const fetchMembers = useCallback(async () => {
    if (!channelId) return
    setLoading(true)
    try {
      const response = await api.get(`/api/channels/${channelId}/members`)
      setMembers(response.data)
    } catch (error) {
      console.error('Failed to fetch members:', error)
    } finally {
      setLoading(false)
    }
  }, [channelId])

  const fetchAllUsers = useCallback(async () => {
    try {
      const response = await api.get('/api/users/')
      setAllUsers(response.data)
    } catch (error) {
      console.error('Failed to fetch users:', error)
    }
  }, [])

  useEffect(() => {
    if (isOpen) {
      fetchMembers()
      fetchAllUsers()
    }
  }, [isOpen, fetchMembers, fetchAllUsers])

  const handleAddMember = async (userId: number) => {
    try {
      await api.post(`/api/channels/${channelId}/members`, { user_id: userId })
      await fetchMembers()
      setShowAddUser(false)
      setSearchQuery('')
    } catch (error: any) {
      console.error('Failed to add member:', error)
      alert(error.response?.data?.detail || 'Failed to add member')
    }
  }

  const handleRemoveMember = async (userId: number) => {
    if (!confirm('Are you sure you want to remove this member?')) return
    try {
      await api.delete(`/api/channels/${channelId}/members/${userId}`)
      await fetchMembers()
    } catch (error: any) {
      console.error('Failed to remove member:', error)
      alert(error.response?.data?.detail || 'Failed to remove member')
    }
  }

  const nonMembers = allUsers.filter(
    u => !members.some(m => m.user_id === u.id) &&
    (searchQuery === '' || 
     u.username.toLowerCase().includes(searchQuery.toLowerCase()) ||
     (u.display_name?.toLowerCase() || '').includes(searchQuery.toLowerCase()))
  )

  if (!isOpen) return null

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
      <div className="bg-[#313338] rounded-lg shadow-xl w-full max-w-lg max-h-[80vh] flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b border-[#1f2023]">
          <div className="flex items-center gap-2">
            <Users size={20} className="text-[#949ba4]" />
            <h2 className="text-lg font-semibold text-white">#{channelName} Settings</h2>
          </div>
          <button
            onClick={onClose}
            className="p-1 text-[#949ba4] hover:text-white transition-colors"
          >
            <X size={20} />
          </button>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto p-4">
          {/* Members Section */}
          <div className="mb-4">
            <div className="flex items-center justify-between mb-3">
              <h3 className="text-sm font-semibold text-[#949ba4] uppercase">
                Members ({members.length})
              </h3>
              <button
                onClick={() => setShowAddUser(!showAddUser)}
                className="flex items-center gap-1 px-2 py-1 text-sm text-[#00a8fc] hover:bg-[#00a8fc]/10 rounded transition-colors"
              >
                <UserPlus size={16} />
                Add Member
              </button>
            </div>

            {/* Add User Panel */}
            {showAddUser && (
              <div className="mb-4 p-3 bg-[#2b2d31] rounded-lg">
                <input
                  type="text"
                  placeholder="Search users..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="w-full px-3 py-2 bg-[#1e1f22] border border-[#1f2023] rounded text-white placeholder-[#949ba4] text-sm mb-2"
                />
                <div className="max-h-32 overflow-y-auto">
                  {nonMembers.length === 0 ? (
                    <p className="text-sm text-[#949ba4] text-center py-2">
                      {searchQuery ? 'No matching users' : 'All users are members'}
                    </p>
                  ) : (
                    nonMembers.slice(0, 10).map(user => (
                      <button
                        key={user.id}
                        onClick={() => handleAddMember(user.id)}
                        className="w-full flex items-center gap-2 px-2 py-1.5 hover:bg-[#35373c] rounded transition-colors text-left"
                      >
                        <div className="w-6 h-6 rounded-full bg-[#5865f2] flex items-center justify-center text-white text-xs">
                          {(user.display_name || user.username).charAt(0).toUpperCase()}
                        </div>
                        <div className="flex-1 min-w-0">
                          <span className="text-white text-sm">{user.display_name || user.username}</span>
                          <span className="text-[#949ba4] text-xs ml-1">@{user.username}</span>
                        </div>
                        <UserPlus size={14} className="text-[#00a8fc]" />
                      </button>
                    ))
                  )}
                </div>
              </div>
            )}

            {/* Members List */}
            {loading ? (
              <p className="text-[#949ba4] text-center py-4">Loading...</p>
            ) : members.length === 0 ? (
              <p className="text-[#949ba4] text-center py-4">No members</p>
            ) : (
              <div className="space-y-1">
                {members.map(member => (
                  <div
                    key={member.id}
                    className="flex items-center gap-3 px-3 py-2 bg-[#2b2d31] rounded-lg"
                  >
                    <div className="w-8 h-8 rounded-full bg-[#5865f2] flex items-center justify-center text-white text-sm">
                      {(member.display_name || member.username).charAt(0).toUpperCase()}
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2">
                        <span className="text-white font-medium truncate">
                          {member.display_name || member.username}
                        </span>
                        {member.role === 'admin' && (
                          <span className="flex items-center gap-1 px-1.5 py-0.5 bg-[#5865f2]/20 text-[#5865f2] text-xs rounded">
                            <Shield size={10} />
                            Admin
                          </span>
                        )}
                      </div>
                      <span className="text-[#949ba4] text-xs">@{member.username}</span>
                    </div>
                    <button
                      onClick={() => handleRemoveMember(member.user_id)}
                      className="p-1.5 text-[#949ba4] hover:text-red-500 hover:bg-red-500/10 rounded transition-colors"
                      title="Remove member"
                    >
                      <UserMinus size={16} />
                    </button>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
