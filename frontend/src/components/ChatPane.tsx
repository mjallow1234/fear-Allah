import { useState, useEffect, useRef, useCallback, forwardRef, useImperativeHandle } from 'react'
import { Smile, Download, MessageSquare, X, Pencil, Trash2 } from 'lucide-react'
import type { Message, Reaction } from '../services/useWebSocket'
import { useChatSocket } from '../contexts/ChatSocketContext'
import { useAuthStore } from '../stores/authStore'
import api from '../services/api'
import MarkdownContent from './MarkdownContent'
import { notifyNewMessage, notifyMention } from '../utils/notifications'

interface ChatPaneProps {
  channelId: string
}

export interface ChatPaneRef {
  sendMessage: (content: string) => void
  sendTyping: (isTyping: boolean) => void
}

interface ExtendedMessage extends Message {
  reply_count?: number
  is_edited?: boolean
}

const EMOJI_LIST = ['👍', '❤️', '😂', '😮', '😢', '🎉', '🔥', '👏']

const ChatPane = forwardRef<ChatPaneRef, ChatPaneProps>(({ channelId }, ref) => {
  const [messages, setMessages] = useState<ExtendedMessage[]>([])
  const [showEmojiPicker, setShowEmojiPicker] = useState<number | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [activeThread, setActiveThread] = useState<number | null>(null)
  const [threadReplies, setThreadReplies] = useState<Message[]>([])
  const [threadLoading, setThreadLoading] = useState(false)
  const [threadReplyInput, setThreadReplyInput] = useState('')
  const [replyingTo, setReplyingTo] = useState<{ id: number; username: string } | null>(null)
  const [editingMessage, setEditingMessage] = useState<number | null>(null)
  const [editContent, setEditContent] = useState('')
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const threadEndRef = useRef<HTMLDivElement>(null)
  const threadInputRef = useRef<HTMLInputElement>(null)
  const user = useAuthStore((state) => state.user)

  const channelIdNum = parseInt(channelId) || 1


  // Handle new message from WebSocket - only add if it belongs to current channel
  const handleMessage = useCallback((data: any) => {
    // Only add message if it belongs to the current channel
    if (data.channel_id !== channelIdNum) return
    
    const newMessage: Message = {
      id: data.id,
      content: data.content,
      user_id: data.user_id,
      username: data.username || 'Unknown',
      channel_id: data.channel_id,
      timestamp: data.timestamp,
      reactions: data.reactions || [],
    }
    setMessages((prev) => {
      // Prevent duplicate messages
      if (prev.some(m => m.id === newMessage.id)) return prev
      return [...prev, newMessage]
    })

    // Show browser notification for messages from other users
    if (user && data.user_id !== user.id) {
      const content = data.content || ''
      const username = user.username || user.display_name || ''
      
      // Check if user is mentioned
      if (content.toLowerCase().includes(`@${username.toLowerCase()}`)) {
        notifyMention(data.username, content, channelId)
      } else {
        notifyNewMessage(data.username, content, channelId)
      }
    }
  }, [channelIdNum, user, channelId])

  // Handle reaction updates
  const handleReaction = useCallback((messageId: number, emoji: string, userId: number, action: 'add' | 'remove') => {
    setMessages((prev) =>
      prev.map((msg) => {
        if (msg.id !== messageId) return msg

        let reactions = [...(msg.reactions || [])]
        const existingIdx = reactions.findIndex((r) => r.emoji === emoji)

        if (action === 'add') {
          if (existingIdx >= 0) {
            reactions[existingIdx] = {
              ...reactions[existingIdx],
              count: reactions[existingIdx].count + 1,
              users: [...reactions[existingIdx].users, userId],
            }
          } else {
            reactions.push({ emoji, count: 1, users: [userId] })
          }
        } else {
          if (existingIdx >= 0) {
            const updated = {
              ...reactions[existingIdx],
              count: reactions[existingIdx].count - 1,
              users: reactions[existingIdx].users.filter((id) => id !== userId),
            }
            if (updated.count <= 0) {
              reactions = reactions.filter((_, i) => i !== existingIdx)
            } else {
              reactions[existingIdx] = updated
            }
          }
        }

        return { ...msg, reactions }
      })
    )
  }, [])

  const { connectChannel, wsStatus, sendReaction, sendMessage, sendTyping, onMessage, typingUsers, reconnect } = useChatSocket()

  // Register handler for incoming websocket events once and keep it stable
  useEffect(() => {
    const handler = (data: any) => {
      switch (data.type) {
        case 'message':
          handleMessage(data)
          break
        case 'reaction_add':
          handleReaction(data.message_id, data.emoji, data.user_id, 'add')
          break
        case 'reaction_remove':
          handleReaction(data.message_id, data.emoji, data.user_id, 'remove')
          break
        case 'typing_start':
          // optionally handle typing UI
          break
        case 'typing_stop':
          // optionally handle typing UI
          break
        default:
          break
      }
    }

    const unsubscribe = onMessage(handler)
    return () => {
      unsubscribe()
    }
  }, [onMessage, handleMessage, handleReaction])

  // Connect to the chat socket for this channel; provider handles guards
  useEffect(() => {
    connectChannel(channelIdNum)
  }, [channelIdNum, connectChannel])

  // Expose methods to parent via ref
  useImperativeHandle(ref, () => ({
    sendMessage,
    sendTyping,
  }), [sendMessage, sendTyping])

  // Scroll to bottom on new messages
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  // Fetch messages from API when channel changes
  useEffect(() => {
    const fetchMessages = async () => {
      setIsLoading(true)
      // Clear messages immediately when channel changes
      setMessages([])
      
      try {
        const response = await api.get(`/api/messages/channel/${channelIdNum}`)
        const fetchedMessages: ExtendedMessage[] = response.data.map((msg: any) => ({
          id: msg.id,
          content: msg.content,
          user_id: msg.author_id,
          username: msg.author_username || 'Unknown',
          channel_id: msg.channel_id,
          timestamp: msg.created_at,
          reactions: msg.reactions || [],
          reply_count: msg.reply_count || 0,
          is_edited: msg.is_edited || false,
        }))
        setMessages(fetchedMessages)
      } catch (error) {
        console.error('Failed to fetch messages:', error)
        // Show welcome message if no messages exist
        setMessages([
          {
            id: -1,
            content: `Welcome to #${channelId}! This is the beginning of the channel.`,
            user_id: 0,
            username: 'System',
            channel_id: channelIdNum,
            timestamp: new Date().toISOString(),
            reactions: [],
          },
        ])
      } finally {
        setIsLoading(false)
      }
    }

    fetchMessages()
    // Close thread panel when channel changes
    setActiveThread(null)
    setThreadReplies([])
    setReplyingTo(null)
  }, [channelIdNum, channelId])

  // Load thread replies
  const loadThreadReplies = async (messageId: number) => {
    if (activeThread === messageId) {
      // Close thread if clicking same message
      setActiveThread(null)
      setThreadReplies([])
      setReplyingTo(null)
      return
    }
    
    setThreadLoading(true)
    setActiveThread(messageId)
    setReplyingTo(null)
    try {
      const response = await api.get(`/api/messages/${messageId}/replies`)
      setThreadReplies(response.data.map((msg: any) => ({
        id: msg.id,
        content: msg.content,
        user_id: msg.author_id,
        username: msg.author_username || 'Unknown',
        channel_id: msg.channel_id,
        timestamp: msg.created_at,
        reactions: msg.reactions || [],
      })))
    } catch (error) {
      console.error('Failed to load thread replies:', error)
      setThreadReplies([])
    } finally {
      setThreadLoading(false)
    }
  }

  // Scroll to bottom of thread replies
  useEffect(() => {
    threadEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [threadReplies])

  // Start replying to a specific message in thread
  const startReplyToMessage = (messageId: number, username: string) => {
    setReplyingTo({ id: messageId, username })
    threadInputRef.current?.focus()
  }

  // Cancel replying to specific message
  const cancelReplyTo = () => {
    setReplyingTo(null)
  }

  // Send a reply in a thread
  const sendThreadReply = async () => {
    if (!threadReplyInput.trim() || !activeThread) return
    
    try {
      // Prepend mention if replying to specific message
      let content = threadReplyInput.trim()
      if (replyingTo) {
        content = `@${replyingTo.username} ${content}`
      }
      
      // Use the dedicated reply endpoint
      const response = await api.post(`/api/messages/${activeThread}/reply`, {
        content,
      })
      
      // Optimistically add the new reply to thread replies
      const newReply: Message = {
        id: response.data.id,
        content: response.data.content,
        user_id: response.data.author_id,
        username: response.data.author_username || user?.username || 'Unknown',
        channel_id: response.data.channel_id,
        timestamp: response.data.created_at,
        reactions: response.data.reactions || [],
      }
      setThreadReplies((prev) => [...prev, newReply])
      setThreadReplyInput('')
      setReplyingTo(null)
      
      // Update reply count in main messages
      setMessages((prev) =>
        prev.map((msg) =>
          msg.id === activeThread
            ? { ...msg, reply_count: (msg.reply_count || 0) + 1 }
            : msg
        )
      )
    } catch (error) {
      console.error('Failed to send thread reply:', error)
    }
  }

  // Get the parent message for the active thread
  const parentMessage = activeThread ? messages.find((m) => m.id === activeThread) : null

  const handleAddReaction = (messageId: number, emoji: string) => {
    sendReaction(messageId, emoji, 'add')
    setShowEmojiPicker(null)
  }

  const handleRemoveReaction = (messageId: number, emoji: string) => {
    sendReaction(messageId, emoji, 'remove')
  }

  const toggleReaction = (messageId: number, emoji: string, reaction: Reaction) => {
    const hasReacted = user && reaction.users.includes(user.id)
    if (hasReacted) {
      handleRemoveReaction(messageId, emoji)
    } else {
      handleAddReaction(messageId, emoji)
    }
  }

  // Edit message
  const startEditing = (msg: ExtendedMessage) => {
    setEditingMessage(msg.id)
    setEditContent(msg.content)
  }

  const cancelEditing = () => {
    setEditingMessage(null)
    setEditContent('')
  }

  const saveEdit = async (messageId: number) => {
    if (!editContent.trim()) return
    
    try {
      await api.put(`/api/messages/${messageId}`, { content: editContent.trim() })
      setMessages((prev) =>
        prev.map((msg) =>
          msg.id === messageId
            ? { ...msg, content: editContent.trim(), is_edited: true }
            : msg
        )
      )
      cancelEditing()
    } catch (error) {
      console.error('Failed to edit message:', error)
    }
  }

  // Delete message
  const deleteMessage = async (messageId: number) => {
    if (!confirm('Are you sure you want to delete this message?')) return
    
    try {
      await api.delete(`/api/messages/${messageId}`)
      setMessages((prev) => prev.filter((msg) => msg.id !== messageId))
    } catch (error) {
      console.error('Failed to delete message:', error)
    }
  }

  return (
    <div className="flex-1 flex overflow-hidden">
      {/* Main chat area */}
      <div className={`flex-1 flex flex-col overflow-hidden ${activeThread ? 'border-r border-[#3f4147]' : ''}`}>
        {/* Connection status */}
        {wsStatus === 'connecting' && (
          <div className="bg-yellow-600 text-white text-center py-1 text-sm">
            Connecting to chat...
          </div>
        )}

        {wsStatus === 'error' && (
          <div className="bg-red-600 text-white text-center py-1 text-sm flex items-center justify-center gap-2">
            <span>Failed to connect to chat server.</span>
            <button onClick={() => reconnect()} className="underline">Retry</button>
          </div>
        )}

        {wsStatus === 'disconnected' && (
          <div className="bg-yellow-600 text-white text-center py-1 text-sm flex items-center justify-center gap-2">
            <span>Disconnected from chat server. Reconnecting...</span>
            <button onClick={() => reconnect()} className="underline">Retry</button>
          </div>
        )}

        {/* Messages */}
        <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {isLoading ? (
          <div className="flex items-center justify-center h-full text-[#949ba4]">
            Loading messages...
          </div>
        ) : messages.map((msg) => (
          <div
            key={msg.id}
            className="group flex gap-3 hover:bg-[#2e3035] p-2 rounded relative"
          >
            <div className="w-10 h-10 rounded-full bg-[#5865f2] flex items-center justify-center text-white font-medium flex-shrink-0">
              {msg.username.charAt(0).toUpperCase()}
            </div>
            <div className="flex-1 min-w-0">
              <div className="flex items-baseline gap-2">
                <span className="font-medium text-white">{msg.username}</span>
                <span className="text-xs text-[#949ba4]">
                  {new Date(msg.timestamp).toLocaleTimeString()}
                </span>
                {msg.is_edited && (
                  <span className="text-xs text-[#949ba4]">(edited)</span>
                )}
              </div>
              
              {/* Message content - editable or static */}
              {editingMessage === msg.id ? (
                <div className="mt-1">
                  <input
                    type="text"
                    value={editContent}
                    onChange={(e) => setEditContent(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter') saveEdit(msg.id)
                      if (e.key === 'Escape') cancelEditing()
                    }}
                    className="w-full bg-[#40444b] text-[#dcddde] rounded px-2 py-1 focus:outline-none focus:ring-1 focus:ring-[#5865f2]"
                    autoFocus
                  />
                  <div className="flex gap-2 mt-1 text-xs">
                    <button
                      onClick={() => saveEdit(msg.id)}
                      className="text-[#00aff4] hover:underline"
                    >
                      save
                    </button>
                    <button
                      onClick={cancelEditing}
                      className="text-[#949ba4] hover:underline"
                    >
                      cancel
                    </button>
                  </div>
                </div>
              ) : (
                <MarkdownContent content={msg.content} className="break-words" />
              )}

              {/* File attachments */}
              {msg.files && msg.files.length > 0 && (
                <div className="mt-2 space-y-1">
                  {msg.files.map((file) => (
                    <a
                      key={file.id}
                      href={file.download_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="flex items-center gap-2 text-[#00aff4] hover:underline text-sm"
                    >
                      <Download size={14} />
                      {file.filename}
                    </a>
                  ))}
                </div>
              )}

              {/* Reactions */}
              {msg.reactions && msg.reactions.length > 0 && (
                <div className="flex flex-wrap gap-1 mt-2">
                  {msg.reactions.map((reaction) => (
                    <button
                      key={reaction.emoji}
                      onClick={() => toggleReaction(msg.id, reaction.emoji, reaction)}
                      className={`flex items-center gap-1 px-2 py-0.5 rounded text-sm border ${
                        user && reaction.users.includes(user.id)
                          ? 'bg-[#5865f2]/20 border-[#5865f2] text-white'
                          : 'bg-[#2e3035] border-[#3f4147] text-[#b9bbbe] hover:border-[#5865f2]'
                      }`}
                    >
                      <span>{reaction.emoji}</span>
                      <span>{reaction.count}</span>
                    </button>
                  ))}
                </div>
              )}

              {/* Thread replies indicator */}
              {msg.id > 0 && (msg.reply_count ?? 0) > 0 && (
                <button
                  onClick={() => loadThreadReplies(msg.id)}
                  className="flex items-center gap-1 mt-2 text-[#00aff4] hover:underline text-sm"
                >
                  <MessageSquare size={14} />
                  <span>{msg.reply_count} {msg.reply_count === 1 ? 'reply' : 'replies'}</span>
                </button>
              )}
            </div>

            {/* Action buttons (shown on hover) - only for real messages */}
            {msg.id > 0 && <div className="absolute right-2 top-0 opacity-0 group-hover:opacity-100 transition-opacity">
              <div className="flex gap-1 bg-[#2e3035] rounded border border-[#3f4147] p-1">
                <button
                  onClick={() => setShowEmojiPicker(showEmojiPicker === msg.id ? null : msg.id)}
                  className="p-1 hover:bg-[#3f4147] rounded text-[#b9bbbe] hover:text-white"
                  title="Add reaction"
                >
                  <Smile size={16} />
                </button>
                <button
                  onClick={() => loadThreadReplies(msg.id)}
                  className="p-1 hover:bg-[#3f4147] rounded text-[#b9bbbe] hover:text-white"
                  title="Reply in thread"
                >
                  <MessageSquare size={16} />
                </button>
                {/* Edit button - only for own messages */}
                {user && msg.user_id === user.id && (
                  <button
                    onClick={() => startEditing(msg)}
                    className="p-1 hover:bg-[#3f4147] rounded text-[#b9bbbe] hover:text-white"
                    title="Edit message"
                  >
                    <Pencil size={16} />
                  </button>
                )}
                {/* Delete button - only for own messages */}
                {user && msg.user_id === user.id && (
                  <button
                    onClick={() => deleteMessage(msg.id)}
                    className="p-1 hover:bg-[#3f4147] rounded text-[#ed4245] hover:text-red-400"
                    title="Delete message"
                  >
                    <Trash2 size={16} />
                  </button>
                )}
              </div>

              {/* Emoji picker */}
              {showEmojiPicker === msg.id && (
                <div className="absolute right-0 top-8 bg-[#2e3035] border border-[#3f4147] rounded p-2 z-10">
                  <div className="flex gap-1 flex-wrap w-48">
                    {EMOJI_LIST.map((emoji) => (
                      <button
                        key={emoji}
                        onClick={() => handleAddReaction(msg.id, emoji)}
                        className="p-1 hover:bg-[#3f4147] rounded text-lg"
                      >
                        {emoji}
                      </button>
                    ))}
                  </div>
                </div>
              )}
            </div>}
          </div>
        ))}
        <div ref={messagesEndRef} />
      </div>

      {/* Typing indicator */}
      {typingUsers.length > 0 && (
        <div className="px-4 py-2 text-sm text-[#949ba4]">
          {typingUsers.map((u) => u.name).join(', ')}{' '}
          {typingUsers.length === 1 ? 'is' : 'are'} typing...
        </div>
      )}
      </div>

      {/* Thread panel */}
      {activeThread && parentMessage && (
        <div className="w-80 flex flex-col bg-[#36393f] border-l border-[#3f4147]">
          {/* Thread header */}
          <div className="p-4 border-b border-[#3f4147] flex items-center justify-between">
            <div>
              <h3 className="text-white font-medium">Thread</h3>
              {threadReplies.length > 0 && (
                <p className="text-sm text-[#949ba4]">
                  {threadReplies.length} {threadReplies.length === 1 ? 'reply' : 'replies'}
                </p>
              )}
            </div>
            <button
              onClick={() => {
                setActiveThread(null)
                setThreadReplies([])
                setThreadReplyInput('')
                setReplyingTo(null)
              }}
              className="p-1 hover:bg-[#3f4147] rounded text-[#b9bbbe] hover:text-white"
            >
              <X size={20} />
            </button>
          </div>

          {/* Parent message */}
          <div className="p-4 border-b border-[#3f4147] bg-[#2e3035]">
            <div className="flex gap-2 items-start">
              <div className="w-8 h-8 rounded-full bg-[#5865f2] flex items-center justify-center text-white text-sm font-medium flex-shrink-0">
                {parentMessage.username.charAt(0).toUpperCase()}
              </div>
              <div className="flex-1 min-w-0">
                <div className="flex items-baseline gap-2">
                  <span className="text-white font-medium text-sm">{parentMessage.username}</span>
                  <span className="text-xs text-[#949ba4]">
                    {new Date(parentMessage.timestamp).toLocaleTimeString()}
                  </span>
                </div>
                <MarkdownContent content={parentMessage.content} className="text-sm break-words" />
              </div>
            </div>
          </div>

          {/* Thread replies */}
          <div className="flex-1 overflow-y-auto p-4 space-y-3">
            {threadLoading ? (
              <div className="text-center text-[#949ba4] text-sm">Loading replies...</div>
            ) : threadReplies.length === 0 ? (
              <div className="text-center text-[#949ba4] text-sm">No replies yet. Be the first!</div>
            ) : (
              threadReplies.map((reply) => (
                <div key={reply.id} className="group flex gap-2 items-start hover:bg-[#32353b] rounded p-1 -mx-1">
                  <div className="w-8 h-8 rounded-full bg-[#5865f2] flex items-center justify-center text-white text-sm font-medium flex-shrink-0">
                    {reply.username.charAt(0).toUpperCase()}
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-baseline gap-2">
                      <span className="text-white font-medium text-sm">{reply.username}</span>
                      <span className="text-xs text-[#949ba4]">
                        {new Date(reply.timestamp).toLocaleTimeString()}
                      </span>
                      {/* Reply button - visible on hover */}
                      <button
                        onClick={() => startReplyToMessage(reply.id, reply.username)}
                        className="opacity-0 group-hover:opacity-100 text-xs text-[#00aff4] hover:underline ml-auto transition-opacity"
                      >
                        Reply
                      </button>
                    </div>
                    <MarkdownContent content={reply.content} className="text-sm break-words" />
                  </div>
                </div>
              ))
            )}
            <div ref={threadEndRef} />
          </div>

          {/* Thread reply input */}
          <div className="p-4 border-t border-[#3f4147]">
            {/* Replying to indicator */}
            {replyingTo && (
              <div className="flex items-center gap-2 mb-2 text-sm text-[#949ba4]">
                <span>Replying to <span className="text-[#00aff4]">@{replyingTo.username}</span></span>
                <button
                  onClick={cancelReplyTo}
                  className="text-[#949ba4] hover:text-white"
                >
                  <X size={14} />
                </button>
              </div>
            )}
            <div className="flex gap-2">
              <input
                ref={threadInputRef}
                type="text"
                value={threadReplyInput}
                onChange={(e) => setThreadReplyInput(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' && !e.shiftKey) {
                    e.preventDefault()
                    sendThreadReply()
                  }
                  if (e.key === 'Escape' && replyingTo) {
                    cancelReplyTo()
                  }
                }}
                placeholder="Reply..."
                className="flex-1 bg-[#40444b] text-white px-3 py-2 rounded text-sm focus:outline-none focus:ring-1 focus:ring-[#5865f2]"
              />
              <button
                onClick={sendThreadReply}
                disabled={!threadReplyInput.trim()}
                className="px-3 py-2 bg-[#5865f2] text-white rounded text-sm hover:bg-[#4752c4] disabled:opacity-50 disabled:cursor-not-allowed"
              >
                Reply
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
})

ChatPane.displayName = 'ChatPane'

export default ChatPane
