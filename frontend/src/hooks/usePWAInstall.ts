/**
 * usePWAInstall
 *
 * Centralised PWA install-prompt hook.
 *
 * Captures the browser `beforeinstallprompt` event (Android / Chrome Desktop)
 * and exposes a `prompt()` function to trigger the native install dialog.
 *
 * Also detects:
 *   - Whether the app is already running in standalone mode
 *   - Whether the device is iOS (which has no beforeinstallprompt)
 *
 * Usage:
 *   const { canInstall, isStandalone, isIOS, promptInstall, dismiss } = usePWAInstall()
 */
import { useEffect, useState, useCallback } from 'react'

interface BeforeInstallPromptEvent extends Event {
  readonly platforms: string[]
  readonly userChoice: Promise<{ outcome: 'accepted' | 'dismissed'; platform: string }>
  prompt(): Promise<void>
}

const DISMISS_KEY = 'pwa_install_dismissed'
const DISMISS_HOURS = 48

function wasDismissedRecently(): boolean {
  try {
    const ts = localStorage.getItem(DISMISS_KEY)
    if (!ts) return false
    const diff = Date.now() - parseInt(ts, 10)
    return diff < DISMISS_HOURS * 60 * 60 * 1000
  } catch {
    return false
  }
}

export interface PWAInstallState {
  /** True when the native install prompt is available (Android/Chrome) */
  canInstall: boolean
  /** True when running in standalone / TWA mode (already installed) */
  isStandalone: boolean
  /** True on iOS Safari — no beforeinstallprompt, need manual instructions */
  isIOS: boolean
  /** True on Android Chrome — standard install prompt available */
  isAndroid: boolean
  /** True when we have something to show the user */
  shouldShowBanner: boolean
  /** Trigger the native install dialog (Android/Desktop Chrome) */
  promptInstall: () => Promise<void>
  /** Dismiss for DISMISS_HOURS hours */
  dismiss: () => void
}

export function usePWAInstall(): PWAInstallState {
  const [deferredPrompt, setDeferredPrompt] = useState<BeforeInstallPromptEvent | null>(null)
  const [dismissed, setDismissed] = useState<boolean>(wasDismissedRecently)

  const isStandalone =
    window.matchMedia('(display-mode: standalone)').matches ||
    (window.navigator as Navigator & { standalone?: boolean }).standalone === true

  const ua = navigator.userAgent.toLowerCase()
  const isIOS = /iphone|ipad|ipod/.test(ua) && !/crios/.test(ua)
  const isAndroid = /android/.test(ua)

  useEffect(() => {
    const handler = (e: Event) => {
      e.preventDefault()
      setDeferredPrompt(e as BeforeInstallPromptEvent)
    }
    window.addEventListener('beforeinstallprompt', handler)

    // If the user completes the install, clean up
    const installed = () => setDeferredPrompt(null)
    window.addEventListener('appinstalled', installed)

    return () => {
      window.removeEventListener('beforeinstallprompt', handler)
      window.removeEventListener('appinstalled', installed)
    }
  }, [])

  const promptInstall = useCallback(async () => {
    if (!deferredPrompt) return
    await deferredPrompt.prompt()
    await deferredPrompt.userChoice
    setDeferredPrompt(null)
  }, [deferredPrompt])

  const dismiss = useCallback(() => {
    try { localStorage.setItem(DISMISS_KEY, String(Date.now())) } catch { /* ignore */ }
    setDismissed(true)
  }, [])

  const canInstall = Boolean(deferredPrompt)

  const shouldShowBanner =
    !isStandalone &&
    !dismissed &&
    (canInstall || isIOS)

  return { canInstall, isStandalone, isIOS, isAndroid, shouldShowBanner, promptInstall, dismiss }
}
