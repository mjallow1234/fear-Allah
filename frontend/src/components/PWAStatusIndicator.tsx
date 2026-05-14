/**
 * PWAStatusIndicator — DEV ONLY
 *
 * Lightweight diagnostics badge rendered in the bottom-left corner.
 * Shows:
 *   - Service Worker state (active / inactive / unsupported)
 *   - Installability state
 *   - Standalone mode detection
 *
 * Rendered ONLY when import.meta.env.DEV is true.
 * Returns null in production builds — zero bundle impact.
 */
import { useEffect, useState } from 'react'
import { usePWAInstall } from '../hooks/usePWAInstall'

type SWState = 'unsupported' | 'pending' | 'active' | 'inactive'

// Inner component holds all hooks — only mounted in DEV
function PWAStatusInner() {
  const { canInstall, isStandalone, isIOS } = usePWAInstall()
  const [swState, setSWState] = useState<SWState>('pending')
  const [open, setOpen] = useState(false)

  useEffect(() => {
    if (!('serviceWorker' in navigator)) {
      setSWState('unsupported')
      return
    }

    // Check current state immediately
    navigator.serviceWorker.getRegistration().then((reg) => {
      if (reg?.active) setSWState('active')
      else if (reg?.installing || reg?.waiting) setSWState('pending')
      else setSWState('inactive')
    })

    // Wait for ready (resolves once SW is active — handles the installing→active transition)
    navigator.serviceWorker.ready.then(() => {
      setSWState('active')
    })

    // Pick up subsequent controller changes (skipWaiting claim)
    const onControllerChange = () => {
      if (navigator.serviceWorker.controller) setSWState('active')
    }
    navigator.serviceWorker.addEventListener('controllerchange', onControllerChange)
    return () => {
      navigator.serviceWorker.removeEventListener('controllerchange', onControllerChange)
    }
  }, [])

  const swColor =
    swState === 'active'      ? '#57f287' :
    swState === 'inactive'    ? '#fee75c' :
    swState === 'unsupported' ? '#ed4245' : '#949ba4'

  return (
    <div
      className="fixed bottom-2 left-2 z-[9999] font-mono text-xs select-none"
      style={{ fontFamily: 'monospace' }}
    >
      {open ? (
        <div
          className="rounded-lg border border-[#1f2023] bg-[#111214] text-[#dcddde] p-3 shadow-2xl w-56"
          onClick={() => setOpen(false)}
        >
          <p className="font-bold text-white mb-2">PWA Dev Status</p>
          <div className="space-y-1.5">
            <Row label="SW"         value={swState}              color={swColor} />
            <Row label="Standalone" value={isStandalone ? 'yes' : 'no'} color={isStandalone ? '#57f287' : '#949ba4'} />
            <Row label="Installable" value={canInstall ? 'yes' : 'no'} color={canInstall ? '#57f287' : '#949ba4'} />
            <Row label="iOS"        value={isIOS ? 'yes' : 'no'} color={isIOS ? '#fee75c' : '#949ba4'} />
          </div>
          <p className="text-[#5c5e66] mt-2 text-[10px]">Click to collapse</p>
        </div>
      ) : (
        <button
          onClick={() => setOpen(true)}
          className="flex items-center gap-1 px-2 py-1 rounded-md bg-[#111214] border border-[#1f2023] text-[#949ba4] hover:text-white"
          title="PWA dev diagnostics"
        >
          <span className="inline-block w-2 h-2 rounded-full" style={{ backgroundColor: swColor }} />
          PWA
        </button>
      )}
    </div>
  )
}

function Row({ label, value, color }: { label: string; value: string; color: string }) {
  return (
    <div className="flex items-center justify-between gap-2">
      <span className="text-[#949ba4]">{label}</span>
      <span style={{ color }}>{value}</span>
    </div>
  )
}

// Outer: no hooks — safely returns null in production
export default function PWAStatusIndicator() {
  if (!import.meta.env.DEV) return null
  return <PWAStatusInner />
}

