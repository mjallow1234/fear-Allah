'use client'

import type { ReactNode } from 'react'
import Sidebar from './Sidebar'
import TopBar from './TopBar'

export default function AppShell({ children }: { children: ReactNode }) {
  return (
    <div className="min-h-screen flex bg-[#f7f7f8] text-gray-900">
      <aside className="w-[260px] bg-white border-r border-gray-200 flex-none">
        <Sidebar />
      </aside>

      <div className="flex-1 flex flex-col">
        <header className="bg-white border-b border-gray-200">
          <TopBar />
        </header>

        <main className="flex-1 p-8">{children}</main>
      </div>
    </div>
  )
}
