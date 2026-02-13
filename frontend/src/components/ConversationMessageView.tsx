import React, { useState, useEffect, useRef, useCallback, useLayoutEffect } from 'react'
import { useLocation } from 'react-router-dom'
import type { Message as WSMessage } from '../services/useWebSocket'
import Message from './Chat/Message'
import ThreadPanel from '../components/ThreadPanel'
import { Send, Paperclip } from 'lucide-react'
import { joinChannel, leaveChannel, joinRoom, leaveRoom, onSocketEvent } from '../realtime'
import { fetchChannelMessages } from '../services/channels'
import { fetchDirectConversationMessages, postDirectConversationMessage } from '../services/directConversations'
import api from '../services/api'
import { uploadFile, getUploadLimits, validateFile, type AttachmentLimits, type UploadProgress } from '../services/attachments'
import AttachmentPreview, { type StagedFile, type UploadingFile } from './AttachmentPreview'
import { mergeMessagesById } from '../utils/mergeMessages'
import { toggleReaction } from '../services/reactions'
import EmojiPickerPopover, { EmojiPickerTrigger } from './EmojiPickerPopover'
import { useAuthStore } from '../stores/authStore'
import { useTypingStore, formatTypingIndicator } from '../stores/typingStore'
import { useReadReceiptStore, formatSeenBy } from '../stores/readReceiptStore'
import { emitTypingStart, emitTypingStop, subscribeToTyping, emitTypingStartDirect, emitTypingStopDirect, subscribeToTypingDirect } from '../realtime/typing'
import { fetchChannelReads, markChannelRead, clearPendingMarkRead, fetchDirectConversationReads, markDirectConversationRead } from '../realtime/readReceipts'
import { useOrderStore } from '../stores/orderStore'
import { useAutomationEventsStore, parseAutomationEventFromResponse } from '../stores/automationEventsStore'

export type Props =
  | { mode: 'channel'; channelId: number; memberUsernames?: Record<number, string> }
  | { mode: 'direct'; conversationId: number; memberUsernames?: Record<number, string> }

