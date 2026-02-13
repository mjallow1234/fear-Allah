import { useState, useRef } from 'react'
import { MessageCircle, MoreHorizontal, Edit2, Trash2, Pin } from 'lucide-react'
import MessageAttachments from '../MessageAttachments'
import MessageReactions from '../MessageReactions'
import EmojiPickerPopover, { EmojiPickerTrigger } from '../EmojiPickerPopover'
import SlashCommandResponse, { isSlashCommandResponse } from './SlashCommandResponse'
import api from '../../services/api'

interface MessageProps {
  message: any
  onClick?: (message: any) => void
  showThreadIndicator?: boolean
  onToggleReaction?: (messageId: number, emoji: string) => void
  showReactionButton?: boolean
  currentUser?: any
  isSystemAdmin?: boolean
  canPin?: boolean
  onUpdate?: (updated: any) => void
  is_unread?: boolean
}

export default function Message({ 
  message, 
  onClick, 
  showThreadIndicator = true,
  onToggleReaction,
  showReactionButton = true,
  currentUser,
  isSystemAdmin = false,
  canPin = false,
  onUpdate,
}: MessageProps) {
  const [showEmojiPicker, setShowEmojiPicker] = useState(false)
  const [menuOpen, setMenuOpen] = useState(false)
  const [editing, setEditing] = useState(false)
  const [editContent, setEditContent] = useState('')
  const [confirmDelete, setConfirmDelete] = useState(false)
  const hasThread = message.thread_count > 0
  const hasAttachments = message.attachments && message.attachments.length > 0
  const hasReactions = message.reactions && message.reactions.length > 0
  const triggerRef = useRef<HTMLButtonElement | null>(null)
  const menuRef = useRef<HTMLDivElement | null>(null)

  const handleToggleReaction = (emoji: string) => {
    if (onToggleReaction) {
      onToggleReaction(message.id, emoji)
    }
  }

  const canEdit = currentUser && (currentUser.id === message.author_id || isSystemAdmin)
  const canDelete = currentUser && (currentUser.id === message.author_id || isSystemAdmin)

  // Edit handlers
  const startEditing = () => {
    setEditContent(message.content || '')
    setEditing(true)
    setMenuOpen(false)
  }

  const cancelEditing = () => {
    setEditing(false)
    setEditContent('')
  }

  const saveEdit = async () => {
    if (!editContent.trim()) return
    // Optimistic UI update
    onUpdate?.({ ...message, content: editContent.trim(), is_edited: true })
    setEditing(false)

    try {
      await api.put(`/api/messages/${message.id}`, { content: editContent.trim() })
    } catch (err) {
      console.error('Failed to save edit', err)
      // Re-fetch or rollback could be done here; for now refetch via onUpdate with server state omitted
    }
  }

  // Delete handlers (soft-delete)
  const confirmDeleteMessage = () => {
    setConfirmDelete(true)
    setMenuOpen(false)
  }

  const performDelete = async () => {
    // Optimistic soft-delete
    onUpdate?.({ ...message, deleted: true, content: 'This message was deleted', reactions: [] })
    setConfirmDelete(false)

    try {
      await api.delete(`/api/messages/${message.id}`)
    } catch (err) {
      console.error('Failed to delete message', err)
    }
  }

  // Pin / unpin
  const togglePin = async () => {
    try {
      if (message.pinned) {
        onUpdate?.({ ...message, pinned: false })
        await api.delete(`/api/messages/${message.id}/pin`)
      } else {
        onUpdate?.({ ...message, pinned: true })
        await api.post(`/api/messages/${message.id}/pin`)
      }
    } catch (err) {
      console.error('Failed to toggle pin', err)
    }
    setMenuOpen(false)
  }

  return (
    <div 
      data-message-id={message.id}
      className={`message group relative p-2 rounded-lg hover:bg-gray-800/50 transition-colors ${onClick ? 'cursor-pointer' : ''}`}
      onClick={(e) => {
        // Don't trigger onClick when clicking reaction buttons or menu
        if ((e.target as HTMLElement).closest('.reactions-area')) return
        if ((e.target as HTMLElement).closest('.message-menu')) return
        onClick?.(message)
      }}
    >
      <div className="flex items-baseline justify-between">
        <div className="author font-bold flex items-center gap-2">
          {message.pinned && <Pin size={14} className="text-yellow-400" />}
          <span>{message.author_username || message.author}</span>
        </div>
        {message.created_at && (
          <div className="text-xs text-gray-500 ml-2 flex items-center gap-2">
            <span>{new Date(message.created_at).toLocaleString()}</span>
            {/** unread indicator for this user */}
            {typeof (message as any).is_unread !== 'undefined' && (message as any).is_unread && (
              <span className="w-2 h-2 rounded-full bg-blue-400 inline-block ml-1" title="Unread" />
            )}
          </div>
        )}
      </div>

      {/* Content / deleted state */}
      {message.deleted ? (
        <div className="content mt-1 italic text-gray-400">This message was deleted</div>
      ) : editing ? (
        <div className="mt-1">
          <textarea
            value={editContent}
            onChange={(e) => setEditContent(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault()
                saveEdit()
              }
              if (e.key === 'Escape') cancelEditing()
            }}
            className="w-full bg-[#1f2326] text-white rounded px-2 py-1 focus:outline-none focus:ring-1 focus:ring-[#5865f2]"
            rows={3}
            autoFocus
          />
          <div className="flex gap-2 mt-1 text-xs">
            <button onClick={saveEdit} className="text-[#00aff4] hover:underline">Save</button>
            <button onClick={cancelEditing} className="text-[#949ba4] hover:underline">Cancel</button>
          </div>
        </div>
      ) : isSlashCommandResponse(message) ? (
        <div className="content mt-2">
          <SlashCommandResponse content={message.content || ''} />
        </div>
      ) : (
        <div className="content mt-1">{message.content}</div>
      )}
      
      {/* Attachments */}
      {!message.deleted && hasAttachments && (
        <MessageAttachments attachments={message.attachments} />
      )}

      {/* Reactions display */}
      <div className="reactions-area">
        {(!message.deleted && hasReactions) && (
          <MessageReactions
            reactions={message.reactions}
            onToggleReaction={handleToggleReaction}
          />
        )}
      </div>
      
      {/* Thread indicator */}
      {showThreadIndicator && hasThread && !message.deleted && (
        <div className="mt-2 flex items-center gap-1 text-xs text-blue-400">
          <MessageCircle size={12} />
          <span>{message.thread_count} {message.thread_count === 1 ? 'reply' : 'replies'}</span>
        </div>
      )}

      {/* Reaction button (shown on hover) */}
      {showReactionButton && onToggleReaction && message.id > 0 && !message.deleted && (
        <div className="absolute right-2 top-2 opacity-0 group-hover:opacity-100 transition-opacity reactions-area">
          <div className="relative">
            <EmojiPickerTrigger
              ref={triggerRef}
              onClick={() => setShowEmojiPicker(!showEmojiPicker)}
            />
            <EmojiPickerPopover
              anchorRef={triggerRef}
              open={showEmojiPicker}
              onClose={() => setShowEmojiPicker(false)}
              onSelect={handleToggleReaction}
            />
          </div>
        </div>
      )}

      {/* Kebab menu */}
      {message.id > 0 && !message.deleted && (
        <div className="absolute right-2 bottom-2 opacity-0 group-hover:opacity-100 transition-opacity message-menu">
          <div className="relative">
            <button onClick={() => setMenuOpen(!menuOpen)} className="p-1 rounded text-gray-300 hover:bg-gray-700">
              <MoreHorizontal size={16} />
            </button>
            {menuOpen && (
              <div ref={menuRef} className="absolute right-0 mt-2 w-40 bg-gray-800 border border-gray-700 rounded text-sm z-20">
                <div className="flex flex-col">
                  {canEdit && (
                    <button onClick={startEditing} className="text-left px-3 py-2 hover:bg-gray-700 flex items-center gap-2"><Edit2 size={14} />Edit</button>
                  )}
                  {canDelete && (
                    <button onClick={confirmDeleteMessage} className="text-left px-3 py-2 hover:bg-gray-700 flex items-center gap-2"><Trash2 size={14} />Delete</button>
                  )}
                  {canPin && (
                    <button onClick={togglePin} className="text-left px-3 py-2 hover:bg-gray-700 flex items-center gap-2"><Pin size={14} />{message.pinned ? 'Unpin' : 'Pin'}</button>
                  )}
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Delete confirmation modal */}
      {confirmDelete && (
        <div className="absolute inset-0 z-30 flex items-center justify-center bg-black/60">
          <div className="bg-gray-900 rounded p-4 w-96">
            <h3 className="font-semibold mb-2">Confirm delete</h3>
            <p className="text-sm text-gray-400 mb-4">Are you sure you want to delete this message? This action can be undone by admins.</p>
            <div className="flex gap-2 justify-end">
              <button onClick={() => setConfirmDelete(false)} className="px-3 py-2 bg-gray-700 rounded">Cancel</button>
              <button onClick={performDelete} className="px-3 py-2 bg-red-600 rounded text-white">Delete</button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
