import { useState, useLayoutEffect, type RefObject } from 'react'

export type FloatingPlacement = 'bottom-end' | 'bottom-start' | 'top-end' | 'top-start'

export interface FloatingCoords {
  top: number
  left: number
}

interface UseFloatingOptions {
  /** Ref pointing at the trigger / anchor element. */
  anchorRef: RefObject<HTMLElement | null>
  /** Whether the floating panel is currently visible. */
  open: boolean
  /** Estimated (or known) pixel width of the floating panel. Default: 240 */
  width?: number
  /** Estimated (or known) pixel height of the floating panel. Default: 320 */
  height?: number
  /** Preferred placement. The hook flips when there is not enough room. Default: 'bottom-end' */
  placement?: FloatingPlacement
  /** Gap in px between the anchor edge and the panel. Default: 4 */
  gap?: number
}

/**
 * Computes `position: fixed` top/left coordinates for a floating overlay
 * anchored to a trigger element.
 *
 * - Uses `getBoundingClientRect()` — always viewport-relative.
 * - Flips vertically (bottom ↔ top) when there is insufficient room.
 * - Clamps horizontally so the panel never escapes the viewport.
 * - Returns `null` when `open` is false or the anchor is unavailable.
 *
 * @example
 * const triggerRef = useRef<HTMLButtonElement>(null)
 * const coords = useFloating({ anchorRef: triggerRef, open: isOpen, width: 320, height: 450 })
 *
 * return (
 *   <>
 *     <button ref={triggerRef} ...>Open</button>
 *     {isOpen && coords && (
 *       <Portal>
 *         <div style={{ position: 'fixed', top: coords.top, left: coords.left, width: 320 }} ...>
 *           ...
 *         </div>
 *       </Portal>
 *     )}
 *   </>
 * )
 */
export function useFloating({
  anchorRef,
  open,
  width = 240,
  height = 320,
  placement = 'bottom-end',
  gap = 4,
}: UseFloatingOptions): FloatingCoords | null {
  const [coords, setCoords] = useState<FloatingCoords | null>(null)

  useLayoutEffect(() => {
    if (!open) {
      setCoords(null)
      return
    }
    const el = anchorRef.current
    if (!el) return

    const rect = el.getBoundingClientRect()
    const vw = window.innerWidth
    const vh = window.innerHeight

    // ── Vertical ────────────────────────────────────────────────────────────
    const spaceBelow = vh - rect.bottom
    const spaceAbove = rect.top
    const preferBelow = placement.startsWith('bottom')
    let top: number
    if (preferBelow) {
      top =
        spaceBelow >= height + gap
          ? rect.bottom + gap
          : spaceAbove >= height + gap
          ? rect.top - height - gap
          : rect.bottom + gap // keep below even if it overflows; browser will scroll
    } else {
      top =
        spaceAbove >= height + gap
          ? rect.top - height - gap
          : rect.bottom + gap
    }
    // Never go above viewport
    top = Math.max(4, Math.min(top, vh - height - 4))

    // ── Horizontal ──────────────────────────────────────────────────────────
    let left: number
    if (placement.endsWith('end')) {
      // Right-align: panel right edge = anchor right edge
      left = rect.right - width
    } else {
      // Left-align: panel left edge = anchor left edge
      left = rect.left
    }
    // Clamp so panel stays inside viewport
    left = Math.max(4, Math.min(left, vw - width - 4))

    setCoords({ top: Math.round(top), left: Math.round(left) })
  }, [open, anchorRef, width, height, placement, gap])

  return coords
}
