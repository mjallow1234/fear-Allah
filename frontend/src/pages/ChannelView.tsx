import { useState, useEffect, useLayoutEffect, useRef, useCallback } from 'react'
import { useParams } from 'react-router-dom'
import api from '../services/api'
import { fetchChannelMessages } from '../services/channels'
import Message from '../components/Chat/Message'
import ThreadPanel from '../components/ThreadPanel'
import { Send, Users, Paperclip } from 'lucide-react'
import { joinChannel, leaveChannel, onSocketEvent } from '../realtime'
import { useAuthStore } from '../stores/authStore'
import { usePresenceStore } from '../stores/presenceStore'
import { useTypingStore, formatTypingIndicator } from '../stores/typingStore'
import { useReadReceiptStore, formatSeenBy } from '../stores/readReceiptStore'
import { usePermissions } from '../hooks/usePermissions'
import { emitTypingStart, emitTypingStop, subscribeToTyping } from '../realtime/typing'
import { fetchChannelReads, markChannelRead, clearPendingMarkRead } from '../realtime/readReceipts'
import { uploadFile, getUploadLimits, validateFile, type AttachmentLimits, type UploadProgress } from '../services/attachments'
import AttachmentPreview, { type StagedFile, type UploadingFile } from '../components/AttachmentPreview'
import { mergeMessagesById } from '../utils/mergeMessages'
import { toggleReaction } from '../services/reactions'
import EmojiPickerPopover, { EmojiPickerTrigger } from '../components/EmojiPickerPopover'
import { useOrderStore } from '../stores/orderStore'
import { useAutomationEventsStore, parseAutomationEventFromResponse } from '../stores/automationEventsStore'

