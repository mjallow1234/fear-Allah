import { useState, useEffect } from 'react'
import { X, Search, MessageSquare } from 'lucide-react'
import api from '../services/api'
import { useAuthStore } from '../stores/authStore'

interface User {
  id: number
  username: string
  display_name: string | null
  email: string
}

interface NewDMModalProps {
  isOpen: boolean
  onClose: () => void
  onDMCreated: (channelId: number) => void
}

export default function NewDMModal({ isOpen, onClose, onDMCreated }: NewDMModalProps) {
  const [users, setUsers] = useState<User[]>([])
  const [searchQuery, setSearchQuery] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const [creating, setCreating] = useState<number | null>(null)
  const currentUser = useAuthStore((state) => state.user)

  useEffect(() => {
    if (isOpen) {
      fetchUsers()
    }
  }, [isOpen])

  const fetchUsers = async () => {
    setIsLoading(true)
    try {
      const response = await api.get('/api/users/')
      // Filter out current user
      setUsers(response.data.filter((u: User) => u.id !== currentUser?.id))
    } catch (error) {
      console.error('Failed to fetch users:', error)
    } finally {
      setIsLoading(false)
    }
  }

  const startDM = async (userId: number) => {
    setCreating(userId)
    try {
      const response = await api.post('/api/channels/direct', { user_id: userId })
      onDMCreated(response.data.id)
      onClose()
    } catch (error) {
      console.error('Failed to create DM:', error)
    } finally {
      setCreating(null)
    }
  }

  const filteredUsers = users.filter(
    (u) =>
      u.username.toLowerCase().includes(searchQuery.toLowerCase()) ||
      (u.display_name && u.display_name.toLowerCase().includes(searchQuery.toLowerCase()))
  )

  if (!isOpen) return null

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
      <div className="bg-[#313338] rounded-lg w-full max-w-md shadow-xl">
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b border-[#3f4147]">
          <h2 className="text-xl font-bold text-white">New Direct Message</h2>
          <button
            onClick={onClose}
            className="p-1 text-[#949ba4] hover:text-white transition-colors"
          >
            <X size={24} />
          </button>
        </div>

        {/* Search */}
        <div className="p-4">
          <div className="relative">
            <Search size={18} className="absolute left-3 top-1/2 -translate-y-1/2 text-[#949ba4]" />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search users..."
              className="w-full bg-[#1e1f22] text-white pl-10 pr-4 py-2 rounded border border-[#3f4147] focus:outline-none focus:border-[#5865f2]"
              autoFocus
            />
          </div>
        </div>

        {/* User list */}
        <div className="max-h-80 overflow-y-auto px-2 pb-4">
          {isLoading ? (
            <div className="text-center text-[#949ba4] py-8">Loading users...</div>
          ) : filteredUsers.length === 0 ? (
            <div className="text-center text-[#949ba4] py-8">
              {searchQuery ? 'No users found' : 'No other users available'}
            </div>
          ) : (
            filteredUsers.map((user) => (
              <button
                key={user.id}
                onClick={() => startDM(user.id)}
                disabled={creating === user.id}
                className="w-full flex items-center gap-3 px-3 py-2 rounded hover:bg-[#35373c] transition-colors text-left disabled:opacity-50"
              >
                <div className="w-10 h-10 rounded-full bg-[#5865f2] flex items-center justify-center text-white font-medium">
                  {(user.display_name || user.username).charAt(0).toUpperCase()}
                </div>
                <div className="flex-1 min-w-0">
                  <div className="text-white font-medium truncate">
                    {user.display_name || user.username}
                  </div>
                  <div className="text-[#949ba4] text-sm truncate">@{user.username}</div>
                </div>
                {creating === user.id ? (
                  <div className="text-[#949ba4] text-sm">Creating...</div>
                ) : (
                  <MessageSquare size={18} className="text-[#949ba4]" />
                )}
              </button>
            ))
          )}
        </div>
      </div>
    </div>
  )
}
