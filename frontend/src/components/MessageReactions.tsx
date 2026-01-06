/**
 * MessageReactions - Displays reaction badges under a message
 * Phase 9.4 - Emoji Reactions Frontend
 * 
 * Features:
 * - Shows emoji with count
 * - Highlights user's own reactions
 * - Click to toggle reaction
 */
import { useAuthStore } from '../stores/authStore'

export interface Reaction {
  emoji: string
  count: number
  users: number[]
}

interface MessageReactionsProps {
  reactions: Reaction[]
  onToggleReaction: (emoji: string) => void
  disabled?: boolean
}

/**
 * Check if current user has reacted with a specific emoji
 */
export function hasReacted(reaction: Reaction, userId: number | undefined): boolean {
  if (!userId) return false
  return reaction.users.includes(userId)
}

export default function MessageReactions({ 
  reactions, 
  onToggleReaction, 
  disabled = false 
}: MessageReactionsProps) {
  const user = useAuthStore((state) => state.user)
  
  if (!reactions || reactions.length === 0) {
    return null
  }

  return (
    <div className="flex flex-wrap gap-1 mt-2">
      {reactions.map((reaction) => {
        const isOwnReaction = hasReacted(reaction, user?.id)
        
        return (
          <button
            key={reaction.emoji}
            onClick={() => !disabled && onToggleReaction(reaction.emoji)}
            disabled={disabled}
            className={`
              flex items-center gap-1 px-2 py-0.5 rounded text-sm border transition-colors
              ${disabled ? 'cursor-not-allowed opacity-50' : 'cursor-pointer'}
              ${isOwnReaction
                ? 'bg-[#5865f2]/20 border-[#5865f2] text-white'
                : 'bg-[#2e3035] border-[#3f4147] text-[#b9bbbe] hover:border-[#5865f2]'
              }
            `}
            title={`${reaction.users.length} ${reaction.users.length === 1 ? 'user' : 'users'} reacted with ${reaction.emoji}`}
          >
            <span>{reaction.emoji}</span>
            <span className="min-w-[0.75rem] text-center">{reaction.count}</span>
          </button>
        )
      })}
    </div>
  )
}
