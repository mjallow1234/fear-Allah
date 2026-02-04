import { useCallback, useRef } from 'react'

// Sound file path - place notification.mp3 in public folder
// Falls back to Web Audio API beep if file not found
const NOTIFICATION_SOUND_PATH = '/notification.mp3'

/**
 * Generate a simple beep sound using Web Audio API
 * Used as fallback when notification.mp3 is not available
 */
function playBeep() {
  try {
    const audioContext = new (window.AudioContext || (window as any).webkitAudioContext)()
    const oscillator = audioContext.createOscillator()
    const gainNode = audioContext.createGain()
    
    oscillator.connect(gainNode)
    gainNode.connect(audioContext.destination)
    
    oscillator.frequency.value = 880 // A5 note
    oscillator.type = 'sine'
    
    gainNode.gain.setValueAtTime(0.3, audioContext.currentTime)
    gainNode.gain.exponentialRampToValueAtTime(0.01, audioContext.currentTime + 0.3)
    
    oscillator.start(audioContext.currentTime)
    oscillator.stop(audioContext.currentTime + 0.3)
  } catch {
    // Silently fail if Web Audio API is not available
  }
}

/**
 * Hook to play notification sounds
 * 
 * Features:
 * - Preloads audio for instant playback
 * - Debounces to prevent spam
 * - Handles browser autoplay restrictions
 * - Falls back to Web Audio API beep
 */
export function useNotificationSound() {
  const audioRef = useRef<HTMLAudioElement | null>(null)
  const lastPlayedRef = useRef<number>(0)
  
  // Minimum time between sounds (ms) to prevent spam
  const DEBOUNCE_MS = 1000

  const playSound = useCallback(() => {
    const now = Date.now()
    
    // Debounce: don't play if we just played
    if (now - lastPlayedRef.current < DEBOUNCE_MS) {
      return
    }
    
    lastPlayedRef.current = now

    try {
      // Create new audio instance each time for reliability
      if (!audioRef.current) {
        audioRef.current = new Audio(NOTIFICATION_SOUND_PATH)
        audioRef.current.volume = 0.5
      }
      
      // Reset to start if already playing
      audioRef.current.currentTime = 0
      
      // Play with error handling for autoplay restrictions
      const playPromise = audioRef.current.play()
      
      if (playPromise !== undefined) {
        playPromise.catch(() => {
          // Audio file not found or autoplay prevented - use beep fallback
          playBeep()
        })
      }
    } catch {
      // Fallback to beep
      playBeep()
    }
  }, [])

  return { playSound }
}

// Standalone function for use outside React components
let globalAudio: HTMLAudioElement | null = null
let globalLastPlayed = 0

export function playNotificationSound() {
  const now = Date.now()
  
  if (now - globalLastPlayed < 1000) {
    return
  }
  
  globalLastPlayed = now

  try {
    if (!globalAudio) {
      globalAudio = new Audio(NOTIFICATION_SOUND_PATH)
      globalAudio.volume = 0.5
    }
    
    globalAudio.currentTime = 0
    globalAudio.play().catch(() => {
      // Fallback to beep
      playBeep()
    })
  } catch {
    playBeep()
  }
}
