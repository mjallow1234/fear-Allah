/**
 * Read receipt realtime subscriptions.
 * Phase 4.4 - Subscribe to receipt:update events.
 */
import { getSocket } from './socket';
import { useReadReceiptStore } from '../stores/readReceiptStore';
import { useAuthStore } from '../stores/authStore';
import api from '../services/api';

// Debounce timer for mark-as-read calls
let markReadDebounceTimer: ReturnType<typeof setTimeout> | null = null;
const MARK_READ_DEBOUNCE_MS = 500;

// Track pending mark-read calls to avoid duplicates
let pendingMarkRead: { channelId: number; messageId: number } | null = null;

/**
 * Subscribe to read receipt updates.
 * Call this once when authenticated.
 * Returns unsubscribe function.
 */
export function subscribeToReadReceipts(): () => void {
  const socket = getSocket();
  if (!socket) return () => {};
  
  const handleReceiptUpdate = (data: {
    channel_id: number;
    user_id: number;
    last_read_message_id: number;
  }) => {
    // Skip our own updates (we already updated optimistically)
    const currentUserId = useAuthStore.getState().user?.id;
    if (data.user_id === currentUserId) {
      return;
    }
    
    // Update store (store handles ignoring lower values)
    useReadReceiptStore.getState().updateRead(
      data.channel_id,
      data.user_id,
      data.last_read_message_id
    );
  };

  const handleDirectReceiptUpdate = (data: { direct_conversation_id: number; user_id: number; last_read_message_id: number | null }) => {
    const currentUserId = useAuthStore.getState().user?.id;
    if (data.user_id === currentUserId) return;
    useReadReceiptStore.getState().updateRead(`dm:${data.direct_conversation_id}`, data.user_id, data.last_read_message_id || 0);
  }
  
  socket.on('receipt:update', handleReceiptUpdate);
  socket.on('direct:read_updated', handleDirectReceiptUpdate);
  
  return () => {
    socket.off('receipt:update', handleReceiptUpdate);
    socket.off('direct:read_updated', handleDirectReceiptUpdate);
  };
}

/**
 * Fetch initial read receipts for a channel.
 * Call when entering a channel.
 * @param channelType - Optional channel type. If 'direct', skip the fetch (DMs don't support read receipts).
 */
export async function fetchChannelReads(channelId: number, channelType?: string): Promise<void> {
  // Skip read receipts for DM channels (not supported)
  if (channelType === 'direct') {
    return;
  }

  try {
    const response = await api.get(`/api/channels/${channelId}/reads`);
    const reads = response.data as Array<{ user_id: number; last_read_message_id: number | null }>;
    
    useReadReceiptStore.getState().setInitialReads(channelId, reads);
  } catch (error) {
    console.error('Failed to fetch channel reads:', error);
  }
}

/**
 * Mark a channel as read up to a specific message.
 * Debounced to avoid spam on scroll.
 * @param lastMessageId - Optional message ID. If not provided or invalid, skip the API call.
 * @param channelType - Optional channel type. If 'direct', skip the API call (DMs don't support read receipts).
 */
export function markChannelRead(channelId: number, lastMessageId?: number, channelType?: string): void {
  // Skip read receipts for DM channels (not supported)
  if (channelType === 'direct') {
    return;
  }

  // Skip if no valid message ID provided
  if (!lastMessageId || typeof lastMessageId !== 'number' || lastMessageId <= 0) {
    return;
  }

  // Skip if no valid channel ID
  if (!channelId || typeof channelId !== 'number' || channelId <= 0) {
    return;
  }

  // Skip if we're already pending the same or higher message
  if (
    pendingMarkRead &&
    pendingMarkRead.channelId === channelId &&
    pendingMarkRead.messageId >= lastMessageId
  ) {
    return;
  }
  
  // Update pending
  pendingMarkRead = { channelId, messageId: lastMessageId };
  
  // Clear existing timer
  if (markReadDebounceTimer) {
    clearTimeout(markReadDebounceTimer);
  }
  
  // Debounce the API call
  markReadDebounceTimer = setTimeout(async () => {
    const pending = pendingMarkRead;
    if (!pending) return;
    
    // Get current user ID for optimistic update
    const currentUserId = useAuthStore.getState().user?.id;
    
    try {
      await api.post(`/api/channels/${pending.channelId}/read`, {
        last_read_message_id: pending.messageId,
      });
      
      // Optimistically update local store with actual user ID
      if (currentUserId) {
        useReadReceiptStore.getState().updateRead(
          pending.channelId,
          currentUserId,
          pending.messageId
        );
      }

      // Also notify UI to refresh channel list immediately (server is authoritative)
      try {
        window.dispatchEvent(new CustomEvent('channels:refetch', { detail: { channel_id: pending.channelId } }))
      } catch (err) {
        /* ignore - non-browser environments */
      }
    } catch (error) {
      console.error('Failed to mark channel as read:', error);
    } finally {
      // Clear pending if it matches what we just sent
      if (
        pendingMarkRead &&
        pendingMarkRead.channelId === pending.channelId &&
        pendingMarkRead.messageId === pending.messageId
      ) {
        pendingMarkRead = null;
      }
    }
  }, MARK_READ_DEBOUNCE_MS);
}

/**
 * Clear pending mark-read state.
 * Call when leaving a channel.
 */
export function clearPendingMarkRead(): void {
  if (markReadDebounceTimer) {
    clearTimeout(markReadDebounceTimer);
    markReadDebounceTimer = null;
  }
  pendingMarkRead = null;
}

/**
 * Fetch direct conversation reads for a DM
 */
export async function fetchDirectConversationReads(convId: number): Promise<Array<{ user_id: number; last_read_message_id: number | null }>> {
  try {
    const response = await api.get(`/api/direct-conversations/${convId}/reads`)
    return Array.isArray(response.data) ? response.data : []
  } catch (err) {
    console.error('Failed to fetch direct conversation reads:', err)
    return []
  }
}

/**
 * Mark a direct conversation read up to a message (no debounce)
 */
export async function markDirectConversationRead(convId: number, lastMessageId?: number): Promise<void> {
  if (!lastMessageId || lastMessageId <= 0) return
  try {
    await api.post(`/api/direct-conversations/${convId}/read`, { last_read_message_id: lastMessageId })
    // Optimistically update local store
    useReadReceiptStore.getState().updateRead(`dm:${convId}`, useAuthStore.getState().user?.id || 0, lastMessageId)
  } catch (err) {
    console.error('Failed to mark direct conversation read:', err)
  }
}
