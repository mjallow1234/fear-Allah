'use client'

export default function Sidebar() {
  return (
    <div className="p-6">
      <div className="text-xl font-semibold mb-6">fear-Allah</div>

      <nav className="space-y-2">
        <div className="px-3 py-2 rounded hover:bg-gray-100 cursor-default">Channels</div>
        <div className="px-3 py-2 rounded hover:bg-gray-100 cursor-default">Tasks</div>
        <div className="px-3 py-2 rounded hover:bg-gray-100 cursor-default">Orders</div>
        <div className="px-3 py-2 rounded hover:bg-gray-100 cursor-default">Sales</div>
      </nav>
    </div>
  )
}
