import { MessageCircle } from 'lucide-react'

interface MessageProps {
  message: any
  onClick?: (message: any) => void
  showThreadIndicator?: boolean
}

export default function Message({ message, onClick, showThreadIndicator = true }: MessageProps) {
  const hasThread = message.thread_count > 0

  return (
    <div 
      className={`message p-2 border-b ${onClick ? 'cursor-pointer hover:bg-gray-800 transition-colors' : ''}`}
      onClick={() => onClick?.(message)}
    >
      <div className="flex items-baseline justify-between">
        <div className="author font-bold">{message.author_username || message.author}</div>
        {message.created_at && (
          <div className="text-xs text-gray-500 ml-2">
            {new Date(message.created_at).toLocaleString()}
          </div>
        )}
      </div>
      <div className="content mt-1">{message.content}</div>
      
      {/* Thread indicator */}
      {showThreadIndicator && hasThread && (
        <div className="mt-2 flex items-center gap-1 text-xs text-blue-400">
          <MessageCircle size={12} />
          <span>{message.thread_count} {message.thread_count === 1 ? 'reply' : 'replies'}</span>
        </div>
      )}
    </div>
  )
} 
