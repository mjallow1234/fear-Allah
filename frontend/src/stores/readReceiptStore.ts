/**
 * Read receipt state store.
 * Phase 4.4 - Track who has read messages in each channel.
 */
import { create } from 'zustand';

interface ReadReceiptStore {
  // channelId -> { userId -> lastReadMessageId }
  readsByChannel: Record<number, Record<number, number>>;
  
  /**
   * Set initial reads when entering a channel (from REST API).
   */
  setInitialReads: (channelId: number, reads: Array<{ user_id: number; last_read_message_id: number | null }>) => void;
  
  /**
   * Update a single read receipt (from socket event).
   * Only updates if new value > existing.
   */
  updateRead: (channelId: number, userId: number, lastReadMessageId: number) => void;
  
  /**
   * Get all reads for a channel.
   */
  getChannelReads: (channelId: number) => Record<number, number>;
  
  /**
   * Get users who have read up to or past a specific message.
   * Excludes the specified user (typically current user).
   */
  getUsersWhoReadMessage: (channelId: number, messageId: number, excludeUserId?: number) => number[];
  
  /**
   * Clear reads for a channel.
   */
  clearChannel: (channelId: number) => void;
  
  /**
   * Clear all reads.
   */
  clearAll: () => void;
}

export const useReadReceiptStore = create<ReadReceiptStore>((set, get) => ({
  readsByChannel: {},
  
  setInitialReads: (channelId: number, reads: Array<{ user_id: number; last_read_message_id: number | null }>) => {
    const readsMap: Record<number, number> = {};
    
    for (const read of reads) {
      if (read.last_read_message_id !== null) {
        readsMap[read.user_id] = read.last_read_message_id;
      }
    }
    
    set((state) => ({
      readsByChannel: {
        ...state.readsByChannel,
        [channelId]: readsMap,
      },
    }));
  },
  
  updateRead: (channelId: number, userId: number, lastReadMessageId: number) => {
    set((state) => {
      const channelReads = state.readsByChannel[channelId] || {};
      const existing = channelReads[userId];
      
      // Only update if new value is greater
      if (existing !== undefined && lastReadMessageId <= existing) {
        return state;
      }
      
      return {
        readsByChannel: {
          ...state.readsByChannel,
          [channelId]: {
            ...channelReads,
            [userId]: lastReadMessageId,
          },
        },
      };
    });
  },
  
  getChannelReads: (channelId: number) => {
    return get().readsByChannel[channelId] || {};
  },
  
  getUsersWhoReadMessage: (channelId: number, messageId: number, excludeUserId?: number) => {
    const channelReads = get().readsByChannel[channelId] || {};
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
  
  clearChannel: (channelId: number) => {
    set((state) => {
      const newReads = { ...state.readsByChannel };
      delete newReads[channelId];
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
