/**
 * PWAInstallBanner
 *
 * Non-intrusive banner shown at the bottom of the screen when the app
 * can be installed.
 *
 * - Android / Chrome Desktop: native install prompt
 * - iOS Safari: step-by-step "Add to Home Screen" instructions panel
 * - iOS non-Safari (Chrome/Firefox/Edge): "Open in Safari" instructions
 *
 * Dismissed state persists for 48 h in localStorage.
 */
import { useState } from 'react'
import { usePWAInstall } from '../hooks/usePWAInstall'
import { X, Download, Share, ExternalLink } from 'lucide-react'

export default function PWAInstallBanner() {
  const { shouldShowBanner, canInstall, isIOS, isIOSSafari, isIOSNonSafari, promptInstall, dismiss } = usePWAInstall()
  const [showSteps, setShowSteps] = useState(false)

  if (!shouldShowBanner) return null

  // ── title / subtitle copy ─────────────────────────────────────────────────
  const title = isIOSNonSafari
    ? 'Install via Safari'
    : isIOS
    ? 'Add to Home Screen'
    : 'Install Fear Allah Ops'

  const subtitle = isIOSNonSafari
    ? 'Open this page in Safari to install'
    : isIOS
    ? 'Follow 3 quick steps to install'
    : 'Quick access — works offline'

  return (
    <div
      role="banner"
      aria-label="Install app"
      className="fixed left-0 right-0 z-50 mx-3 mb-3 rounded-xl border border-[#5865f2]/40 bg-[#2b2d31] shadow-2xl"
      style={{ bottom: 'max(12px, env(safe-area-inset-bottom))' }}
    >
      {/* ── Main row ───────────────────────────────────────────────────────── */}
      <div className="flex items-center gap-3 px-4 py-3">
        {/* App icon */}
        <div className="flex-shrink-0 w-10 h-10 rounded-lg bg-[#5865f2] flex items-center justify-center">
          <img src="/pwa-192x192.png" alt="" className="w-8 h-8 rounded" />
        </div>

        {/* Text */}
        <div className="flex-1 min-w-0">
          <p className="text-white text-sm font-semibold leading-tight">{title}</p>
          <p className="text-[#949ba4] text-xs mt-0.5 leading-snug">{subtitle}</p>
        </div>

        {/* CTA */}
        <div className="flex-shrink-0 flex items-center gap-2">
          {isIOSSafari ? (
            /* iOS Safari — show/hide step-by-step instructions */
            <button
              onClick={() => setShowSteps((s) => !s)}
              className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold bg-[#5865f2] hover:bg-[#4752c4] active:bg-[#3c45a5] text-white rounded-lg transition-colors"
              aria-expanded={showSteps}
            >
              <Share size={13} />
              How to
            </button>
          ) : isIOSNonSafari ? (
            /* iOS non-Safari — prompt to copy URL and open Safari */
            <button
              onClick={() => setShowSteps((s) => !s)}
              className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold bg-[#5865f2] hover:bg-[#4752c4] active:bg-[#3c45a5] text-white rounded-lg transition-colors"
              aria-expanded={showSteps}
            >
              <ExternalLink size={13} />
              Open in Safari
            </button>
          ) : canInstall ? (
            /* Android / Desktop Chrome — native prompt */
            <button
              onClick={promptInstall}
              className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold bg-[#5865f2] hover:bg-[#4752c4] active:bg-[#3c45a5] text-white rounded-lg transition-colors"
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

      {/* ── iOS Safari step-by-step instructions ──────────────────────────── */}
      {showSteps && isIOSSafari && (
        <div className="border-t border-[#3f4147] px-4 py-3 space-y-2">
          <p className="text-[#949ba4] text-xs font-semibold uppercase tracking-wide mb-2">
            Add to Home Screen
          </p>
          {[
            { n: 1, text: 'Tap the Share button (↑) at the bottom of Safari' },
            { n: 2, text: 'Scroll down and tap "Add to Home Screen"' },
            { n: 3, text: 'Tap "Add" in the top-right corner' },
          ].map(({ n, text }) => (
            <div key={n} className="flex items-start gap-2.5">
              <span className="flex-shrink-0 w-5 h-5 rounded-full bg-[#5865f2] text-white text-[10px] font-bold flex items-center justify-center">
                {n}
              </span>
              <p className="text-white text-xs leading-snug">{text}</p>
            </div>
          ))}
        </div>
      )}

      {/* ── iOS non-Safari: open in Safari instructions ─────────────────── */}
      {showSteps && isIOSNonSafari && (
        <div className="border-t border-[#3f4147] px-4 py-3 space-y-2">
          <p className="text-[#949ba4] text-xs font-semibold uppercase tracking-wide mb-2">
            Install requires Safari
          </p>
          {[
            { n: 1, text: 'Copy the URL from the address bar above' },
            { n: 2, text: 'Open Safari on your iPhone' },
            { n: 3, text: 'Paste the URL and navigate to the page' },
            { n: 4, text: 'Tap Share (↑) → "Add to Home Screen"' },
          ].map(({ n, text }) => (
            <div key={n} className="flex items-start gap-2.5">
              <span className="flex-shrink-0 w-5 h-5 rounded-full bg-[#fee75c] text-[#1a1a1a] text-[10px] font-bold flex items-center justify-center">
                {n}
              </span>
              <p className="text-white text-xs leading-snug">{text}</p>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

