/**
 * Typing indicator realtime subscriptions.
 * Phase 4.3 - Track who is typing in each channel.
 */
import { getSocket } from './socket';

// Debounce timer for emit throttling
let typingDebounceTimer: ReturnType<typeof setTimeout> | null = null;

// Idle timer - stop typing after inactivity
let typingIdleTimer: ReturnType<typeof setTimeout> | null = null;

// Current room key we're tracking typing for (e.g., "channel:1" or "dm:1")
let currentTypingRoomKey: string | null = null;

// Debounce interval (ms) - don't spam server
const TYPING_DEBOUNCE_MS = 500;

// Idle timeout (ms) - stop typing if no keystrokes
const TYPING_IDLE_MS = 2500;

/**
 * Emit typing start event (debounced).
 * Call this on every keystroke in the message input.
 */
export function emitTypingStart(channelId: number): void {
  const socket = getSocket();
  if (!socket?.connected) return;
  
  // Clear idle timer - user is still typing
  if (typingIdleTimer) {
    clearTimeout(typingIdleTimer);
  }
  
  // Set up idle timer to auto-stop
  typingIdleTimer = setTimeout(() => {
    emitTypingStop(channelId);
  }, TYPING_IDLE_MS);
  
  // Skip if we're already tracking this room and within debounce window
  const roomKey = `channel:${channelId}`;
  if (currentTypingRoomKey === roomKey && typingDebounceTimer) {
    return;
  }
  
  // Update current room key
  currentTypingRoomKey = roomKey;
  
  // Clear previous debounce timer
  if (typingDebounceTimer) {
    clearTimeout(typingDebounceTimer);
  }
  
  // Emit immediately on first keystroke
  socket.emit('typing_start', { channel_id: channelId });
  
  // Set debounce timer to prevent spam
  typingDebounceTimer = setTimeout(() => {
    typingDebounceTimer = null;
  }, TYPING_DEBOUNCE_MS);
}

// Direct conversation typing helpers
export function emitTypingStartDirect(convId: number): void {
  const socket = getSocket();
  if (!socket?.connected) return;

  // Clear idle timer - reuse same timers to avoid extra complexity
  if (typingIdleTimer) {
    clearTimeout(typingIdleTimer);
  }

  typingIdleTimer = setTimeout(() => {
    emitTypingStopDirect(convId);
  }, TYPING_IDLE_MS);

  const roomKey = `dm:${convId}`;
  if (currentTypingRoomKey === roomKey && typingDebounceTimer) {
    return;
  }

  currentTypingRoomKey = roomKey;
  if (typingDebounceTimer) {
    clearTimeout(typingDebounceTimer);
  }

  socket.emit('typing_start', { direct_conversation_id: convId });

  typingDebounceTimer = setTimeout(() => {
    typingDebounceTimer = null;
  }, TYPING_DEBOUNCE_MS);
}

export function emitTypingStopDirect(convId: number): void {
  const socket = getSocket();

  if (typingDebounceTimer) {
    clearTimeout(typingDebounceTimer);
    typingDebounceTimer = null;
  }
  if (typingIdleTimer) {
    clearTimeout(typingIdleTimer);
    typingIdleTimer = null;
  }

  const roomKey = `dm:${convId}`;
  if (currentTypingRoomKey === roomKey) {
    currentTypingRoomKey = null;
    if (socket?.connected) {
      socket.emit('typing_stop', { direct_conversation_id: convId });
    }
  }
}

export function subscribeToTypingDirect(
  convId: number,
  onTypingStart: (userId: number, username: string) => void,
  onTypingStop: (userId: number, username: string) => void
): () => void {
  const socket = getSocket();
  if (!socket) return () => {};

  const handleTypingStart = (data: { user_id: number; username: string; direct_conversation_id?: number }) => {
    if (data.direct_conversation_id === convId) {
      onTypingStart(data.user_id, data.username);
    }
  };

  const handleTypingStop = (data: { user_id: number; username: string; direct_conversation_id?: number }) => {
    if (data.direct_conversation_id === convId) {
      onTypingStop(data.user_id, data.username);
    }
  };

  socket.on('typing:start', handleTypingStart);
  socket.on('typing:stop', handleTypingStop);

  return () => {
    socket.off('typing:start', handleTypingStart);
    socket.off('typing:stop', handleTypingStop);
  };
}

/**
 * Emit typing stop event.
 * Call this when:
 * - User sends a message
 * - User clears the input
 * - User leaves the channel
 */
export function emitTypingStop(channelId: number): void {
  const socket = getSocket();
  
  // Clear timers
  if (typingDebounceTimer) {
    clearTimeout(typingDebounceTimer);
    typingDebounceTimer = null;
  }
  if (typingIdleTimer) {
    clearTimeout(typingIdleTimer);
    typingIdleTimer = null;
  }
  
  const roomKey = `channel:${channelId}`;
  // Only emit if we were tracking this room
  if (currentTypingRoomKey === roomKey) {
    currentTypingRoomKey = null;
    if (socket?.connected) {
      socket.emit('typing_stop', { channel_id: channelId });
    }
  }
}

/**
 * Subscribe to typing events for a channel.
 * Returns unsubscribe function.
 */
export function subscribeToTyping(
  channelId: number,
  onTypingStart: (userId: number, username: string) => void,
  onTypingStop: (userId: number, username: string) => void
): () => void {
  const socket = getSocket();
  if (!socket) return () => {};
  
  const handleTypingStart = (data: { user_id: number; username: string; channel_id: number }) => {
    if (data.channel_id === channelId) {
      onTypingStart(data.user_id, data.username);
    }
  };
  
  const handleTypingStop = (data: { user_id: number; username: string; channel_id: number }) => {
    if (data.channel_id === channelId) {
      onTypingStop(data.user_id, data.username);
    }
  };
  
  socket.on('typing:start', handleTypingStart);
  socket.on('typing:stop', handleTypingStop);
  
  return () => {
    socket.off('typing:start', handleTypingStart);
    socket.off('typing:stop', handleTypingStop);
  };
}

/**
 * Clear all typing state.
 * Call when disconnecting or switching teams.
 */
export function clearTypingState(): void {
  if (typingDebounceTimer) {
    clearTimeout(typingDebounceTimer);
    typingDebounceTimer = null;
  }
  if (typingIdleTimer) {
    clearTimeout(typingIdleTimer);
    typingIdleTimer = null;
  }
  currentTypingRoomKey = null;
}
