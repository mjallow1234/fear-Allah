import { useState, useRef, useCallback, useMemo } from 'react'
import { useParams } from 'react-router-dom'
import { Send, Paperclip, X, FileText } from 'lucide-react'
import ChatPane, { ChatPaneRef } from '../components/ChatPane'
import MentionPicker from '../components/MentionPicker'
import { useAuthStore } from '../stores/authStore'
import api from '../services/api'

export default function ChannelView() {
  const { channelId } = useParams<{ channelId: string }>()
  const [message, setMessage] = useState('')
  const [selectedFile, setSelectedFile] = useState<File | null>(null)
  const [filePreview, setFilePreview] = useState<string | null>(null)
  const [isUploading, setIsUploading] = useState(false)
  const [mentionPickerOpen, setMentionPickerOpen] = useState(false)
  const [mentionQuery, setMentionQuery] = useState('')
  const [mentionStartIndex, setMentionStartIndex] = useState(-1)
  const inputRef = useRef<HTMLInputElement>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)
  const chatPaneRef = useRef<ChatPaneRef>(null)
  const inputContainerRef = useRef<HTMLDivElement>(null)
  const token = useAuthStore((state) => state.token)

  const channelIdNum = parseInt(channelId || '1') || 1

  const handleSend = useCallback(() => {
    if (!message.trim()) return
    chatPaneRef.current?.sendMessage(message.trim())
    setMessage('')
  }, [message])

  const handleKeyDown = (e: React.KeyboardEvent) => {
    // Don't handle Enter/Tab if mention picker is open (it handles them)
    if (mentionPickerOpen && (e.key === 'Enter' || e.key === 'Tab' || e.key === 'ArrowUp' || e.key === 'ArrowDown')) {
      return
    }
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
    if (e.key === 'Escape' && mentionPickerOpen) {
      setMentionPickerOpen(false)
    }
  }

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const value = e.target.value
    const cursorPosition = e.target.selectionStart || 0
    setMessage(value)
    
    // Check for @ mention trigger
    const textBeforeCursor = value.slice(0, cursorPosition)
    const lastAtIndex = textBeforeCursor.lastIndexOf('@')
    
    if (lastAtIndex !== -1) {
      // Check if @ is at start or preceded by a space
      const charBeforeAt = lastAtIndex > 0 ? textBeforeCursor[lastAtIndex - 1] : ' '
      if (charBeforeAt === ' ' || lastAtIndex === 0) {
        const textAfterAt = textBeforeCursor.slice(lastAtIndex + 1)
        // Only show picker if there's no space after @ (still typing username)
        if (!textAfterAt.includes(' ')) {
          setMentionPickerOpen(true)
          setMentionQuery(textAfterAt)
          setMentionStartIndex(lastAtIndex)
        } else {
          setMentionPickerOpen(false)
        }
      } else {
        setMentionPickerOpen(false)
      }
    } else {
      setMentionPickerOpen(false)
    }

    if (value.trim()) {
      chatPaneRef.current?.sendTyping(true)
    } else {
      chatPaneRef.current?.sendTyping(false)
    }
  }

  const handleMentionSelect = (username: string) => {
    // Replace the @query with @username
    const beforeMention = message.slice(0, mentionStartIndex)
    const afterCursor = message.slice(mentionStartIndex + mentionQuery.length + 1) // +1 for @
    const newMessage = `${beforeMention}@${username} ${afterCursor}`
    setMessage(newMessage)
    setMentionPickerOpen(false)
    setMentionQuery('')
    setMentionStartIndex(-1)
    
    // Focus back on input and set cursor after the mention
    setTimeout(() => {
      if (inputRef.current) {
        inputRef.current.focus()
        const newCursorPos = beforeMention.length + username.length + 2 // +2 for @ and space
        inputRef.current.setSelectionRange(newCursorPos, newCursorPos)
      }
    }, 0)
  }

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (file) {
      setSelectedFile(file)
      // Create preview for images
      if (file.type.startsWith('image/')) {
        const reader = new FileReader()
        reader.onload = (e) => {
          setFilePreview(e.target?.result as string)
        }
        reader.readAsDataURL(file)
      } else {
        setFilePreview(null)
      }
    }
  }

  const handleFileUpload = async () => {
    if (!selectedFile || !token) return

    setIsUploading(true)
    try {
      const formData = new FormData()
      formData.append('file', selectedFile)

      const response = await api.post(`/api/channels/${channelIdNum}/files`, formData, {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
      })

      if (response.status === 201) {
        setSelectedFile(null)
        setFilePreview(null)
        if (fileInputRef.current) {
          fileInputRef.current.value = ''
        }
        // Send a message with the file attachment info using the REST API
        const fileData = response.data
        const downloadUrl = `/api/channels/${channelIdNum}/files/${fileData.id}/download?token=${encodeURIComponent(token)}`
        
        // Use REST API to create message - it will broadcast to WebSocket
        await api.post('/api/messages/', {
          content: `📎 [${fileData.filename}](${downloadUrl})`,
          channel_id: channelIdNum,
        })
      }
    } catch (error: any) {
      console.error('Upload error:', error?.response?.data || error)
    } finally {
      setIsUploading(false)
    }
  }

  const clearSelectedFile = () => {
    setSelectedFile(null)
    setFilePreview(null)
    if (fileInputRef.current) {
      fileInputRef.current.value = ''
    }
  }

  const isImageFile = useMemo(() => {
    return selectedFile?.type.startsWith('image/')
  }, [selectedFile])

  const formatFileSize = (bytes: number) => {
    if (bytes < 1024) return `${bytes} B`
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
  }

  return (
    <div className="flex flex-col h-full">
      <ChatPane ref={chatPaneRef} channelId={channelId || '1'} />

      {/* Selected file preview */}
      {selectedFile && (
        <div className="px-4 py-2 border-t border-[#3f4147]">
          <div className="bg-[#2e3035] rounded-lg p-3">
            <div className="flex items-start gap-3">
              {/* Preview thumbnail */}
              <div className="flex-shrink-0">
                {isImageFile && filePreview ? (
                  <img 
                    src={filePreview} 
                    alt="Preview" 
                    className="w-20 h-20 object-cover rounded border border-[#3f4147]"
                  />
                ) : (
                  <div className="w-20 h-20 bg-[#1e1f22] rounded border border-[#3f4147] flex items-center justify-center">
                    <FileText size={32} className="text-[#949ba4]" />
                  </div>
                )}
              </div>
              
              {/* File info */}
              <div className="flex-1 min-w-0">
                <p className="text-white font-medium truncate">{selectedFile.name}</p>
                <p className="text-[#949ba4] text-sm">{formatFileSize(selectedFile.size)}</p>
                <p className="text-[#949ba4] text-xs">{selectedFile.type || 'Unknown type'}</p>
              </div>

              {/* Actions */}
              <div className="flex items-center gap-2">
                <button
                  onClick={clearSelectedFile}
                  className="p-2 text-[#949ba4] hover:text-white hover:bg-[#3f4147] rounded transition-colors"
                  title="Remove"
                >
                  <X size={18} />
                </button>
              </div>
            </div>
            
            {/* Upload button */}
            <div className="mt-3 flex justify-end">
              <button
                onClick={handleFileUpload}
                disabled={isUploading}
                className="px-4 py-2 bg-[#5865f2] hover:bg-[#4752c4] text-white text-sm rounded font-medium disabled:opacity-50 transition-colors"
              >
                {isUploading ? 'Uploading...' : 'Upload File'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Message input */}
      <div className="p-4 relative" ref={inputContainerRef}>
        {/* Mention Picker */}
        <MentionPicker
          isOpen={mentionPickerOpen}
          searchQuery={mentionQuery}
          position={{ top: 60, left: 50 }}
          onSelect={handleMentionSelect}
          onClose={() => setMentionPickerOpen(false)}
        />
        
        <div className="flex items-center gap-2 bg-[#383a40] rounded-lg px-4 py-2">
          <input
            ref={fileInputRef}
            type="file"
            onChange={handleFileSelect}
            className="hidden"
            id="file-upload"
          />
          <button
            onClick={() => fileInputRef.current?.click()}
            className="p-2 text-[#949ba4] hover:text-white transition-colors"
            title="Attach file"
          >
            <Paperclip size={20} />
          </button>
          <input
            ref={inputRef}
            type="text"
            value={message}
            onChange={handleInputChange}
            onKeyDown={handleKeyDown}
            placeholder={`Message #${channelId}`}
            className="flex-1 bg-transparent text-white placeholder-[#6d6f78] focus:outline-none"
          />
          <button
            onClick={handleSend}
            disabled={!message.trim()}
            className="p-2 text-[#949ba4] hover:text-white disabled:opacity-50 transition-colors"
          >
            <Send size={20} />
          </button>
        </div>
      </div>
    </div>
  )
}
