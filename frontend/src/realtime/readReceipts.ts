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
  
  socket.on('receipt:update', handleReceiptUpdate);
  
  return () => {
    socket.off('receipt:update', handleReceiptUpdate);
  };
}

/**
 * Fetch initial read receipts for a channel.
 * Call when entering a channel.
 */
export async function fetchChannelReads(channelId: number): Promise<void> {
  try {
    const response = await api.get(`/channels/${channelId}/reads`);
    const reads = response.data as Array<{ user_id: number; last_read_message_id: number | null }>;
    
    useReadReceiptStore.getState().setInitialReads(channelId, reads);
  } catch (error) {
    console.error('Failed to fetch channel reads:', error);
  }
}

/**
 * Mark a channel as read up to a specific message.
 * Debounced to avoid spam on scroll.
 */
export function markChannelRead(channelId: number, lastReadMessageId: number): void {
  // Skip if we're already pending the same or higher message
  if (
    pendingMarkRead &&
    pendingMarkRead.channelId === channelId &&
    pendingMarkRead.messageId >= lastReadMessageId
  ) {
    return;
  }
  
  // Update pending
  pendingMarkRead = { channelId, messageId: lastReadMessageId };
  
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
      await api.post(`/channels/${pending.channelId}/read`, {
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
