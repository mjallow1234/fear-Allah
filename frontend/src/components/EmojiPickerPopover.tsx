/**
 * EmojiPickerPopover - A simple emoji picker dropdown
 * Phase 9.4 - Emoji Reactions Frontend
 * 
 * Features:
 * - Common emoji grid
 * - Click outside to close
 * - Positioned relative to trigger
 */
import { useEffect, useState, useLayoutEffect } from 'react'
import { createPortal } from 'react-dom'
import { SmilePlus } from 'lucide-react'
import EMOJI_DATA, { type EmojiItem } from '../data/emojiData'

interface EmojiPickerPopoverProps {
  open: boolean
  onClose: () => void
  onSelect: (emoji: string) => void
  anchorRef?: React.RefObject<HTMLButtonElement>
}

const CATEGORY_ORDER: { id: EmojiItem['category']; label: string }[] = [
  { id: 'people', label: 'Smileys & People' },
  { id: 'nature', label: 'Animals & Nature' },
  { id: 'foods', label: 'Food & Drink' },
  { id: 'activity', label: 'Activities' },
  { id: 'places', label: 'Travel & Places' },
  { id: 'objects', label: 'Objects' },
  { id: 'symbols', label: 'Symbols' },
  { id: 'flags', label: 'Flags' },
]

const RECENT_KEY = 'emoji_recent_v1'
const RECENT_LIMIT = 50

export default function EmojiPickerPopover({
  open,
  onClose,
  onSelect,
  anchorRef,
}: EmojiPickerPopoverProps) {
  const [position, setPosition] = useState<{ top: number; left: number } | null>(null)
  const [activeCategory, setActiveCategory] = useState<string>('recent')
  const [query, setQuery] = useState('')
  const [recent, setRecent] = useState<string[]>([])

  useEffect(() => {
    const stored = localStorage.getItem(RECENT_KEY)
    setRecent(stored ? JSON.parse(stored) : [])
  }, [])


  // Positioning (compute only after mount; don't gate render on anchorRef)
  useLayoutEffect(() => {
    if (!open) return
    console.log('[Emoji] popover open')
    if (!anchorRef?.current) {
      // Wait until anchor is available
      setPosition(null)
      return
    }

    const rect = anchorRef.current.getBoundingClientRect()
    const pickerHeight = 360
    const spacing = 8

    const spaceBelow = window.innerHeight - rect.bottom
    const top = spaceBelow >= pickerHeight ? rect.bottom + spacing : rect.top - pickerHeight - spacing

    const left = Math.min(Math.max(8, rect.left), window.innerWidth - 360 - 8)
    const computed = { top: Math.round(top), left: Math.round(left) }
    console.log('[Emoji] computed position', computed)
    setPosition(computed)
  }, [open, anchorRef])

  // Close on outside click or Escape
  useEffect(() => {
    if (!open) return
    const handleClickOutside = (e: MouseEvent) => {
      const target = e.target as Node
      // If click is inside anchor, ignore
      if (anchorRef?.current && anchorRef.current.contains(target)) return
      // If click is inside the picker portal, ignore
      const el = (target as HTMLElement).closest('.emoji-picker')
      if (el) return
      onClose()
    }
    const handleKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
    }
    document.addEventListener('mousedown', handleClickOutside)
    document.addEventListener('keydown', handleKey)
    return () => {
      document.removeEventListener('mousedown', handleClickOutside)
      document.removeEventListener('keydown', handleKey)
    }
  }, [open, onClose, anchorRef])

  // Compose list of emojis for the active view
  const getDisplayed = () => {
    const q = query.trim().toLowerCase()
    if (q) {
      return EMOJI_DATA.filter(e => e.name.includes(q) || e.char.includes(q))
    }
    if (activeCategory === 'recent') {
      return recent
        .map((c) => EMOJI_DATA.find(e => e.char === c))
        .filter(Boolean) as EmojiItem[]
    }
    return EMOJI_DATA.filter(e => e.category === (activeCategory as EmojiItem['category']))
  }

  const handleSelect = (emoji: string) => {
    // Update recent
    const updated = [emoji, ...recent.filter(c => c !== emoji)].slice(0, RECENT_LIMIT)
    setRecent(updated)
    localStorage.setItem(RECENT_KEY, JSON.stringify(updated))

    onSelect(emoji)
    onClose()
  }

  if (!open) return null

  const displayed = getDisplayed()

  return createPortal(
    <div
      style={{
        position: 'fixed',
        top: position?.top ?? -9999,
        left: position?.left ?? -9999,
        width: 360,
        height: 360,
        zIndex: 9999,
      }}
      className="emoji-picker"
      aria-hidden={false}
    >
      <div className="bg-[#2e3035] border border-[#3f4147] rounded-lg shadow-lg overflow-hidden flex flex-col">
        {/* Search (sticky) */}
        <div className="p-2 sticky top-0 bg-[#2e3035] z-10">
          <input
            type="search"
            placeholder="Search emojis"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            className="w-full px-2 py-1 bg-gray-800 rounded focus:outline-none"
          />
        </div>

        {/* Category tabs */}
        <div className="flex gap-1 px-2 py-1 overflow-x-auto">
          <button
            className={`px-2 py-1 rounded ${activeCategory === 'recent' ? 'bg-gray-700' : 'bg-transparent'}`}
            onClick={() => { setActiveCategory('recent'); setQuery('') }}
            title="Recent"
          >
            Recent
          </button>
          {CATEGORY_ORDER.map(c => (
            <button
              key={c.id}
              className={`px-2 py-1 rounded ${activeCategory === c.id ? 'bg-gray-700' : 'bg-transparent'}`}
              onClick={() => { setActiveCategory(c.id); setQuery('') }}
              title={c.label}
            >
              {c.label.split(' ')[0]}
            </button>
          ))}
        </div>

        {/* Grid */}
        <div className="p-2 overflow-auto" style={{ flex: 1 }}>
          {displayed.length === 0 ? (
            <div className="text-sm text-gray-400">No emojis found</div>
          ) : (
            <div className="grid grid-cols-8 gap-1">
              {displayed.map((item: any, idx: number) => (
                <button
                  key={`${item.char}-${idx}`}
                  onClick={() => handleSelect(item.char)}
                  className="p-2 hover:bg-[#3f4147] rounded text-lg transition-colors"
                  title={item.name || item.char}
                >
                  {item.char}
                </button>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>,
    document.body
  )
}

// Trigger button component for consistency
interface EmojiPickerTriggerProps {
  onClick: () => void
  className?: string
}

import React from 'react'

export const EmojiPickerTrigger = React.forwardRef<HTMLButtonElement, EmojiPickerTriggerProps>(({ onClick, className = '' }, ref) => {
  return (
    <button
      ref={ref}
      type="button"
      onClick={onClick}
      className={`p-1 hover:bg-[#3f4147] rounded text-[#b9bbbe] hover:text-white transition-colors ${className} emoji-trigger`}
      title="Add reaction"
    >
      <SmilePlus size={16} />
    </button>
  )
})

EmojiPickerTrigger.displayName = 'EmojiPickerTrigger'
