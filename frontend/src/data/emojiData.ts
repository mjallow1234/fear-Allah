// Minimal curated emoji dataset across categories for picker completeness
// Includes many commonly used emojis across categories used by the app.
export type EmojiItem = {
  char: string
  name: string
  category: 'people'|'nature'|'foods'|'activity'|'places'|'objects'|'symbols'|'flags'
}

const EMOJI_DATA: EmojiItem[] = [
  // People
  { char: '😀', name: 'grinning face', category: 'people' },
  { char: '😁', name: 'beaming face', category: 'people' },
  { char: '😂', name: 'face with tears of joy', category: 'people' },
  { char: '🤣', name: 'rolling on the floor laughing', category: 'people' },
  { char: '🙂', name: 'slightly smiling face', category: 'people' },
  { char: '🙃', name: 'upside-down face', category: 'people' },
  { char: '😉', name: 'winking face', category: 'people' },
  { char: '😊', name: 'smiling face with smiling eyes', category: 'people' },
  { char: '😍', name: 'smiling face with heart-eyes', category: 'people' },
  { char: '😘', name: 'face blowing a kiss', category: 'people' },
  { char: '😎', name: 'smiling face with sunglasses', category: 'people' },
  { char: '😢', name: 'crying face', category: 'people' },
  { char: '😡', name: 'pouting face', category: 'people' },
  { char: '😮', name: 'face with open mouth', category: 'people' },
  { char: '👍', name: 'thumbs up', category: 'people' },
  { char: '👎', name: 'thumbs down', category: 'people' },
  { char: '👏', name: 'clapping hands', category: 'people' },
  { char: '🙏', name: 'folded hands', category: 'people' },
  { char: '💯', name: 'hundred points', category: 'people' },
  { char: '💪', name: 'flexed biceps', category: 'people' },

  // Nature
  { char: '🐶', name: 'dog face', category: 'nature' },
  { char: '🐱', name: 'cat face', category: 'nature' },
  { char: '🐭', name: 'mouse face', category: 'nature' },
  { char: '🐼', name: 'panda face', category: 'nature' },
  { char: '🐻', name: 'bear face', category: 'nature' },
  { char: '🦊', name: 'fox face', category: 'nature' },
  { char: '🐨', name: 'koala', category: 'nature' },
  { char: '🦁', name: 'lion face', category: 'nature' },
  { char: '🐯', name: 'tiger face', category: 'nature' },
  { char: '🐸', name: 'frog face', category: 'nature' },
  { char: '🐵', name: 'monkey face', category: 'nature' },
  { char: '🦄', name: 'unicorn', category: 'nature' },
  { char: '🐝', name: 'honeybee', category: 'nature' },
  { char: '🌸', name: 'cherry blossom', category: 'nature' },
  { char: '🌲', name: 'evergreen tree', category: 'nature' },

  // Foods
  { char: '🍎', name: 'red apple', category: 'foods' },
  { char: '🍌', name: 'banana', category: 'foods' },
  { char: '🍕', name: 'pizza', category: 'foods' },
  { char: '🍔', name: 'hamburger', category: 'foods' },
  { char: '🍟', name: 'french fries', category: 'foods' },
  { char: '🍣', name: 'sushi', category: 'foods' },
  { char: '🍩', name: 'doughnut', category: 'foods' },
  { char: '🍪', name: 'cookie', category: 'foods' },
  { char: '☕', name: 'hot beverage', category: 'foods' },

  // Activity
  { char: '⚽', name: 'soccer ball', category: 'activity' },
  { char: '🏀', name: 'basketball', category: 'activity' },
  { char: '🏈', name: 'american football', category: 'activity' },
  { char: '🎾', name: 'tennis', category: 'activity' },
  { char: '🏆', name: 'trophy', category: 'activity' },
  { char: '🎮', name: 'video game', category: 'activity' },
  { char: '🎵', name: 'musical note', category: 'activity' },

  // Places / travel
  { char: '🚗', name: 'automobile', category: 'places' },
  { char: '✈️', name: 'airplane', category: 'places' },
  { char: '🚀', name: 'rocket', category: 'places' },
  { char: '🏝️', name: 'desert island', category: 'places' },
  { char: '🏠', name: 'house', category: 'places' },

  // Objects
  { char: '📱', name: 'mobile phone', category: 'objects' },
  { char: '💻', name: 'laptop', category: 'objects' },
  { char: '⌚', name: 'watch', category: 'objects' },
  { char: '📷', name: 'camera', category: 'objects' },
  { char: '🔒', name: 'lock', category: 'objects' },

  // Symbols
  { char: '❤️', name: 'red heart', category: 'symbols' },
  { char: '✨', name: 'sparkles', category: 'symbols' },
  { char: '🔥', name: 'fire', category: 'symbols' },
  { char: '✅', name: 'check mark', category: 'symbols' },
  { char: '❌', name: 'cross mark', category: 'symbols' },
  { char: '💤', name: 'zzz', category: 'symbols' },

  // Flags (a small sample)
  { char: '🇺🇸', name: 'flag: United States', category: 'flags' },
  { char: '🇬🇧', name: 'flag: United Kingdom', category: 'flags' },
  { char: '🇨🇦', name: 'flag: Canada', category: 'flags' },
  { char: '🇯🇵', name: 'flag: Japan', category: 'flags' },
]

export default EMOJI_DATA
