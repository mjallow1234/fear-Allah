import { createPortal } from 'react-dom'
import type { ReactNode } from 'react'

/**
 * Renders children into document.body, escaping any overflow / stacking-context
 * ancestors. Use for dropdowns, context-menus, popovers, tooltips, etc.
 *
 * Pair with `useFloating` to compute `position: fixed` coordinates from a
 * trigger element's viewport rect.
 */
export default function Portal({ children }: { children: ReactNode }) {
  return createPortal(children, document.body)
}
