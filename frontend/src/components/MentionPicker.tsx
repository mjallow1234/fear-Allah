import { useState, useEffect, useRef, useCallback } from 'react'
import api from '../services/api'

interface User {
  id: number
  username: string
  display_name: string | null
  avatar_url: string | null
  status: string
}

interface MentionPickerProps {
  isOpen: boolean
  searchQuery: string
  position: { top: number; left: number }
  onSelect: (username: string) => void
  onClose: () => void
}

export default function MentionPicker({ 
  isOpen, 
  searchQuery, 
  position, 
  onSelect, 
  onClose 
}: MentionPickerProps) {
  const [users, setUsers] = useState<User[]>([])
  const [filteredUsers, setFilteredUsers] = useState<User[]>([])
  const [selectedIndex, setSelectedIndex] = useState(0)
  const [isLoading, setIsLoading] = useState(false)
  const containerRef = useRef<HTMLDivElement>(null)

  // Fetch users on mount
  useEffect(() => {
    const fetchUsers = async () => {
      setIsLoading(true)
      try {
        const response = await api.get('/api/users/')
        setUsers(response.data)
      } catch (error) {
        console.error('Failed to fetch users:', error)
      } finally {
        setIsLoading(false)
      }
    }
    fetchUsers()
  }, [])

  // Filter users based on search query
  useEffect(() => {
    if (!searchQuery) {
      setFilteredUsers(users.slice(0, 10))
    } else {
      const query = searchQuery.toLowerCase()
      const filtered = users.filter(user => 
        user.username.toLowerCase().includes(query) ||
        (user.display_name?.toLowerCase().includes(query))
      ).slice(0, 10)
      setFilteredUsers(filtered)
    }
    setSelectedIndex(0)
  }, [searchQuery, users])

  // Handle keyboard navigation
  const handleKeyDown = useCallback((e: KeyboardEvent) => {
    if (!isOpen) return

    switch (e.key) {
      case 'ArrowDown':
        e.preventDefault()
        setSelectedIndex(prev => 
          prev < filteredUsers.length - 1 ? prev + 1 : 0
        )
        break
      case 'ArrowUp':
        e.preventDefault()
        setSelectedIndex(prev => 
          prev > 0 ? prev - 1 : filteredUsers.length - 1
        )
        break
      case 'Enter':
      case 'Tab':
        e.preventDefault()
        if (filteredUsers[selectedIndex]) {
          onSelect(filteredUsers[selectedIndex].username)
        }
        break
      case 'Escape':
        e.preventDefault()
        onClose()
        break
    }
  }, [isOpen, filteredUsers, selectedIndex, onSelect, onClose])

  useEffect(() => {
    document.addEventListener('keydown', handleKeyDown)
    return () => document.removeEventListener('keydown', handleKeyDown)
  }, [handleKeyDown])

  // Scroll selected item into view
  useEffect(() => {
    if (containerRef.current && filteredUsers.length > 0) {
      const selectedElement = containerRef.current.children[selectedIndex] as HTMLElement
      if (selectedElement) {
        selectedElement.scrollIntoView({ block: 'nearest' })
      }
    }
  }, [selectedIndex, filteredUsers.length])

  if (!isOpen) return null

  // Get status color
  const getStatusColor = (status: string) => {
    switch (status) {
      case 'online': return 'bg-green-500'
      case 'away': return 'bg-yellow-500'
      case 'dnd': return 'bg-red-500'
      default: return 'bg-gray-500'
    }
  }

  return (
    <div
      className="absolute z-50 bg-[#2b2d31] border border-[#1e1f22] rounded-lg shadow-xl overflow-hidden"
      style={{
        bottom: position.top,
        left: position.left,
        minWidth: '250px',
        maxWidth: '350px',
        maxHeight: '300px',
      }}
    >
      {/* Header */}
      <div className="px-3 py-2 border-b border-[#1e1f22] text-xs font-semibold text-[#949ba4] uppercase">
        Users matching @{searchQuery || '...'}
      </div>

      {/* User list */}
      <div ref={containerRef} className="overflow-y-auto max-h-[250px]">
        {isLoading ? (
          <div className="px-3 py-4 text-center text-[#949ba4]">
            <div className="w-5 h-5 border-2 border-blue-500 border-t-transparent rounded-full animate-spin mx-auto" />
          </div>
        ) : filteredUsers.length === 0 ? (
          <div className="px-3 py-4 text-center text-[#949ba4] text-sm">
            No users found
          </div>
        ) : (
          filteredUsers.map((user, index) => (
            <button
              key={user.id}
              onClick={() => onSelect(user.username)}
              onMouseEnter={() => setSelectedIndex(index)}
              className={`w-full px-3 py-2 flex items-center gap-3 text-left transition-colors ${
                index === selectedIndex 
                  ? 'bg-[#5865f2] text-white' 
                  : 'hover:bg-[#35373c] text-[#dcddde]'
              }`}
            >
              {/* Avatar */}
              <div className="relative flex-shrink-0">
                {user.avatar_url ? (
                  <img
                    src={user.avatar_url}
                    alt={user.username}
                    className="w-8 h-8 rounded-full"
                  />
                ) : (
                  <div className="w-8 h-8 rounded-full bg-[#5865f2] flex items-center justify-center text-white text-sm font-medium">
                    {user.username[0].toUpperCase()}
                  </div>
                )}
                {/* Status indicator */}
                <div className={`absolute -bottom-0.5 -right-0.5 w-3 h-3 rounded-full border-2 border-[#2b2d31] ${getStatusColor(user.status)}`} />
              </div>

              {/* User info */}
              <div className="flex-1 min-w-0">
                <div className="font-medium truncate">
                  {user.display_name || user.username}
                </div>
                <div className={`text-xs truncate ${
                  index === selectedIndex ? 'text-white/70' : 'text-[#949ba4]'
                }`}>
                  @{user.username}
                </div>
              </div>
            </button>
          ))
        )}
      </div>

      {/* Footer hint */}
      <div className="px-3 py-1.5 border-t border-[#1e1f22] text-xs text-[#949ba4] flex items-center gap-2">
        <span className="bg-[#1e1f22] px-1.5 py-0.5 rounded text-[10px]">↑↓</span>
        <span>to navigate</span>
        <span className="bg-[#1e1f22] px-1.5 py-0.5 rounded text-[10px]">Tab</span>
        <span>to select</span>
        <span className="bg-[#1e1f22] px-1.5 py-0.5 rounded text-[10px]">Esc</span>
        <span>to close</span>
      </div>
    </div>
  )
}