export default function ChannelView() {
  const { channelId } = useParams<{ channelId: string }>()
  const currentUser = useAuthStore((state) => state.user)
  const onlineUserIds = usePresenceStore((state) => state.onlineUserIds)
  const { addTypingUser, removeTypingUser, getTypingUsers, clearChannel } = useTypingStore()
  const { getUsersWhoReadMessage } = useReadReceiptStore()
  const { hasPermission, isSystemAdmin } = usePermissions()
  const [channelName, setChannelName] = useState<string | null>(null)
  const [channelType, setChannelType] = useState<string | null>(null)
  const [channelMembers, setChannelMembers] = useState<{ id: number; user_id?: number; username?: string }[]>([])
  const [memberUsernames, setMemberUsernames] = useState<Record<number, string>>({})
  const [loading, setLoading] = useState(false)

  const [messages, setMessages] = useState<any[] | null>(null)
  const [loadingMessages, setLoadingMessages] = useState(false)
  const [messagesError, setMessagesError] = useState<string | null>(null)
  const [hasMore, setHasMore] = useState<boolean>(false)
  const [loadingOlder, setLoadingOlder] = useState(false)
  // Track seen message IDs to prevent duplicates when simultaneous socket handlers fire
  const seenMessageIdsRef = useRef<Set<number>>(new Set())

  // Message input state
  const [newMessage, setNewMessage] = useState('')
  const [sending, setSending] = useState(false)
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const messagesContainerRef = useRef<HTMLDivElement>(null)
  
  // Track if we should scroll to bottom (only for new messages, not older)
  const shouldScrollToBottom = useRef(true)
  
  // Store scroll position before loading older messages
  const scrollRestoreInfo = useRef<{ scrollHeight: number; scrollTop: number } | null>(null)
  
  // Thread panel state
  const [selectedThread, setSelectedThread] = useState<any | null>(null)

  // Track current channel for merge logic
  const currentChannelRef = useRef<string | undefined>(undefined)

  // File upload state
  const [stagedFiles, setStagedFiles] = useState<(StagedFile | UploadingFile)[]>([])
  const [uploadLimits, setUploadLimits] = useState<AttachmentLimits | null>(null)
  const [isDragging, setIsDragging] = useState(false)
  const fileInputRef = useRef<HTMLInputElement>(null)
  const dragCounterRef = useRef(0)

  // Emoji picker state for composer (hotfix)
  const [emojiOpen, setEmojiOpen] = useState(false)
  const inputRef = useRef<HTMLInputElement>(null)
  const emojiTriggerRef = useRef<HTMLButtonElement | null>(null)

  // Mark channel as read when at bottom with messages
  const markAsReadIfAtBottom = useCallback(() => {
    if (!channelId || !messages || messages.length === 0) return
    
    // Skip for DM channels
    if (channelType === 'direct') return
    
    const container = messagesContainerRef.current
    if (!container) return
    
    // Check if scrolled to bottom (within 100px threshold)
    const isAtBottom = container.scrollHeight - container.scrollTop - container.clientHeight < 100
    
    if (isAtBottom) {
      // Filter messages to only those belonging to the current channel
      const numChannelId = Number(channelId)
      const channelMessages = messages.filter(
        (m: any) => m.channel_id === numChannelId && !m.parent_id
      )
      
      // Only mark as read if we have messages for this specific channel
      if (channelMessages.length === 0) return
      
      const lastMessageId = channelMessages[channelMessages.length - 1].id
      if (!lastMessageId || typeof lastMessageId !== 'number') return
      
      markChannelRead(numChannelId, lastMessageId, channelType || undefined)
    }
  }, [channelId, messages, channelType])

  useEffect(() => {
    if (!channelId) return
    setLoading(true)
    api.get(`/api/channels/${channelId}`)
      .then((res) => {
        setChannelName(res.data.display_name || res.data.name || `Channel ${channelId}`)
        setChannelType(res.data.type || null)
      })
      .catch(() => {
        setChannelName(`Channel ${channelId}`)
        setChannelType(null)
      })
      .finally(() => setLoading(false))
    
    // Fetch channel members for presence count and usernames
    api.get(`/api/channels/${channelId}/members`)
      .then((res) => {
        const members = Array.isArray(res.data) ? res.data : []
        setChannelMembers(members)
        
        // Build username map for read receipts
        const usernameMap: Record<number, string> = {}
        for (const m of members) {
          const userId = m.user_id || m.id
          if (userId && m.username) {
            usernameMap[userId] = m.username
          }
        }
        setMemberUsernames(usernameMap)
      })
      .catch(() => setChannelMembers([]))
  }, [channelId])

  // Fetch initial read receipts for this channel (skip for DMs)
  useEffect(() => {
    if (!channelId || channelType === null) return
    fetchChannelReads(Number(channelId), channelType)
  }, [channelId, channelType])

  // Combined: Fetch messages FIRST, then join socket room
  // This prevents race condition where socket events arrive before messages are loaded
  useEffect(() => {
    if (!channelId) {
      setMessages(null)
      setHasMore(false)
      currentChannelRef.current = undefined
      return
    }
    
    const numChannelId = Number(channelId)
    const currentUserId = currentUser?.id
    
    // Track if we're switching to a different channel
    const isSameChannel = currentChannelRef.current === channelId
    currentChannelRef.current = channelId
    
    // Do NOT clear messages - keep previous state until REST completes
    // This prevents flicker and preserves attachments during the brief load
    
    seenMessageIdsRef.current.clear()
    
    let cancelled = false
    let socketCleanup: (() => void) | null = null
    
    setLoadingMessages(true)
    setMessagesError(null)
    
    console.log(`[ChannelView] Fetching messages for channel ${channelId}`)
    
    // STEP 1: Fetch messages FIRST
    fetchChannelMessages(numChannelId)
      .then(({ messages: list, has_more }) => {
        if (cancelled) return
        
        console.log(`[ChannelView] Messages loaded: ${list?.length || 0}`)
        
        // Merge with existing messages to preserve realtime-added attachments
        setMessages(prev => {
          // If switching channels, don't merge with old channel's messages
          if (!isSameChannel) return list
          return mergeMessagesById(prev, list)
        })
        setHasMore(has_more)
        // Initialize seenMessageIdsRef with existing messages to avoid duplicates
        seenMessageIdsRef.current = new Set((list || []).map((m: any) => m.id))
        
        // STEP 2: Only AFTER messages are loaded, join socket room
        console.log(`[ChannelView] Joining socket room after load for channel ${channelId}`)
        joinChannel(numChannelId)
        
        // Subscribe to new messages
        const unsubscribeMessage = onSocketEvent<{
          id: number
          content: string
          channel_id: number
          author_id: number
          author_username: string
          parent_id: number | null
          created_at: string
          is_edited: boolean
          reactions: any[]
        }>('message:new', (data) => {
          if (cancelled) return
          // Only handle messages for this channel (top-level only, not thread replies)
          if (data.channel_id !== numChannelId) return
          if (data.parent_id) return  // Thread replies are handled separately
          
          // Skip messages from current user - they're added via REST response
          if (data.author_id === currentUserId) {
            console.log('[Socket.IO] Skipping own message (added via REST):', data.id)
            return
          }
          
          // Prevent duplicates using seenMessageIdsRef (guards against concurrent handlers)
          if (seenMessageIdsRef.current.has(data.id)) {
            console.log('[Socket.IO] Duplicate message ignored by seen set:', data.id)
            return
          }
          seenMessageIdsRef.current.add(data.id)

          // Add message from other users
          setMessages(prev => {
            if (!prev) return [data]
            // Double-check for duplicates
            if (prev.some(m => m.id === data.id)) return prev
            // Scroll to bottom for new real-time messages
            shouldScrollToBottom.current = true
            console.log('[Socket.IO] Adding message from other user:', data.id)
            return [...prev, data]
          })
        })

        // Subscribe to thread replies (update reply count)
        const unsubscribeThread = onSocketEvent<{
          id: number
          parent_id: number
          channel_id: number
        }>('thread:reply', (data) => {
          if (cancelled) return
          console.log('[ChannelView] Received thread:reply', data)
          if (data.channel_id !== numChannelId) return

          // Update parent message's thread count
          setMessages(prev => {
            if (!prev) return prev
            return prev.map(m => {
              if (m.id === data.parent_id) {
                return { ...m, thread_count: (m.thread_count || 0) + 1 }
              }
              return m
            })
          })
        })

        // Subscribe to attachment added events
        const unsubscribeAttachment = onSocketEvent<{
          id: number
          message_id: number
          channel_id: number
          filename: string
          file_size: number
          mime_type: string
          url: string
          created_at: string
        }>('message:attachment_added', (data) => {
          if (cancelled) return
          console.log('[ChannelView] Received message:attachment_added', data)
          if (data.channel_id !== numChannelId) return

          // Add attachment to the message
          setMessages(prev => {
            if (!prev) {
              // Safety net: messages not loaded yet, trigger refetch
              console.log('[ChannelView] Attachment received but no messages - triggering refetch')
              fetchChannelMessages(numChannelId).then(({ messages: list }) => {
                if (!cancelled) setMessages(list)
              })
              return prev
            }
            
            const messageExists = prev.some(m => m.id === data.message_id)
            if (!messageExists) {
              // Safety net: message doesn't exist, trigger refetch
              console.log(`[ChannelView] Attachment for unknown message ${data.message_id} - triggering refetch`)
              fetchChannelMessages(numChannelId).then(({ messages: list }) => {
                if (!cancelled) setMessages(p => mergeMessagesById(p, list))
              })
              return prev
            }
            
            return prev.map(m => {
              if (m.id === data.message_id) {
                const existingAttachments = m.attachments || []
                // Prevent duplicate attachments
                if (existingAttachments.some((a: any) => a.id === data.id)) return m
                return {
                  ...m,
                  attachments: [...existingAttachments, {
                    id: data.id,
                    filename: data.filename,
                    file_size: data.file_size,
                    mime_type: data.mime_type,
                    url: data.url,
                    created_at: data.created_at,
                  }]
                }
              }
              return m
            })
          })
        })

        // Subscribe to reaction added events
        const unsubscribeReactionAdded = onSocketEvent<{
          message_id: number
          emoji: string
          user_id: number
          username: string
        }>('message:reaction_added', (data) => {
          if (cancelled) return
          console.log('[ChannelView] Received message:reaction_added', data)
          
          setMessages(prev => {
            if (!prev) return prev
            return prev.map(m => {
              if (m.id !== data.message_id) return m
              // Reconcile reactions immutably: always replace the reactions array
              const oldReactions = m.reactions || []
              const idx = oldReactions.findIndex((r: any) => r.emoji === data.emoji)
              let newReactions
              if (idx >= 0) {
                // Update existing reaction (add user if not present)
                const r = oldReactions[idx]
                if (!r.users.includes(data.user_id)) {
                  newReactions = [
                    ...oldReactions.slice(0, idx),
                    {
                      ...r,
                      count: r.count + 1,
                      users: [...r.users, data.user_id],
                    },
                    ...oldReactions.slice(idx + 1),
                  ]
                } else {
                  // Already present, no change
                  newReactions = oldReactions
                }
              } else {
                // Add new reaction
                newReactions = [
                  ...oldReactions,
                  {
                    emoji: data.emoji,
                    count: 1,
                    users: [data.user_id],
                  },
                ]
              }
              return { ...m, reactions: newReactions }
            })
          })
        })

        // Subscribe to reaction removed events
        const unsubscribeReactionRemoved = onSocketEvent<{
          message_id: number
          emoji: string
          user_id: number
          username: string
        }>('message:reaction_removed', (data) => {
          if (cancelled) return
          console.log('[ChannelView] Received message:reaction_removed', data)
          
          setMessages(prev => {
            if (!prev) return prev
            return prev.map(m => {
              if (m.id !== data.message_id) return m
              const oldReactions = m.reactions || []
              const idx = oldReactions.findIndex((r: any) => r.emoji === data.emoji)
              let newReactions = oldReactions
              if (idx >= 0) {
                const r = oldReactions[idx]
                const updatedUsers = r.users.filter((id: number) => id !== data.user_id)
                if (updatedUsers.length === 0) {
                  // Remove the reaction entirely
                  newReactions = [
                    ...oldReactions.slice(0, idx),
                    ...oldReactions.slice(idx + 1),
                  ]
                } else {
                  newReactions = [
                    ...oldReactions.slice(0, idx),
                    {
                      ...r,
                      count: updatedUsers.length,
                      users: updatedUsers,
                    },
                    ...oldReactions.slice(idx + 1),
                  ]
                }
              }
              return { ...m, reactions: newReactions }
            })
          })
        })

        // message updated (edit)
        const unsubscribeUpdated = onSocketEvent<{
          id: number
          content: string
          channel_id: number
          is_edited?: boolean
          edited_at?: string
        }>('message:updated', (data) => {
          if (cancelled) return
          if (data.channel_id !== numChannelId) return
          console.log('[ChannelView] Received message:updated', data)
          setMessages(prev => prev && prev.map((m: any) => m.id === data.id ? { ...m, content: data.content, is_edited: Boolean(data.is_edited), edited_at: data.edited_at } : m))
        })

        // message deleted (soft-delete)
        const unsubscribeDeleted = onSocketEvent<{
          id: number
          channel_id: number
        }>('message:deleted', (data) => {
          if (cancelled) return
          if (data.channel_id !== numChannelId) return
          console.log('[ChannelView] Received message:deleted', data)
          setMessages(prev => prev && prev.map((m: any) => m.id === data.id ? { ...m, deleted: true, content: 'This message was deleted', reactions: [] } : m))
        })

        // pinned / unpinned
        const unsubscribePinned = onSocketEvent<{ id: number; channel_id: number }>('message:pinned', (data) => {
          if (cancelled) return
          if (data.channel_id !== numChannelId) return
          console.log('[ChannelView] Received message:pinned', data)
          setMessages(prev => prev && prev.map((m: any) => m.id === data.id ? { ...m, pinned: true } : m))
        })

        const unsubscribeUnpinned = onSocketEvent<{ id: number; channel_id: number }>('message:unpinned', (data) => {
          if (cancelled) return
          if (data.channel_id !== numChannelId) return
          console.log('[ChannelView] Received message:unpinned', data)
          setMessages(prev => prev && prev.map((m: any) => m.id === data.id ? { ...m, pinned: false } : m))
        })

        socketCleanup = () => {
          leaveChannel(numChannelId)
          unsubscribeMessage()
          unsubscribeThread()
          unsubscribeAttachment()
          unsubscribeReactionAdded()
          unsubscribeReactionRemoved()
          unsubscribeUpdated()
          unsubscribeDeleted()
          unsubscribePinned()
          unsubscribeUnpinned()
        }
      })
      .catch((err) => {
        if (cancelled) return
        console.error('Failed to load messages', err)
        setMessagesError('Failed to load messages')
      })
      .finally(() => {
        if (cancelled) return
        setLoadingMessages(false)
      })
      
    return () => {
      cancelled = true
      if (socketCleanup) socketCleanup()
    }
  }, [channelId, currentUser?.id])

  // Scroll to bottom only when shouldScrollToBottom is true (new messages, not older)
  useEffect(() => {
    if (shouldScrollToBottom.current) {
      messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
      // Mark as read when scrolling to bottom with new messages
      markAsReadIfAtBottom()
    }
  }, [messages, markAsReadIfAtBottom])

  // Mark as read on scroll
  useEffect(() => {
    const container = messagesContainerRef.current
    if (!container) return
    
    const handleScroll = () => {
      markAsReadIfAtBottom()
    }
    
    container.addEventListener('scroll', handleScroll, { passive: true })
    return () => container.removeEventListener('scroll', handleScroll)
  }, [markAsReadIfAtBottom])

  // Mark as read when channel gains focus
  useEffect(() => {
    const handleFocus = () => {
      markAsReadIfAtBottom()
    }
    
    window.addEventListener('focus', handleFocus)
    return () => window.removeEventListener('focus', handleFocus)
  }, [markAsReadIfAtBottom])

  // Cleanup pending mark-read when leaving channel
  useEffect(() => {
    return () => {
      clearPendingMarkRead()
    }
  }, [channelId])

  // Subscribe to typing events
  useEffect(() => {
    if (!channelId) return
    
    const numChannelId = Number(channelId)
    
    // Clear any stale typing state for this channel
    clearChannel(numChannelId)
    
    // Subscribe to typing events
    const unsubscribe = subscribeToTyping(
      numChannelId,
      (userId, username) => addTypingUser(numChannelId, userId, username),
      (userId, _username) => removeTypingUser(numChannelId, userId)
    )
    
    return () => {
      unsubscribe()
      clearChannel(numChannelId)
      // Stop typing if we were typing in this channel
      emitTypingStop(numChannelId)
    }
  }, [channelId, addTypingUser, removeTypingUser, clearChannel])

  // Fetch upload limits on mount
  useEffect(() => {
    getUploadLimits()
      .then(setUploadLimits)
      .catch((err) => console.error('Failed to fetch upload limits:', err))
  }, [])

  // Generate unique ID for staged files
  const generateFileId = () => `file-${Date.now()}-${Math.random().toString(36).slice(2, 9)}`

  // Handle file selection from file picker
  const handleFileSelect = useCallback((files: FileList | null) => {
    if (!files || files.length === 0 || !uploadLimits) return

    const newFiles: StagedFile[] = []
    
    for (let i = 0; i < files.length; i++) {
      const file = files[i]
      const error = validateFile(file, uploadLimits)
      
      const stagedFile: StagedFile = {
        id: generateFileId(),
        file,
        error: error || undefined,
      }

      // Generate preview for images
      if (!error && file.type.startsWith('image/')) {
        const reader = new FileReader()
        reader.onload = (e) => {
          setStagedFiles(prev => 
            prev.map(f => f.id === stagedFile.id ? { ...f, preview: e.target?.result as string } : f)
          )
        }
        reader.readAsDataURL(file)
      }

      newFiles.push(stagedFile)
    }

    setStagedFiles(prev => [...prev, ...newFiles])
  }, [uploadLimits])

  // Remove a staged file
  const removeStagedFile = useCallback((id: string) => {
    setStagedFiles(prev => prev.filter(f => f.id !== id))
  }, [])

  // Drag and drop handlers
  const handleDragEnter = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    e.stopPropagation()
    dragCounterRef.current++
    if (e.dataTransfer.types.includes('Files')) {
      setIsDragging(true)
    }
  }, [])

  const handleDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    e.stopPropagation()
    dragCounterRef.current--
    if (dragCounterRef.current === 0) {
      setIsDragging(false)
    }
  }, [])

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    e.stopPropagation()
  }, [])

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    e.stopPropagation()
    setIsDragging(false)
    dragCounterRef.current = 0
    
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      handleFileSelect(e.dataTransfer.files)
    }
  }, [handleFileSelect])

  // Restore scroll position synchronously after DOM updates when loading older messages
  useLayoutEffect(() => {
    if (scrollRestoreInfo.current && messagesContainerRef.current) {
      const container = messagesContainerRef.current
      const { scrollHeight: oldScrollHeight, scrollTop: oldScrollTop } = scrollRestoreInfo.current
      const newScrollHeight = container.scrollHeight
      // Restore position: new content added at top pushes everything down
      container.scrollTop = newScrollHeight - oldScrollHeight + oldScrollTop
      // Clear the restore info
      scrollRestoreInfo.current = null
      // NOTE: Do NOT re-enable shouldScrollToBottom here - 
      // the useEffect above runs AFTER this and would scroll to bottom!
      // shouldScrollToBottom stays false until user sends a new message
    }
  }, [messages])

  async function loadOlder() {
    if (!messages || messages.length === 0) return
    
    // Capture scroll position before loading
    const container = messagesContainerRef.current
    if (container) {
      scrollRestoreInfo.current = {
        scrollHeight: container.scrollHeight,
        scrollTop: container.scrollTop
      }
    }
    
    // Don't scroll to bottom when loading older messages
    shouldScrollToBottom.current = false
    
    setLoadingOlder(true)
    setMessagesError(null)
    try {
      const oldest = messages[0]
      const beforeId = oldest.id
      const res = await fetchChannelMessages(Number(channelId), beforeId)
      setMessages(prev => (prev ? [...res.messages, ...prev] : res.messages))
      setHasMore(res.has_more)
      // Scroll restoration happens in useLayoutEffect above
    } catch (err) {
      console.error('Failed to load older messages', err)
      setMessagesError('Failed to load messages')
      scrollRestoreInfo.current = null
      shouldScrollToBottom.current = true
    } finally {
      setLoadingOlder(false)
    }
  }

  async function handleSendMessage(e: React.FormEvent) {
    e.preventDefault()
    
    // Need either message content or files (files without message are allowed)
    const hasContent = newMessage.trim().length > 0
    const hasValidFiles = stagedFiles.some(f => !f.error && !('completed' in f && f.completed))
    
    if ((!hasContent && !hasValidFiles) || !channelId || sending) return

    // Enable scroll to bottom for new messages
    shouldScrollToBottom.current = true
    
    // Stop typing indicator when sending
    emitTypingStop(Number(channelId))
    
    setSending(true)
    try {
      let messageId: number | undefined
      
      // Send message first (if there's content)
      if (hasContent) {
        const messageContent = newMessage.trim()
        const response = await api.post('/api/messages/', {
          content: messageContent,
          channel_id: Number(channelId)
        })
        // Optimistically append the new message
        const sentMessage = response.data
        setMessages(prev => prev ? [...prev, sentMessage] : [sentMessage])
        // Mark as seen to avoid duplicate from socket emit
        if (sentMessage?.id) {
          seenMessageIdsRef.current.add(sentMessage.id)
          messageId = sentMessage.id
        }
        
        // Trigger Orders store refresh if /order create succeeded (not dry_run, not error)
        if (
          messageContent.toLowerCase().startsWith('/order create') &&
          !messageContent.toLowerCase().includes('dry_run=true') &&
          sentMessage?.system === true &&
          sentMessage?.content?.includes('Order created')
        ) {
          // Refresh orders store so Orders tab updates immediately
          useOrderStore.getState().handleOrderCreated({ 
            order_id: parseInt(sentMessage.content.match(/ID:\s*(\d+)/)?.[1] || '0'),
            status: 'SUBMITTED'
          })
        }
        
        // Track automation events from slash command responses
        if (sentMessage?.system === true && messageContent.startsWith('/')) {
          const eventData = parseAutomationEventFromResponse(
            sentMessage.content || '',
            currentUser?.username || 'unknown'
          )
          if (eventData) {
            useAutomationEventsStore.getState().addEvent(eventData)
          }
        }
        
        setNewMessage('')
      }
      
      // Upload files
      const validFiles = stagedFiles.filter(f => !f.error && !('completed' in f && f.completed))
      
      if (validFiles.length > 0) {
        // Mark files as uploading
        setStagedFiles(prev => 
          prev.map(f => {
            if (validFiles.some(vf => vf.id === f.id)) {
              return { ...f, uploading: true, progress: 0, completed: false } as UploadingFile
            }
            return f
          })
        )
        
        // For file-only uploads (no message content), we'll need to refetch to get the created message
        const isFileOnlyUpload = !hasContent
        let fileOnlyMessageId: number | undefined
        
        // Upload each file
        for (const stagedFile of validFiles) {
          try {
            const response = await uploadFile(
              stagedFile.file,
              Number(channelId),
              messageId,
              (progress: UploadProgress) => {
                setStagedFiles(prev =>
                  prev.map(f => 
                    f.id === stagedFile.id 
                      ? { ...f, progress: progress.percentage } as UploadingFile
                      : f
                  )
                )
              }
            )
            
            // For file-only uploads, backend creates the message - track its ID
            // Response is the Attachment object itself, message_id is directly on it
            if (isFileOnlyUpload && response?.message_id) {
              fileOnlyMessageId = response.message_id
              // Mark this message as seen to avoid duplicates
              if (fileOnlyMessageId) seenMessageIdsRef.current.add(fileOnlyMessageId)
            }
            
            // Mark as completed
            setStagedFiles(prev =>
              prev.map(f => 
                f.id === stagedFile.id 
                  ? { ...f, uploading: false, completed: true, progress: 100 } as UploadingFile
                  : f
              )
            )
          } catch (err) {
            const error = err instanceof Error ? err.message : 'Upload failed'
            setStagedFiles(prev =>
              prev.map(f => 
                f.id === stagedFile.id 
                  ? { ...f, uploading: false, error, progress: 0, completed: false } as UploadingFile
                  : f
              )
            )
          }
        }
        
        // For file-only uploads, fetch the message to add it to the UI
        if (isFileOnlyUpload && fileOnlyMessageId) {
          try {
            // Fetch the specific message to add it to the UI
            const msgResponse = await api.get(`/api/messages/${fileOnlyMessageId}`)
            const fileMessage = msgResponse.data
            if (fileMessage) {
              setMessages(prev => {
                if (!prev) return [fileMessage]
                // Check for duplicates
                if (prev.some(m => m.id === fileMessage.id)) return prev
                return [...prev, fileMessage]
              })
            }
          } catch (err) {
            console.error('Failed to fetch file-only message:', err)
            // Fallback: refetch all messages
            fetchChannelMessages(Number(channelId)).then(({ messages: list }) => {
              setMessages(prev => mergeMessagesById(prev, list))
            })
          }
        }
        
        // Clear completed files after a short delay
        setTimeout(() => {
          setStagedFiles(prev => prev.filter(f => !('completed' in f && f.completed)))
        }, 500)
      }
    } catch (err) {
      console.error('Failed to send message', err)
      // Optionally show error to user
    } finally {
      setSending(false)
    }
  }

  // Toggle reaction handler
  const handleToggleReaction = async (messageId: number, emoji: string) => {
    if (!currentUser) return
    // Optimistic UI: update immediately (immutably)
    setMessages(prev => prev && prev.map(m => {
      if (m.id !== messageId) return m
      const oldReactions = m.reactions || []
      const idx = oldReactions.findIndex((r: any) => r.emoji === emoji)
      let newReactions
      if (idx >= 0) {
        // Remove if user already reacted
        const r = oldReactions[idx]
        const updatedUsers = r.users.filter((id: number) => id !== currentUser.id)
        if (updatedUsers.length === 0) {
          newReactions = [
            ...oldReactions.slice(0, idx),
            ...oldReactions.slice(idx + 1),
          ]
        } else {
          newReactions = [
            ...oldReactions.slice(0, idx),
            { ...r, count: updatedUsers.length, users: updatedUsers },
            ...oldReactions.slice(idx + 1),
          ]
        }
      } else {
        // Add new reaction
        newReactions = [
          ...oldReactions,
          { emoji, count: 1, users: [currentUser.id] },
        ]
      }
      return { ...m, reactions: newReactions }
    }))
    try {
      const res = await toggleReaction(messageId, emoji)
      // Use server response to update state (authoritative)
      setMessages(prev => prev && prev.map(m => {
        if (m.id !== messageId) return m
        return { ...m, reactions: res.reactions }
      }))
    } catch (err) {
      // Rollback on error
      setMessages(prev => prev && prev.map(m => {
        if (m.id !== messageId) return m
        // TODO: Optionally refetch reactions from server
        return m
      }))
    }
  }

  if (!channelId) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="text-center text-gray-400">
          <h2 className="text-xl font-semibold">Select a channel to start chatting</h2>
          <p className="mt-2 text-sm">Choose a channel from the sidebar to begin.</p>
        </div>
      </div>
    )
  }

  return (
    <div 
      className="flex h-full relative"
      onDragEnter={handleDragEnter}
      onDragLeave={handleDragLeave}
      onDragOver={handleDragOver}
      onDrop={handleDrop}
    >
      {/* Drag & drop overlay */}
      {isDragging && (
        <div className="absolute inset-0 z-50 bg-blue-600/20 border-4 border-dashed border-blue-500 rounded-lg flex items-center justify-center pointer-events-none">
          <div className="bg-gray-800 rounded-lg p-6 text-center">
            <Paperclip size={48} className="mx-auto text-blue-400 mb-2" />
            <p className="text-xl text-white font-medium">Drop files to upload</p>
            <p className="text-sm text-gray-400 mt-1">Release to add files to your message</p>
          </div>
        </div>
      )}

      {/* Hidden file input */}
      <input
        ref={fileInputRef}
        type="file"
        multiple
        className="hidden"
        onChange={(e) => {
          handleFileSelect(e.target.files)
          e.target.value = '' // Reset to allow selecting the same file again
        }}
        accept={uploadLimits?.allowed_mime_types.join(',') || '*/*'}
      />

      {/* Main channel content */}
      <div className="flex flex-col flex-1">
        {/* Header */}
        <div className="p-4 border-b border-gray-700 flex items-center justify-between">
          <h1 className="text-xl font-semibold">{loading ? 'Loading…' : (channelName || 'Channel')}</h1>
          {channelMembers.length > 0 && (
            <div className="flex items-center gap-2 text-sm text-gray-400">
              <Users size={16} />
              <span>
                {channelMembers.filter(m => onlineUserIds.has(m.id)).length} online / {channelMembers.length} members
              </span>
            </div>
          )}
        </div>

        {/* Messages area */}
        <div ref={messagesContainerRef} className="flex-1 overflow-y-auto p-4">
          {loadingMessages && <div className="text-gray-400">Loading messages…</div>}
          {messagesError && <div className="text-red-500">{messagesError}</div>}

          {!loadingMessages && !messagesError && messages && messages.length === 0 && (
            <div className="text-gray-500 text-center py-8">No messages yet. Start the conversation!</div>
          )}

          {!loadingMessages && !messagesError && messages && messages.length > 0 && (
            <div>
              {hasMore && (
                <div className="mb-4 text-center">
                  <button 
                    className="px-4 py-2 bg-gray-700 hover:bg-gray-600 rounded text-sm transition-colors" 
                    onClick={loadOlder} 
                    disabled={loadingOlder}
                  >
                    {loadingOlder ? 'Loading…' : 'Load older messages'}
                  </button>
                </div>
              )}
              <div className="messages space-y-3">
                {messages.filter(m => !m.parent_id).map((m: any) => (
                  <Message 
                    key={m.id} 
                    message={{ ...m, author_username: m.author_username }} 
                    onClick={setSelectedThread}
                    onToggleReaction={handleToggleReaction}
                    currentUser={currentUser}
                    isSystemAdmin={isSystemAdmin}
                    canPin={hasPermission && hasPermission('message.pin')}
                    onUpdate={(updated: any) => {
                      // Immutable, idempotent update
                      setMessages(prev => prev && prev.map(pm => pm.id === updated.id ? { ...pm, ...updated } : pm))
                    }}
                  />
                ))}
              </div>
              
              {/* Seen by indicator - only show on messages sent by current user */}
              {(() => {
                const topLevelMessages = messages.filter(m => !m.parent_id)
                if (topLevelMessages.length === 0) return null
                
                const lastMessage = topLevelMessages[topLevelMessages.length - 1]
                
                // Only show "Seen by" on messages the current user sent
                if (lastMessage.author_id !== currentUser?.id) return null
                
                const readByUserIds = getUsersWhoReadMessage(
                  Number(channelId),
                  lastMessage.id,
                  currentUser?.id
                )
                
                if (readByUserIds.length === 0) return null
                
                // Convert user IDs to usernames
                const usernames = readByUserIds
                  .map(uid => memberUsernames[uid])
                  .filter(Boolean)
                
                const seenText = formatSeenBy(usernames)
                if (!seenText) return null
                
                return (
                  <div className="text-xs text-gray-500 text-right mt-1 pr-2">
                    {seenText}
                  </div>
                )
              })()}
              
              <div ref={messagesEndRef} />
            </div>
          )}
        </div>

        {/* Message input */}
        <div className="border-t border-gray-700">
          {/* Staged files preview */}
          {stagedFiles.length > 0 && (
            <AttachmentPreview
              files={stagedFiles}
              onRemove={removeStagedFile}
              disabled={sending}
            />
          )}
          
          <div className="p-4">
            {/* Typing indicator */}
            {(() => {
              const typingUsers = getTypingUsers(Number(channelId))
              const text = formatTypingIndicator(typingUsers)
              if (!text) return null
              return (
                <div className="text-sm text-gray-400 mb-2 animate-pulse">
                  {text}
                </div>
              )
            })()}
            <form onSubmit={handleSendMessage} className="flex gap-2">
              {/* File picker button */}
              <button
                type="button"
                onClick={() => fileInputRef.current?.click()}
                className="px-3 py-2 bg-gray-700 hover:bg-gray-600 rounded-lg transition-colors"
                title="Attach files"
                disabled={sending}
              >
                <Paperclip size={18} className="text-gray-400" />
              </button>
              
              {/* Emoji picker button */}
              <div className="relative flex items-center">
                <EmojiPickerTrigger
                  ref={emojiTriggerRef}
                  onClick={() => {
                    console.log('[Emoji] Trigger clicked')
                    setEmojiOpen(true)
                  }}
                />
                <EmojiPickerPopover
                  anchorRef={emojiTriggerRef}
                  open={emojiOpen}
                  onClose={() => setEmojiOpen(false)}
                  onSelect={(emoji) => {
                    setNewMessage((prev) => prev + emoji)
                    setEmojiOpen(false)
                    setTimeout(() => {
                      inputRef.current?.focus()
                    }, 0)
                  }}
                />
              </div>

              <input
                type="text"
                value={newMessage}
                onChange={(e) => {
                  setNewMessage(e.target.value)
                  // Emit typing if there's content
                  if (e.target.value.trim() && channelId) {
                    emitTypingStart(Number(channelId))
                  } else if (channelId) {
                    emitTypingStop(Number(channelId))
                  }
                }}
                placeholder="Type a message..."
                className="flex-1 px-4 py-2 bg-gray-700 rounded-lg text-white placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500"
                disabled={sending}
                ref={inputRef} // Attach ref to input
              />
              <button
                type="submit"
                disabled={(!newMessage.trim() && stagedFiles.filter(f => !f.error).length === 0) || sending}
                className="px-4 py-2 bg-blue-600 hover:bg-blue-500 disabled:bg-gray-600 disabled:cursor-not-allowed rounded-lg transition-colors flex items-center gap-2"
              >
                <Send size={18} />
                {sending ? 'Sending…' : 'Send'}
              </button>
            </form>
          </div>
        </div>
      </div>

      {/* Thread panel */}
      {selectedThread && (
        <ThreadPanel 
          parentMessage={selectedThread} 
          onClose={() => setSelectedThread(null)} 
        />
      )}
    </div>
  )
}



