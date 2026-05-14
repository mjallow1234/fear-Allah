/**
 * PWAInstallBanner
 *
 * Non-intrusive banner shown at the bottom of the screen when the app
 * can be installed.
 *
 * - Android / Chrome Desktop: native install prompt
 * - iOS Safari: manual "Add to Home Screen" instructions
 *
 * Dismissed state persists for 48 h in localStorage.
 */
import { usePWAInstall } from '../hooks/usePWAInstall'
import { X, Download, Share } from 'lucide-react'

export default function PWAInstallBanner() {
  const { shouldShowBanner, canInstall, isIOS, promptInstall, dismiss } = usePWAInstall()

  if (!shouldShowBanner) return null

  return (
    <div
      role="banner"
      aria-label="Install app"
      className="fixed bottom-safe-bottom left-0 right-0 z-50 mx-3 mb-3 rounded-xl border border-[#5865f2]/40 bg-[#2b2d31] shadow-2xl"
      style={{ bottom: 'max(12px, env(safe-area-inset-bottom))' }}
    >
      <div className="flex items-center gap-3 px-4 py-3">
        {/* Icon */}
        <div className="flex-shrink-0 w-10 h-10 rounded-lg bg-[#5865f2] flex items-center justify-center">
          <img src="/pwa-192x192.png" alt="" className="w-8 h-8 rounded" />
        </div>

        {/* Text */}
        <div className="flex-1 min-w-0">
          <p className="text-white text-sm font-semibold leading-tight">
            {isIOS ? 'Add to Home Screen' : 'Install Fear Allah Ops'}
          </p>
          <p className="text-[#949ba4] text-xs mt-0.5 leading-snug">
            {isIOS
              ? 'Tap the share icon below, then "Add to Home Screen"'
              : 'Install for quick access — works offline'}
          </p>
        </div>

        {/* CTA */}
        <div className="flex-shrink-0 flex items-center gap-2">
          {isIOS ? (
            <Share size={20} className="text-[#5865f2]" />
          ) : canInstall ? (
            <button
              onClick={promptInstall}
              className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold bg-[#5865f2] hover:bg-[#4752c4] text-white rounded-lg transition-colors"
            >
              <Download size={13} />
              Install
            </button>
          ) : null}

          <button
            onClick={dismiss}
            className="p-1.5 text-[#949ba4] hover:text-white transition-colors"
            aria-label="Dismiss"
          >
            <X size={16} />
          </button>
        </div>
      </div>
    </div>
  )
}