export default function ConversationMessageView(props: Props) {
  const currentUser = useAuthStore((s) => s.user)
  const { addTypingUser, removeTypingUser, getTypingUsers, clearChannel } = useTypingStore()
  const { getUsersWhoReadMessage, getChannelReads } = useReadReceiptStore()

  // Message lists and state
  const [messages, setMessages] = useState<any[] | null>(null)
  const [loadingMessages, setLoadingMessages] = useState(false)
  const [messagesError, setMessagesError] = useState<string | null>(null)
  const [hasMore, setHasMore] = useState<boolean>(false)
  const [loadingOlder, setLoadingOlder] = useState(false)
  const [newMessagesCount, setNewMessagesCount] = useState(0)
  const seenMessageIdsRef = useRef<Set<number>>(new Set())

  // Strongly-typed message shape used in this component
  type MessageType = WSMessage & {
    id: number
    created_at?: string
    author_username?: string
    parent_id?: number | null
    thread_count?: number
    reactions?: any[]
    attachments?: any[]
    _highlight?: boolean
  }

  // Helper that always sets messages sorted by created_at (oldest first)
  const setSortedMessages = useCallback((updater: MessageType[] | ((prev: MessageType[] | null) => MessageType[] | null)) => {
    setMessages((prev: MessageType[] | null) => {
      const next = typeof updater === 'function' ? (updater as (p: MessageType[] | null) => MessageType[] | null)(prev) : updater
      if (!next) return next as any
      const arr = Array.isArray(next) ? [...next] : (next as MessageType[])
      arr.sort((a: MessageType, b: MessageType) => new Date((a.created_at || '')).getTime() - new Date((b.created_at || '')).getTime())
      return arr as any
    })
  }, [setMessages])

  // Composer state
  const [newMessage, setNewMessage] = useState('')
  const [sending, setSending] = useState(false)
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const messagesContainerRef = useRef<HTMLDivElement>(null)
  const shouldScrollToBottom = useRef(true)
  const scrollRestoreInfo = useRef<{ scrollHeight: number; scrollTop: number } | null>(null)

  // Thread
  const [selectedThread, setSelectedThread] = useState<any | null>(null)
  const isThreadOpen = Boolean(selectedThread)


  // File upload
  const [stagedFiles, setStagedFiles] = useState<(StagedFile | UploadingFile)[]>([])
  const [uploadLimits, setUploadLimits] = useState<AttachmentLimits | null>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)

  // Emoji picker
  const [emojiOpen, setEmojiOpen] = useState(false)
  const inputRef = useRef<HTMLTextAreaElement | null>(null)
  const emojiTriggerRef = useRef<HTMLButtonElement | null>(null)

  // Composer autosize helper
  const adjustComposerHeight = useCallback((el?: HTMLTextAreaElement | null) => {
    const ta = el || inputRef.current
    if (!ta) return
    ta.style.height = 'auto'
    // add 2px padding buffer to avoid clipping on some browsers
    ta.style.height = `${Math.min(ta.scrollHeight + 2, 400)}px`
  }, [])


  // Helper to get numeric id and mode checks
  const isChannel = props.mode === 'channel'
  const isDirect = props.mode === 'direct'
  const channelId = isChannel ? props.channelId : undefined
  const convId = isDirect ? props.conversationId : undefined

  // When opening a thread panel, mark reply notifications as read for that parent message
  useEffect(() => {
    if (!selectedThread) return
    ;(async () => {
      try {
        const types = isDirect ? ['dm_reply'] : ['channel_reply']
        await (await import('../services/notifications')).markNotificationsReadFiltered({ parent_id: Number(selectedThread.id), types })
      } catch (err) {
        console.warn('Failed to mark thread notifications as read:', err)
      }
    })()
  }, [selectedThread, isDirect])

  // Mark as read for channel mode
  const markAsReadIfAtBottom = useCallback(() => {
    if (!messages || messages.length === 0) return
    const container = messagesContainerRef.current
    if (!container) return
    const isAtBottom = container.scrollHeight - container.scrollTop - container.clientHeight < 100
    if (isAtBottom) {
      if (isChannel && channelId) {
        const numChannelId = Number(channelId)
        const channelMessages = messages.filter((m: any) => m.channel_id === numChannelId && !m.parent_id)
        if (channelMessages.length === 0) return
        const lastMessageId = channelMessages[channelMessages.length - 1].id
        if (!lastMessageId || typeof lastMessageId !== 'number') return
        markChannelRead(numChannelId, lastMessageId)
      } else if (isDirect && convId) {
        const convMessages = messages.filter((m: any) => m.direct_conversation_id === convId && !m.parent_id)
        if (convMessages.length === 0) return
        const lastMessageId = convMessages[convMessages.length - 1].id
        if (!lastMessageId || typeof lastMessageId !== 'number') return
        // Mark DM read immediately
        markDirectConversationRead(convId, lastMessageId)
      }
    }
  }, [channelId, messages, isChannel, isDirect, convId])

  // Fetch messages (channel or direct)
  useEffect(() => {
    let cancelled = false
    let socketCleanup: (() => void) | null = null
    const currentUserId = currentUser?.id

    async function loadMessages() {
      setLoadingMessages(true)
      setMessagesError(null)
      seenMessageIdsRef.current.clear()

      try {
        if (isChannel && channelId !== undefined) {
          const { messages: list, has_more } = await fetchChannelMessages(channelId)
          if (cancelled) return
          setSortedMessages((prev: MessageType[] | null) => mergeMessagesById(prev, list))
          setHasMore(has_more)
          seenMessageIdsRef.current = new Set((list || []).map((m: any) => m.id))

          // Join channel room
          joinChannel(channelId)

          // Mark channel reply notifications as read for this channel
          try {
            // Only mark the channel_reply notifications for this channel
            await (await import('../services/notifications')).markNotificationsReadFiltered({ channel_id: Number(channelId), types: ['channel_reply'] })
          } catch (err) {
            console.warn('Failed to mark channel notifications as read:', err)
          }

        } else if (isDirect && convId !== undefined) {
          const { messages: list, has_more } = await fetchDirectConversationMessages(convId)
          if (cancelled) return
          setSortedMessages((prev: MessageType[] | null) => mergeMessagesById(prev, list))
          setHasMore(has_more)
          seenMessageIdsRef.current = new Set((list || []).map((m: any) => m.id))

          // Join DM room
          const room = `dm:${convId}`
          joinRoom(room)

          // Mark DM message notifications as read for this conversation
          try {
            await (await import('../services/notifications')).markNotificationsReadFiltered({ direct_conversation_id: Number(convId), types: ['dm_message'] })
          } catch (err) {
            console.warn('Failed to mark DM notifications as read:', err)
          }

        }

        // Subscribe to message:new events for this view
        const unsubscribeMessage = onSocketEvent<any>('message:new', (data) => {
          if (cancelled) return

          // Channel mode: require channel_id to match
          if (isChannel) {
            if (data.channel_id !== channelId) return
            if (data.parent_id) return
            if (data.author_id === currentUserId) return
            if (seenMessageIdsRef.current.has(data.id)) return
            seenMessageIdsRef.current.add(data.id)

            // Determine whether user is near bottom before adding
            const container = messagesContainerRef.current
            const isNearBottom = container ? (container.scrollHeight - container.scrollTop - container.clientHeight) < 80 : true

            setSortedMessages((prev: MessageType[] | null) => prev ? [...prev, data] : [data])

            if (isNearBottom) {
              shouldScrollToBottom.current = true
              // mark read will be handled by scroll handler shortly
            } else {
              // user scrolled up — show new messages indicator
              setNewMessagesCount(n => n + 1)
            }
            return
          }

          // Direct mode: require direct_conversation_id to match
          if (isDirect) {
            if (data.direct_conversation_id !== convId) return
            if (data.parent_id) return
            if (data.author_id === currentUserId) return
            if (seenMessageIdsRef.current.has(data.id)) return
            seenMessageIdsRef.current.add(data.id)

            const container = messagesContainerRef.current
            const isNearBottom = container ? (container.scrollHeight - container.scrollTop - container.clientHeight) < 80 : true

            setSortedMessages((prev: MessageType[] | null) => prev ? [...prev, data] : [data])

            if (isNearBottom) {
              shouldScrollToBottom.current = true
            } else {
              setNewMessagesCount(n => n + 1)
            }
            return
          }
        })

        const unsubscribeThread = onSocketEvent<any>('thread:reply', (data) => {
          if (cancelled) return
          // thread:reply usually includes channel_id; if present, filter similarly
          if (isChannel && data.channel_id !== channelId) return
          if (isDirect && data.direct_conversation_id !== convId) return

          // Promote parent message to bottom and highlight it briefly
          setMessages(prev => {
            if (!prev) return prev
            const idx = prev.findIndex(m => m.id === data.parent_id)
            if (idx === -1) return prev.map(m => m.id === data.parent_id ? { ...m, thread_count: (m.thread_count || 0) + 1 } : m)

            const parent = { ...prev[idx], thread_count: (prev[idx].thread_count || 0) + 1, _highlight: true }
            const next = [...prev.slice(0, idx), ...prev.slice(idx + 1), parent]

            // remove highlight after 1.6s
            setTimeout(() => setMessages(cur => cur && cur.map(msg => msg.id === parent.id ? { ...msg, _highlight: false } : msg)), 1600)
            return next
          })
        })

        const unsubscribeAttachment = onSocketEvent<any>('message:attachment_added', (data) => {
          if (cancelled) return
          if (isChannel && data.channel_id !== channelId) return
          if (isDirect && data.direct_conversation_id !== convId) return

          setMessages(prev => {
            if (!prev) return prev
            const messageExists = prev.some(m => m.id === data.message_id)
            if (!messageExists) {
              // Trigger refetch for missing messages
              if (isChannel && channelId !== undefined) fetchChannelMessages(channelId).then(({ messages: list }) => setMessages(p => mergeMessagesById(p, list)))
              if (isDirect && convId !== undefined) fetchDirectConversationMessages(convId).then(({ messages: list }) => setMessages(p => mergeMessagesById(p, list)))
              return prev
            }

            return prev.map(m => {
              if (m.id === data.message_id) {
                const existingAttachments = m.attachments || []
                if (existingAttachments.some((a: any) => a.id === data.id)) return m
                return { ...m, attachments: [...existingAttachments, data] }
              }
              return m
            })
          })
        })

        const unsubscribeReactionAdded = onSocketEvent<any>('message:reaction_added', (data) => {
          if (cancelled) return
          if (isChannel && data.channel_id !== channelId) return
          if (isDirect && data.direct_conversation_id !== convId) return
          setMessages(prev => prev && prev.map(m => {
            if (m.id !== data.message_id) return m
            const oldReactions = m.reactions || []
            const idx = oldReactions.findIndex((r: any) => r.emoji === data.emoji)
            let newReactions
            if (idx >= 0) {
              const r = oldReactions[idx]
              if (!r.users.includes(data.user_id)) {
                newReactions = [
                  ...oldReactions.slice(0, idx),
                  { ...r, count: r.count + 1, users: [...r.users, data.user_id] },
                  ...oldReactions.slice(idx + 1)
                ]
              } else {
                newReactions = oldReactions
              }
            } else {
              newReactions = [...oldReactions, { emoji: data.emoji, count: 1, users: [data.user_id] }]
            }
            return { ...m, reactions: newReactions }
          }))
        })

        const unsubscribeReactionRemoved = onSocketEvent<any>('message:reaction_removed', (data) => {
          if (cancelled) return
          if (isChannel && data.channel_id !== channelId) return
          if (isDirect && data.direct_conversation_id !== convId) return
          setMessages(prev => prev && prev.map(m => {
            if (m.id !== data.message_id) return m
            const oldReactions = m.reactions || []
            const idx = oldReactions.findIndex((r: any) => r.emoji === data.emoji)
            let newReactions = oldReactions
            if (idx >= 0) {
              const r = oldReactions[idx]
              const updatedUsers = r.users.filter((id: number) => id !== data.user_id)
              if (updatedUsers.length === 0) {
                newReactions = [...oldReactions.slice(0, idx), ...oldReactions.slice(idx + 1)]
              } else {
                newReactions = [...oldReactions.slice(0, idx), { ...r, count: updatedUsers.length, users: updatedUsers }, ...oldReactions.slice(idx + 1)]
              }
            }
            return { ...m, reactions: newReactions }
          }))
        })

        const unsubscribeUpdated = onSocketEvent<any>('message:updated', (data) => {
          if (cancelled) return
          if (isChannel && data.channel_id !== channelId) return
          if (isDirect && data.direct_conversation_id !== convId) return
          setMessages(prev => prev && prev.map((m: any) => m.id === data.id ? { ...m, content: data.content, is_edited: Boolean(data.is_edited), edited_at: data.edited_at } : m))
        })

        const unsubscribeDeleted = onSocketEvent<any>('message:deleted', (data) => {
          if (cancelled) return
          if (isChannel && data.channel_id !== channelId) return
          if (isDirect && data.direct_conversation_id !== convId) return
          setMessages(prev => prev && prev.map((m: any) => m.id === data.id ? { ...m, deleted: true, content: 'This message was deleted', reactions: [] } : m))
        })

        const unsubscribePinned = onSocketEvent<any>('message:pinned', (data) => {
          if (cancelled) return
          if (isChannel && data.channel_id !== channelId) return
          if (isDirect && data.direct_conversation_id !== convId) return
          setMessages(prev => prev && prev.map((m: any) => m.id === data.id ? { ...m, pinned: true } : m))
        })

        const unsubscribeUnpinned = onSocketEvent<any>('message:unpinned', (data) => {
          if (cancelled) return
          if (isChannel && data.channel_id !== channelId) return
          if (isDirect && data.direct_conversation_id !== convId) return
          setMessages(prev => prev && prev.map((m: any) => m.id === data.id ? { ...m, pinned: false } : m))
        })

        socketCleanup = () => {
          if (isChannel && channelId !== undefined) leaveChannel(channelId)
          if (isDirect && convId !== undefined) leaveRoom(`dm:${convId}`)
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

      } catch (err: any) {
        if (cancelled) return
        console.error('Failed to load messages', err)
        // If the backend returned 403, expose a specific forbidden state for the UI
        if (err?.response?.status === 403) {
          setMessagesError('forbidden')
        } else {
          setMessagesError('Failed to load messages')
        }
      } finally {
        if (cancelled) return
        setLoadingMessages(false)
      }
    }

    loadMessages()

    return () => {
      cancelled = true
      if (socketCleanup) socketCleanup()
    }
  }, [props, channelId, convId, isChannel, isDirect, currentUser?.id])

  // Scroll to bottom when new messages arrive (if appropriate)
  useEffect(() => {
    if (shouldScrollToBottom.current) {
      if (messagesEndRef.current && typeof messagesEndRef.current.scrollIntoView === 'function') {
        messagesEndRef.current.scrollIntoView({ behavior: 'smooth' })
      }
    }
  }, [messages, markAsReadIfAtBottom, isChannel])

  // Ensure composer autosize runs on mount and when channel/direct conversation changes
  useEffect(() => {
    adjustComposerHeight()
  }, [channelId, convId, adjustComposerHeight])

  // Open thread panel automatically when ?message={parent_id} present in URL
  const location = useLocation()
  useEffect(() => {
    const params = new URLSearchParams(location.search)
    const parentId = params.get('message') ? Number(params.get('message')) : null
    if (!parentId) return

    ;(async () => {
      try {
        // Try to find parent in loaded messages first
        let parent = messages?.find((m: any) => m.id === parentId)

        // If not found, fetch message from server
        if (!parent) {
          const res = await api.get(`/api/messages/${parentId}`)
          parent = res.data
          if (!parent) return
          // Merge parent into current messages so it appears in the list
          setSortedMessages((p: MessageType[] | null) => mergeMessagesById(p, [parent]))
        }

        // Ensure this parent belongs to this view (channel or direct)
        if (isChannel && parent.channel_id !== channelId) return
        if (isDirect && parent.direct_conversation_id !== convId) return

        setSelectedThread(parent)

        // Mark parent as read when thread is opened
        if (isChannel && channelId) {
          markChannelRead(Number(channelId), parent.id)
        } else if (isDirect && convId) {
          markDirectConversationRead(convId, parent.id)
        }

        // Scroll to and briefly highlight the parent message
        setTimeout(() => {
          const el = document.querySelector(`[data-message-id="${parentId}"]`) as HTMLElement | null
          if (!el) return
          if (typeof el.scrollIntoView === 'function') {
            el.scrollIntoView({ behavior: 'smooth', block: 'center' })
          }
          el.classList.add('ring-2', 'ring-blue-400', 'rounded-lg')
          setTimeout(() => el.classList.remove('ring-2', 'ring-blue-400', 'rounded-lg'), 1600)
        }, 100)
      } catch (err) {
        console.error('Failed to open thread from URL', err)
      }
    })()
  }, [messages, location.search, channelId, convId, isChannel, isDirect])

  // Mark as read on scroll and track whether user is near bottom
  useEffect(() => {
    const container = messagesContainerRef.current
    if (!container) return
    const handleScroll = () => {
      const isNear = (container.scrollHeight - container.scrollTop - container.clientHeight) < 80
      if (isNear) {
        // mark channel as read when user returns to bottom
        markAsReadIfAtBottom()
        setNewMessagesCount(0)
      }
    }
    container.addEventListener('scroll', handleScroll, { passive: true })
    return () => container.removeEventListener('scroll', handleScroll)
  }, [markAsReadIfAtBottom])

  // Typing subscription only for channel mode
  useEffect(() => {
    if (!isChannel || !channelId) return
    const numChannelId = Number(channelId)
    clearChannel(numChannelId)
    const unsubscribe = subscribeToTyping(
      numChannelId,
      (userId, username) => addTypingUser(numChannelId, userId, username),
      (userId, _username) => removeTypingUser(numChannelId, userId)
    )
    return () => {
      unsubscribe()
      clearChannel(numChannelId)
      emitTypingStop(numChannelId)
    }
  }, [isChannel, channelId, addTypingUser, removeTypingUser, clearChannel])

  // Typing subscription for direct mode (uses room-key-based typing map)
  useEffect(() => {
    if (!isDirect || !convId) return
    const numConvId = Number(convId)
    const roomKey = `dm:${numConvId}`
    // Clear any prior typing state for this room
    clearChannel(roomKey)
    const unsubscribe = subscribeToTypingDirect(
      numConvId,
      (userId, username) => addTypingUser(roomKey, userId, username),
      (userId, _username) => removeTypingUser(roomKey, userId)
    )
    return () => {
      unsubscribe()
      clearChannel(roomKey)
      emitTypingStopDirect(numConvId)
    }
  }, [isDirect, convId, addTypingUser, removeTypingUser, clearChannel])

  // Fetch initial read receipts for this channel (skip for DMs)
  useEffect(() => {
    if (isChannel && channelId) {
      fetchChannelReads(Number(channelId))
    } else if (isDirect && convId) {
      // Fetch DM reads and populate read store under dm:{id}
      fetchDirectConversationReads(Number(convId)).then((reads) => {
        useReadReceiptStore.getState().setInitialReads(`dm:${convId}`, reads as any)
      }).catch((err) => console.error('Failed to fetch DM reads:', err))
    }
  }, [isChannel, channelId, isDirect, convId])

  // Cleanup pending mark-read when leaving channel
  useEffect(() => {
    return () => {
      if (isChannel && channelId) clearPendingMarkRead()
    }
  }, [isChannel, channelId])

  // Fetch upload limits
  useEffect(() => {
    getUploadLimits().then(setUploadLimits).catch((err) => console.error('Failed to fetch upload limits:', err))
  }, [])

  // File helpers
  const generateFileId = () => `file-${Date.now()}-${Math.random().toString(36).slice(2, 9)}`

  const handleFileSelect = useCallback((files: FileList | null) => {
    if (!files || files.length === 0 || !uploadLimits) return
    const newFiles: StagedFile[] = []
    for (let i = 0; i < files.length; i++) {
      const file = files[i]
      const error = validateFile(file, uploadLimits)
      const stagedFile: StagedFile = { id: generateFileId(), file, error: error || undefined }
      if (!error && file.type.startsWith('image/')) {
        const reader = new FileReader()
        reader.onload = (e) => setStagedFiles(prev => prev.map(f => f.id === stagedFile.id ? { ...f, preview: e.target?.result as string } : f))
        reader.readAsDataURL(file)
      }
      newFiles.push(stagedFile)
    }
    setStagedFiles(prev => [...prev, ...newFiles])
  }, [uploadLimits])

  const removeStagedFile = useCallback((id: string) => setStagedFiles(prev => prev.filter(f => f.id !== id)), [])

  // Layout effect to restore scroll when older messages loaded
  useLayoutEffect(() => {
    if (scrollRestoreInfo.current && messagesContainerRef.current) {
      const container = messagesContainerRef.current
      const { scrollHeight: oldScrollHeight, scrollTop: oldScrollTop } = scrollRestoreInfo.current
      const newScrollHeight = container.scrollHeight
      container.scrollTop = newScrollHeight - oldScrollHeight + oldScrollTop
      scrollRestoreInfo.current = null
    }
  }, [messages])

  async function loadOlder() {
    if (!messages || messages.length === 0) return
    const container = messagesContainerRef.current
    if (container) {
      scrollRestoreInfo.current = { scrollHeight: container.scrollHeight, scrollTop: container.scrollTop }
    }
    shouldScrollToBottom.current = false
    setLoadingOlder(true)
    setMessagesError(null)
    try {
      const oldest = messages[0]
      const beforeId = oldest.id
      if (isChannel && channelId !== undefined) {
        const res = await fetchChannelMessages(Number(channelId), beforeId)
        setMessages(prev => prev ? [...res.messages, ...prev] : res.messages)
        setHasMore(res.has_more)
      } else if (isDirect && convId !== undefined) {
        const res = await fetchDirectConversationMessages(convId, beforeId)
        setMessages(prev => prev ? [...res.messages, ...prev] : res.messages)
        setHasMore(res.has_more)
      }
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
    const hasContent = newMessage.trim().length > 0
    const hasValidFiles = stagedFiles.some(f => !f.error && !('completed' in f && f.completed))
    if ((!hasContent && !hasValidFiles) || sending) return
    shouldScrollToBottom.current = true

    // For channel mode, use emit typing stop with channel id
    if (isChannel && channelId) emitTypingStop(Number(channelId))
    // For direct mode, stop typing as well
    if (isDirect && convId) emitTypingStopDirect(Number(convId))

    setSending(true)
    try {
      let messageId: number | undefined
      if (hasContent) {
        if (isChannel && channelId !== undefined) {
          const response = await api.post('/api/messages/', { content: newMessage.trim(), channel_id: Number(channelId) })
          const sentMessage = response.data
          setMessages(prev => prev ? [...prev, sentMessage] : [sentMessage])
          if (sentMessage?.id) seenMessageIdsRef.current.add(sentMessage.id)

          // Orders and automation handling preserved
          if (newMessage.trim().toLowerCase().startsWith('/order create') && sentMessage?.system === true && sentMessage?.content?.includes('Order created')) {
            useOrderStore.getState().handleOrderCreated({ order_id: parseInt(sentMessage.content.match(/ID:\s*(\d+)/)?.[1] || '0'), status: 'SUBMITTED' })
          }
          if (sentMessage?.system === true && newMessage.trim().startsWith('/')) {
            const eventData = parseAutomationEventFromResponse(sentMessage.content || '', currentUser?.username || 'unknown')
            if (eventData) useAutomationEventsStore.getState().addEvent(eventData)
          }

        } else if (isDirect && convId !== undefined) {
          const msg = await postDirectConversationMessage(convId, newMessage.trim())
          setMessages(prev => prev ? [...prev, msg] : [msg])
          if (msg?.id) seenMessageIdsRef.current.add(msg.id)
        }
        setNewMessage('')
        // Reset composer height after clearing
        adjustComposerHeight()
      }

      // Handle file uploads for channels and direct conversations
      const validFiles = stagedFiles.filter(f => !f.error && !('completed' in f && f.completed))
      if (validFiles.length > 0 && ((isChannel && channelId !== undefined) || (isDirect && convId !== undefined))) {
        setStagedFiles(prev => prev.map(f => validFiles.some(vf => vf.id === f.id) ? { ...f, uploading: true, progress: 0, completed: false } as UploadingFile : f ))
        const isFileOnlyUpload = !hasContent
        let fileOnlyMessageId: number | undefined
        for (const stagedFile of validFiles) {
          try {
            const response = await uploadFile(
              stagedFile.file,
              isChannel ? Number(channelId!) : 0,
              messageId,
              (progress: UploadProgress) => {
                setStagedFiles(prev => prev.map(f => f.id === stagedFile.id ? { ...f, progress: progress.percentage } as UploadingFile : f))
              },
              isDirect ? convId : undefined
            )
            if (isFileOnlyUpload && response?.message_id) {
              fileOnlyMessageId = response.message_id
              if (fileOnlyMessageId) seenMessageIdsRef.current.add(fileOnlyMessageId)
            }
            setStagedFiles(prev => prev.map(f => f.id === stagedFile.id ? { ...f, uploading: false, completed: true, progress: 100 } as UploadingFile : f))
          } catch (err) {
            const error = err instanceof Error ? err.message : 'Upload failed'
            setStagedFiles(prev => prev.map(f => f.id === stagedFile.id ? { ...f, uploading: false, error, progress: 0, completed: false } as UploadingFile : f))
          }
        }
        if (isFileOnlyUpload && fileOnlyMessageId) {
          try {
            const msgResponse = await api.get(`/api/messages/${fileOnlyMessageId}`)
            const fileMessage = msgResponse.data
            if (fileMessage) setMessages(prev => prev ? [...prev, fileMessage] : [fileMessage])
          } catch (err) {
            console.error('Failed to fetch file-only message:', err)
            if (channelId !== undefined) fetchChannelMessages(Number(channelId)).then(({ messages: list }) => setSortedMessages((prev: MessageType[] | null) => mergeMessagesById(prev, list)))
            else if (isDirect && convId !== undefined) fetchDirectConversationMessages(convId).then(({ messages: list }) => setSortedMessages((prev: MessageType[] | null) => mergeMessagesById(prev, list)))
          }
        }
        setTimeout(() => setStagedFiles(prev => prev.filter(f => !('completed' in f && f.completed))), 500)
      }

    } catch (err) {
      console.error('Failed to send message', err)
    } finally {
      setSending(false)
    }
  }

  const handleToggleReaction = async (messageId: number, emoji: string) => {
    if (!currentUser) return
    setMessages(prev => prev && prev.map(m => {
      if (m.id !== messageId) return m
      const oldReactions = m.reactions || []
      const idx = oldReactions.findIndex((r: any) => r.emoji === emoji)
      let newReactions
      if (idx >= 0) {
        const r = oldReactions[idx]
        const updatedUsers = r.users.filter((id: number) => id !== currentUser.id)
        if (updatedUsers.length === 0) {
          newReactions = [...oldReactions.slice(0, idx), ...oldReactions.slice(idx + 1)]
        } else {
          newReactions = [...oldReactions.slice(0, idx), { ...r, count: updatedUsers.length, users: updatedUsers }, ...oldReactions.slice(idx + 1)]
        }
      } else {
        newReactions = [...oldReactions, { emoji, count: 1, users: [currentUser.id] }]
      }
      return { ...m, reactions: newReactions }
    }))

    try {
      const res = await toggleReaction(messageId, emoji)
      setMessages(prev => prev && prev.map(m => m.id === messageId ? { ...m, reactions: res.reactions } : m))
    } catch (err) {
      // rollback could be implemented by refetching
    }
  }

  if ((isChannel && channelId === undefined) || (isDirect && convId === undefined)) {
    return <div />
  }

  return (
    <div className="flex h-full min-h-0">
      {/* MESSAGE COLUMN */}
      <div className={`flex flex-col min-h-0 ${isThreadOpen ? "flex-1" : "flex-1"}`}>
        <div ref={messagesContainerRef} className="flex-1 min-h-0 overflow-y-auto p-4 pb-24">
          {loadingMessages && <div className="text-gray-400">Loading messages…</div>}
          {messagesError === 'forbidden' && (
            <div className="text-center text-red-400 py-10">
              🔒 You do not have access to this channel.
            </div>
          )}

          {messagesError && messagesError !== 'forbidden' && (
            <div className="text-red-500">{messagesError}</div>
          )}

          {!loadingMessages && !messagesError && messages && messages.length === 0 && (
            <div className="text-gray-500 text-center py-8">No messages yet. Start the conversation!</div>
          )}

          {!loadingMessages && !messagesError && messages && messages.length > 0 && (
            <>
              {hasMore && (
                <div className="mb-4 text-center">
                  <button className="px-4 py-2 bg-gray-700 hover:bg-gray-600 rounded text-sm transition-colors" onClick={loadOlder} disabled={loadingOlder}>{loadingOlder ? 'Loading…' : 'Load older messages'}</button>
                </div>
              )}

              {/* New messages indicator when user is scrolled up */}
              {newMessagesCount > 0 && (
                <div className="fixed left-1/2 transform -translate-x-1/2 bottom-28 z-40">
                  <button onClick={() => {
                    if (messagesEndRef.current) messagesEndRef.current.scrollIntoView({ behavior: 'smooth' })
                    setNewMessagesCount(0)
                    // mark as read when user clicks
                    if (isChannel && channelId) {
                      const topLevel = messages?.filter(m => !m.parent_id) || []
                      const lastId = topLevel.length ? topLevel[topLevel.length - 1].id : undefined
                      if (lastId) markChannelRead(Number(channelId), lastId)
                    } else if (isDirect && convId) {
                      const topLevel = messages?.filter(m => !m.parent_id) || []
                      const lastId = topLevel.length ? topLevel[topLevel.length - 1].id : undefined
                      if (lastId) markDirectConversationRead(convId, lastId)
                    }
                  }} className="bg-blue-600 text-white px-4 py-2 rounded-full shadow-lg">New Messages ↓</button>
                </div>
              )}

              <div className="space-y-3">
                {messages.filter(m => !m.parent_id).map((m: any) => {
                  const roomKey = isChannel ? Number(channelId) : `dm:${convId}`
                  const reads = getChannelReads(roomKey)
                  const lastRead = currentUser ? (reads[currentUser.id] || 0) : 0
                  const isUnread = m.id > lastRead
                  return (
                    <Message
                      key={m.id}
                      message={{ ...m, author_username: m.author_username }}
                      onClick={setSelectedThread}
                      onToggleReaction={handleToggleReaction}
                      currentUser={currentUser}
                      canPin={true}
                      onUpdate={(updated: any) => setMessages(prev => prev && prev.map(pm => pm.id === updated.id ? { ...pm, ...updated } : pm))}
                      is_unread={isUnread}
                    />
                  )
                })}
              </div>

              {/* Seen by for channel messages */}
              {isChannel && (() => {
                const topLevelMessages = messages.filter(m => !m.parent_id)
                if (topLevelMessages.length === 0) return null
                const lastMessage = topLevelMessages[topLevelMessages.length - 1]
                if (lastMessage.author_id !== currentUser?.id) return null
                const readByUserIds = getUsersWhoReadMessage(Number(channelId), lastMessage.id, currentUser?.id)
                if (readByUserIds.length === 0) return null
                const usernames = readByUserIds.map(uid => (props.memberUsernames && props.memberUsernames[uid]) ? props.memberUsernames[uid] : '')
                const seenText = formatSeenBy(usernames)
                if (!seenText) return null
                return (<div className="text-xs text-gray-500 text-right mt-1 pr-2">{seenText}</div>)
              })()}

              {/* Seen by for direct messages */}
              {isDirect && (() => {
                const topLevelMessages = messages.filter(m => !m.parent_id)
                if (topLevelMessages.length === 0) return null
                const lastMessage = topLevelMessages[topLevelMessages.length - 1]
                if (lastMessage.author_id !== currentUser?.id) return null
                const readByUserIds = getUsersWhoReadMessage(`dm:${convId}`, lastMessage.id, currentUser?.id)
                if (readByUserIds.length === 0) return null
                const usernames = readByUserIds.map(uid => (props.memberUsernames && props.memberUsernames[uid]) ? props.memberUsernames[uid] : '')
                const seenText = formatSeenBy(usernames)
                if (!seenText) return null
                return (<div className="text-xs text-gray-500 text-right mt-1 pr-2">{seenText}</div>)
              })()}

              <div ref={messagesEndRef} />
            </>
          )}
        </div>

        {/* COMPOSER */}
        <div className="border-t shrink-0 border-gray-700">
          {stagedFiles.length > 0 && (
            <AttachmentPreview files={stagedFiles} onRemove={removeStagedFile} disabled={sending} />
          )}

          <div className="p-4">
            {(() => {
              let typingUsers = [] as any
              if (isChannel && channelId) {
                typingUsers = getTypingUsers(Number(channelId))
              } else if (isDirect && convId) {
                typingUsers = getTypingUsers(`dm:${convId}`)
              }
              const text = formatTypingIndicator(typingUsers)
              if (!text) return null
              return (<div className="text-sm text-gray-400 mb-2 animate-pulse">{text}</div>)
            })()}

            <form onSubmit={handleSendMessage} className="flex gap-2">
              <button type="button" onClick={() => fileInputRef.current?.click()} className="px-3 py-2 bg-gray-700 hover:bg-gray-600 rounded-lg transition-colors" title={isChannel ? 'Attach files' : 'Attach files to this conversation'} disabled={sending}>
                <Paperclip size={18} className="text-gray-400" />
              </button>
              <input ref={fileInputRef} type="file" multiple className="hidden" onChange={(e) => { handleFileSelect(e.target.files); if (e.target) e.target.value = '' }} accept={uploadLimits?.allowed_mime_types?.join(',') || '*/*'} />

              <div className="relative flex items-center">
                <EmojiPickerTrigger ref={emojiTriggerRef} onClick={() => setEmojiOpen(true)} />
                <EmojiPickerPopover anchorRef={emojiTriggerRef} open={emojiOpen} onClose={() => setEmojiOpen(false)} onSelect={(emoji) => { setNewMessage(prev => prev + emoji); setEmojiOpen(false); setTimeout(() => inputRef.current?.focus(), 0) }} />
              </div>

              <textarea
                value={newMessage}
                onChange={(e) => {
                  const v = e.target.value
                  setNewMessage(v)
                  adjustComposerHeight(e.target)
                  if (isChannel && channelId) {
                    if (v.trim()) { emitTypingStart(Number(channelId)) } else { emitTypingStop(Number(channelId)) }
                  } else if (isDirect && convId) {
                    if (v.trim()) { emitTypingStartDirect(Number(convId)) } else { emitTypingStopDirect(Number(convId)) }
                  }
                }}
                placeholder="Type a message..."
                className="flex-1 px-4 py-2 bg-gray-700 rounded-lg text-white placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500 resize-none overflow-hidden"
                disabled={sending}
                ref={inputRef}
                rows={1}
              />

              <button type="submit" disabled={(!newMessage.trim() && stagedFiles.filter(f => !f.error).length === 0) || sending} className="px-4 py-2 bg-blue-600 hover:bg-blue-500 disabled:bg-gray-600 disabled:cursor-not-allowed rounded-lg transition-colors flex items-center gap-2"><Send size={18} />{sending ? 'Sending…' : 'Send'}</button>
            </form>
          </div>
        </div>
      </div>

      {/* THREAD PANEL (RIGHT SIDE) */}
      {isThreadOpen && (
        <div className="w-[480px] flex flex-col min-h-0 border-l border-gray-700">
          <ThreadPanel parentMessage={selectedThread} onClose={() => setSelectedThread(null)} />
        </div>
      )}
    </div>
  )
}
