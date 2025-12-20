'use client'

import { useEffect } from 'react'
import { useRouter, usePathname } from 'next/navigation'
import { useAuthStore } from '../stores/authStore'

export default function RequireAuth({ children }: { children: React.ReactNode }) {
  const hydrated = useAuthStore((s) => s.hydrated)
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated)
  const hydrate = useAuthStore((s) => s.hydrate)
  const router = useRouter()
  const pathname = usePathname()

  useEffect(() => {
    // ensure store reads from localStorage
    hydrate()
  }, [hydrate])

  useEffect(() => {
    if (hydrated && !isAuthenticated) {
      router.replace(`/login?next=${encodeURIComponent(pathname)}`)
    }
  }, [hydrated, isAuthenticated, pathname, router])

  if (!hydrated) return null
  if (!isAuthenticated) return null

  return <>{children}</>
}
