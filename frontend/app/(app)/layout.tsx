'use client'

import type { ReactNode } from 'react'
import RequireAuth from '../../components/RequireAuth'
import AppShell from '../../components/AppShell'

export default function AppLayout({ children }: { children: ReactNode }) {
  return (
    <RequireAuth>
      <AppShell>{children}</AppShell>
    </RequireAuth>
  )
}
