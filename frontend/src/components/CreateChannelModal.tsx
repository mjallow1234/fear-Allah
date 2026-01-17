import { useEffect, useState } from 'react'
import clsx from 'clsx'
import api from '../services/api'

interface Props {
  isOpen: boolean
  onClose: () => void
  onCreated?: (channel: any) => void
}

function slugify(s: string) {
  return s
    .toLowerCase()
    .trim()
    .replace(/[^a-z0-9\s-]/g, '')
    .replace(/\s+/g, '-')
    .replace(/-+/g, '-')
}

export default function CreateChannelModal({ isOpen, onClose, onCreated }: Props) {
  const [displayName, setDisplayName] = useState('')
  const [name, setName] = useState('')
  const [isPrivate, setIsPrivate] = useState(false)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    // auto-generate name from display name
    setName((prev) => (displayName ? slugify(displayName) : prev))
    // only auto-fill when user hasn't overridden; simple heuristic
  }, [displayName])

  useEffect(() => {
    if (!isOpen) {
      setDisplayName('')
      setName('')
      setIsPrivate(false)
      setError(null)
      setLoading(false)
    }
  }, [isOpen])

  const submit = async () => {
    setError(null)
    if (!displayName.trim()) return setError('Display name is required')
    if (!name.trim()) return setError('Channel name is required')
    setLoading(true)
    try {
      const payload = {
        name: name,
        display_name: displayName,
        type: isPrivate ? 'P' : 'O',
      }
      const res = await api.post('/channels/', payload)
      const channel = res.data
      onCreated?.(channel)
      onClose()
    } catch (err: any) {
      setError(err?.response?.data?.detail || 'Failed to create channel')
    } finally {
      setLoading(false)
    }
  }

  if (!isOpen) return null

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      <div className="absolute inset-0 bg-black opacity-50" onClick={onClose} />
      <div className="bg-[#111214] rounded shadow-lg w-full max-w-md z-10 p-6 border border-[#1f2023]">
        <h2 className="text-lg font-bold text-white mb-4">Create Channel</h2>

        <label className="block text-sm text-[#cbd5e1] mb-1">Display Name</label>
        <input aria-label="Display Name" value={displayName} onChange={(e) => setDisplayName(e.target.value)} className="w-full mb-3 p-2 rounded bg-[#17181a] text-white" />
 
        <label className="block text-sm text-[#cbd5e1] mb-1">Channel Name</label>
        <input aria-label="Channel Name" value={name} onChange={(e) => setName(e.target.value)} className="w-full mb-3 p-2 rounded bg-[#17181a] text-white" />
        <div className="flex items-center gap-3 mb-3">
          <label className="text-sm text-[#cbd5e1]">Public</label>
          <button onClick={() => setIsPrivate(false)} className={clsx('px-3 py-1 rounded', !isPrivate ? 'bg-[#2b2d31] text-white' : 'bg-transparent text-[#949ba4]')}>O</button>
          <label className="text-sm text-[#cbd5e1]">Private</label>
          <button onClick={() => setIsPrivate(true)} className={clsx('px-3 py-1 rounded', isPrivate ? 'bg-[#2b2d31] text-white' : 'bg-transparent text-[#949ba4]')}>P</button>
        </div>

        {error && <div className="text-red-400 mb-3">{error}</div>}

        <div className="flex justify-end gap-2">
          <button onClick={onClose} className="px-3 py-2 rounded bg-transparent border border-[#2b2d31] text-[#cbd5e1]">Cancel</button>
          <button onClick={submit} disabled={loading} className="px-3 py-2 rounded bg-[#5865f2] text-white">{loading ? 'Creating...' : 'Create'}</button>
        </div>
      </div>
    </div>
  )
}
