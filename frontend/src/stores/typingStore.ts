/**
 * Typing indicator state store.
 * Phase 4.3 - Track who is typing in each channel.
 */
import { create } from 'zustand';

interface TypingUser {
  userId: number;
  username: string;
  startedAt: number;
}

interface TypingStore {
  // channelId -> list of typing users
  typingByChannel: Record<number, TypingUser[]>;
  
  // Actions
  addTypingUser: (channelId: number, userId: number, username: string) => void;
  removeTypingUser: (channelId: number, userId: number) => void;
  getTypingUsers: (channelId: number) => TypingUser[];
  clearChannel: (channelId: number) => void;
  clearAll: () => void;
}

// Auto-expire typing after this many ms (client-side safety)
const TYPING_EXPIRE_MS = 5000;

export const useTypingStore = create<TypingStore>((set, get) => ({
  typingByChannel: {},
  
  addTypingUser: (channelId: number, userId: number, username: string) => {
    set((state) => {
      const existing = state.typingByChannel[channelId] || [];
      
      // Check if user already in list
      const existingIndex = existing.findIndex(u => u.userId === userId);
      
      const newUser: TypingUser = {
        userId,
        username,
        startedAt: Date.now(),
      };
      
      let updated: TypingUser[];
      if (existingIndex >= 0) {
        // Update timestamp
        updated = [...existing];
        updated[existingIndex] = newUser;
      } else {
        // Add new user
        updated = [...existing, newUser];
      }
      
      return {
        typingByChannel: {
          ...state.typingByChannel,
          [channelId]: updated,
        },
      };
    });
    
    // Auto-expire after timeout (safety in case stop event is missed)
    setTimeout(() => {
      const current = get().typingByChannel[channelId] || [];
      const user = current.find(u => u.userId === userId);
      if (user && Date.now() - user.startedAt >= TYPING_EXPIRE_MS - 100) {
        get().removeTypingUser(channelId, userId);
      }
    }, TYPING_EXPIRE_MS);
  },
  
  removeTypingUser: (channelId: number, userId: number) => {
    set((state) => {
      const existing = state.typingByChannel[channelId] || [];
      const filtered = existing.filter(u => u.userId !== userId);
      
      if (filtered.length === existing.length) {
        // No change
        return state;
      }
      
      const newByChannel = { ...state.typingByChannel };
      if (filtered.length === 0) {
        delete newByChannel[channelId];
      } else {
        newByChannel[channelId] = filtered;
      }
      
      return { typingByChannel: newByChannel };
    });
  },
  
  getTypingUsers: (channelId: number) => {
    return get().typingByChannel[channelId] || [];
  },
  
  clearChannel: (channelId: number) => {
    set((state) => {
      const newByChannel = { ...state.typingByChannel };
      delete newByChannel[channelId];
      return { typingByChannel: newByChannel };
    });
  },
  
  clearAll: () => {
    set({ typingByChannel: {} });
  },
}));

/**
 * Format typing indicator text.
 * Returns null if no one is typing.
 */
export function formatTypingIndicator(users: TypingUser[]): string | null {
  if (users.length === 0) return null;
  
  if (users.length === 1) {
    return `${users[0].username} is typing...`;
  }
  
  if (users.length === 2) {
    return `${users[0].username} and ${users[1].username} are typing...`;
  }
  
  // 3+ users
  return `${users[0].username} and ${users.length - 1} others are typing...`;
}
