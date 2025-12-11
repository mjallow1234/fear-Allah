import { useState, useEffect, useRef } from 'react'
import { Search, X, Hash, User, Calendar } from 'lucide-react'
import api from '../services/api'

interface SearchResult {
  id: number
  content: string
  channel_id: number
  channel_name: string | null
  author_id: number
  author_username: string | null
  created_at: string
  highlight: string | null
}

interface SearchModalProps {
  isOpen: boolean
  onClose: () => void
  onResultClick: (channelId: number, messageId: number) => void
}

export default function SearchModal({ isOpen, onClose, onResultClick }: SearchModalProps) {
  const [query, setQuery] = useState('')
  const [results, setResults] = useState<SearchResult[]>([])
  const [loading, setLoading] = useState(false)
  const [channelFilter, setChannelFilter] = useState<number | null>(null)
  const [userFilter, setUserFilter] = useState<number | null>(null)
  const inputRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    if (isOpen && inputRef.current) {
      inputRef.current.focus()
    }
  }, [isOpen])

  useEffect(() => {
    const searchMessages = async () => {
      if (!query.trim() || query.length < 2) {
        setResults([])
        return
      }

      setLoading(true)
      try {
        const response = await api.post('/api/messages/search', {
          query: query.trim(),
          channel_id: channelFilter,
          user_id: userFilter,
          limit: 50,
        })
        setResults(response.data)
      } catch (error) {
        console.error('Search failed:', error)
        setResults([])
      } finally {
        setLoading(false)
      }
    }

    const debounce = setTimeout(searchMessages, 300)
    return () => clearTimeout(debounce)
  }, [query, channelFilter, userFilter])

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Escape') {
      onClose()
    }
  }

  if (!isOpen) return null

  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center pt-20">
      {/* Backdrop */}
      <div
        className="absolute inset-0 bg-black/50"
        onClick={onClose}
      />

      {/* Modal */}
      <div
        className="relative w-full max-w-2xl bg-[#36393f] rounded-lg shadow-xl border border-[#3f4147] overflow-hidden"
        onKeyDown={handleKeyDown}
      >
        {/* Search input */}
        <div className="flex items-center gap-3 p-4 border-b border-[#3f4147]">
          <Search size={20} className="text-[#949ba4]" />
          <input
            ref={inputRef}
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search messages..."
            className="flex-1 bg-transparent text-white placeholder-[#949ba4] focus:outline-none text-lg"
          />
          <button
            onClick={onClose}
            className="p-1 hover:bg-[#3f4147] rounded text-[#949ba4] hover:text-white"
          >
            <X size={20} />
          </button>
        </div>

        {/* Filters */}
        <div className="flex items-center gap-4 px-4 py-2 border-b border-[#3f4147] text-sm">
          <span className="text-[#949ba4]">Filters:</span>
          <button
            onClick={() => setChannelFilter(channelFilter ? null : 1)}
            className={`flex items-center gap-1 px-2 py-1 rounded ${
              channelFilter ? 'bg-[#5865f2] text-white' : 'bg-[#2e3035] text-[#b9bbbe] hover:bg-[#3f4147]'
            }`}
          >
            <Hash size={14} />
            <span>Channel</span>
          </button>
          <button
            onClick={() => setUserFilter(userFilter ? null : 1)}
            className={`flex items-center gap-1 px-2 py-1 rounded ${
              userFilter ? 'bg-[#5865f2] text-white' : 'bg-[#2e3035] text-[#b9bbbe] hover:bg-[#3f4147]'
            }`}
          >
            <User size={14} />
            <span>From user</span>
          </button>
        </div>

        {/* Results */}
        <div className="max-h-96 overflow-y-auto">
          {loading ? (
            <div className="p-8 text-center text-[#949ba4]">
              Searching...
            </div>
          ) : results.length === 0 ? (
            <div className="p-8 text-center text-[#949ba4]">
              {query.length < 2
                ? 'Type at least 2 characters to search'
                : 'No messages found'}
            </div>
          ) : (
            <div className="divide-y divide-[#3f4147]">
              {results.map((result) => (
                <button
                  key={result.id}
                  onClick={() => {
                    onResultClick(result.channel_id, result.id)
                    onClose()
                  }}
                  className="w-full p-4 text-left hover:bg-[#2e3035] transition-colors"
                >
                  <div className="flex items-center gap-2 text-sm text-[#949ba4] mb-1">
                    <Hash size={14} />
                    <span>{result.channel_name || 'Unknown'}</span>
                    <span>•</span>
                    <span>{result.author_username || 'Unknown'}</span>
                    <span>•</span>
                    <Calendar size={14} />
                    <span>{new Date(result.created_at).toLocaleDateString()}</span>
                  </div>
                  <p className="text-[#dcddde] line-clamp-2">
                    {result.highlight || result.content}
                  </p>
                </button>
              ))}
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="px-4 py-2 border-t border-[#3f4147] text-xs text-[#949ba4]">
          Press <kbd className="px-1 py-0.5 bg-[#2e3035] rounded">Esc</kbd> to close
          {results.length > 0 && (
            <span className="float-right">{results.length} results</span>
          )}
        </div>
      </div>
    </div>
  )
}
