/**
 * Read receipt state store.
 * Phase 4.4 - Track who has read messages in each channel.
 */
import { create } from 'zustand';

interface ReadReceiptStore {
  // roomKey -> { userId -> lastReadMessageId } where roomKey is a number (channel id) or string like "dm:{id}"
  readsByChannel: Record<string, Record<number, number>>;
  
  /**
   * Set initial reads when entering a room (channel or DM) (from REST API).
   */
  setInitialReads: (roomKey: string | number, reads: Array<{ user_id: number; last_read_message_id: number | null }>) => void;
  
  /**
   * Update a single read receipt (from socket event).
   * Only updates if new value > existing.
   */
  updateRead: (roomKey: string | number, userId: number, lastReadMessageId: number) => void;
  
  /**
   * Get all reads for a room.
   */
  getChannelReads: (roomKey: string | number) => Record<number, number>;
  
  /**
   * Get users who have read up to or past a specific message.
   * Excludes the specified user (typically current user).
   */
  getUsersWhoReadMessage: (roomKey: string | number, messageId: number, excludeUserId?: number) => number[];
  
  /**
   * Clear reads for a room.
   */
  clearChannel: (roomKey: string | number) => void;
  
  /**
   * Clear all reads.
   */
  clearAll: () => void;
}

export const useReadReceiptStore = create<ReadReceiptStore>((set, get) => ({
  readsByChannel: {},
  
  setInitialReads: (roomKey: string | number, reads: Array<{ user_id: number; last_read_message_id: number | null }>) => {
    const key = typeof roomKey === 'number' ? String(roomKey) : roomKey;
    const readsMap: Record<number, number> = {};
    
    for (const read of reads) {
      if (read.last_read_message_id !== null) {
        readsMap[read.user_id] = read.last_read_message_id;
      }
    }
    
    set((state) => ({
      readsByChannel: {
        ...state.readsByChannel,
        [key]: readsMap,
      },
    }));
  },
  
  updateRead: (roomKey: string | number, userId: number, lastReadMessageId: number) => {
    const key = typeof roomKey === 'number' ? String(roomKey) : roomKey;
    set((state) => {
      const channelReads = state.readsByChannel[key] || {};
      const existing = channelReads[userId];
      
      // Only update if new value is greater
      if (existing !== undefined && lastReadMessageId <= existing) {
        return state;
      }
      
      return {
        readsByChannel: {
          ...state.readsByChannel,
          [key]: {
            ...channelReads,
            [userId]: lastReadMessageId,
          },
        },
      };
    });
  },
  
  getChannelReads: (roomKey: string | number) => {
    const key = typeof roomKey === 'number' ? String(roomKey) : roomKey;
    return get().readsByChannel[key] || {};
  },
  
  getUsersWhoReadMessage: (roomKey: string | number, messageId: number, excludeUserId?: number) => {
    const key = typeof roomKey === 'number' ? String(roomKey) : roomKey;
    const channelReads = get().readsByChannel[key] || {};
    const users: number[] = [];
    
    for (const [userIdStr, lastReadId] of Object.entries(channelReads)) {
      const userId = Number(userIdStr);
      
      // Skip excluded user
      if (excludeUserId !== undefined && userId === excludeUserId) {
        continue;
      }
      
      // Include if they've read this message or beyond
      if (lastReadId >= messageId) {
        users.push(userId);
      }
    }
    
    return users;
  },
  
  clearChannel: (roomKey: string | number) => {
    const key = typeof roomKey === 'number' ? String(roomKey) : roomKey;
    set((state) => {
      const newReads = { ...state.readsByChannel };
      delete newReads[key];
      return { readsByChannel: newReads };
    });
  },
  
  clearAll: () => {
    set({ readsByChannel: {} });
  },
}));

/**
 * Format "Seen by X" text.
 * @param usernames - Array of usernames who have seen the message
 * @returns Formatted string or null if no one has seen it
 */
export function formatSeenBy(usernames: string[]): string | null {
  if (usernames.length === 0) return null;
  
  if (usernames.length === 1) {
    return `Seen by ${usernames[0]}`;
  }
  
  if (usernames.length === 2) {
    return `Seen by ${usernames[0]} and ${usernames[1]}`;
  }
  
  // 3+ users
  return `Seen by ${usernames.length} people`;
}
