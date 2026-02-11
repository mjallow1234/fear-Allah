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
  // roomKey -> list of typing users. roomKey is a string like "channel:1" or "dm:1"
  typingByChannel: Record<string, TypingUser[]>;
  
  // Actions accept either a string room key or a numeric channel id
  addTypingUser: (roomKey: string | number, userId: number, username: string) => void;
  removeTypingUser: (roomKey: string | number, userId: number) => void;
  getTypingUsers: (roomKey: string | number) => TypingUser[];
  clearChannel: (roomKey: string | number) => void;
  clearAll: () => void;
}

// Auto-expire typing after this many ms (client-side safety)
const TYPING_EXPIRE_MS = 5000;

export const useTypingStore = create<TypingStore>((set, get) => ({
  typingByChannel: {},
  
  addTypingUser: (roomKey: string | number, userId: number, username: string) => {
    const key = typeof roomKey === 'number' ? `channel:${roomKey}` : roomKey;
    set((state) => {
      const existing = state.typingByChannel[key] || [];
      
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
          [key]: updated,
        },
      };
    });
    
    // Auto-expire after timeout (safety in case stop event is missed)
    setTimeout(() => {
      const current = get().typingByChannel[key] || [];
      const user = current.find(u => u.userId === userId);
      if (user && Date.now() - user.startedAt >= TYPING_EXPIRE_MS - 100) {
        get().removeTypingUser(key, userId);
      }
    }, TYPING_EXPIRE_MS);
  },
  
  removeTypingUser: (roomKey: string | number, userId: number) => {
    const key = typeof roomKey === 'number' ? `channel:${roomKey}` : roomKey;
    set((state) => {
      const existing = state.typingByChannel[key] || [];
      const filtered = existing.filter(u => u.userId !== userId);
      
      if (filtered.length === existing.length) {
        // No change
        return state;
      }
      
      const newByChannel = { ...state.typingByChannel };
      if (filtered.length === 0) {
        delete newByChannel[key];
      } else {
        newByChannel[key] = filtered;
      }
      
      return { typingByChannel: newByChannel };
    });
  },
  
  getTypingUsers: (roomKey: string | number) => {
    const key = typeof roomKey === 'number' ? `channel:${roomKey}` : roomKey;
    return get().typingByChannel[key] || [];
  },
  
  clearChannel: (roomKey: string | number) => {
    const key = typeof roomKey === 'number' ? `channel:${roomKey}` : roomKey;
    set((state) => {
      const newByChannel = { ...state.typingByChannel };
      delete newByChannel[key];
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
