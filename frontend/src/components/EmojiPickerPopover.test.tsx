import { render, screen, fireEvent, act } from '@testing-library/react'
import EmojiPickerPopover from './EmojiPickerPopover'
import EMOJI_DATA from '../data/emojiData'

describe('EmojiPickerPopover', () => {
  beforeEach(() => {
    // Ensure recent storage cleared
    localStorage.removeItem('emoji_recent_v1')
  })

  test('renders search and categories and full-ish dataset', () => {
    const trigger = document.createElement('button')
    document.body.appendChild(trigger)
    trigger.getBoundingClientRect = () => ({ left: 100, top: 100, right: 120, bottom: 120, width: 20, height: 20 } as DOMRect)

    const onSelect = vi.fn()
    const onClose = vi.fn()

    render(
      <EmojiPickerPopover open={true} onClose={onClose} onSelect={onSelect} anchorRef={{ current: trigger as HTMLButtonElement }} />
    )

    // Search input
    expect(screen.getByPlaceholderText('Search emojis')).toBeInTheDocument()

    // The picker shows category tabs (9 tabs = Recent + 8 categories)
    // plus emoji grid buttons when there's content (recent is empty at start)
    // Check that category tabs are rendered (at least 9 buttons for tabs)
    expect(screen.getAllByRole('button').length).toBeGreaterThanOrEqual(9)

    // A sample emoji we included should be present when searching for it
    const searchInput = screen.getByPlaceholderText('Search emojis') as HTMLInputElement
    // Search for pizza to load the full emoji dataset
    searchInput.focus()
    fireEvent.change(searchInput, { target: { value: 'pizza' } })
    expect(screen.getAllByTitle(/pizza/i).length).toBeGreaterThanOrEqual(1)
  })

  test('search filters results', () => {
    const trigger = document.createElement('button')
    document.body.appendChild(trigger)
    trigger.getBoundingClientRect = () => ({ left: 100, top: 100, right: 120, bottom: 120, width: 20, height: 20 } as DOMRect)

    const onSelect = vi.fn()
    const onClose = vi.fn()

    render(
      <EmojiPickerPopover open={true} onClose={onClose} onSelect={onSelect} anchorRef={{ current: trigger as HTMLButtonElement }} />
    )

    const input = screen.getByPlaceholderText('Search emojis') as HTMLInputElement
    fireEvent.change(input, { target: { value: 'pizza' } })

    // Only pizza (🍕) should match
    expect(screen.getAllByRole('button').some(b => b.textContent === '🍕')).toBe(true)
  })

  test('selecting emoji updates recent and calls callbacks', () => {
    const trigger = document.createElement('button')
    document.body.appendChild(trigger)
    trigger.getBoundingClientRect = () => ({ left: 100, top: 100, right: 120, bottom: 120, width: 20, height: 20 } as DOMRect)

    const onSelect = vi.fn()
    const onClose = vi.fn()

    render(
      <EmojiPickerPopover open={true} onClose={onClose} onSelect={onSelect} anchorRef={{ current: trigger as HTMLButtonElement }} />
    )

    // Search for pizza to make it visible
    const searchInput = screen.getByPlaceholderText('Search emojis') as HTMLInputElement
    fireEvent.change(searchInput, { target: { value: 'pizza' } })

    // Click pizza
    const pizzaBtn = screen.getAllByRole('button').find(b => b.textContent === '🍕')
    expect(pizzaBtn).toBeTruthy()
    fireEvent.click(pizzaBtn!)

    expect(onSelect).toHaveBeenCalledWith('🍕')
    expect(onClose).toHaveBeenCalled()

    const stored = JSON.parse(localStorage.getItem('emoji_recent_v1') || '[]')
    expect(stored[0]).toBe('🍕')
  })

  test('picker flips up when trigger near bottom', () => {
    const trigger = document.createElement('button')
    document.body.appendChild(trigger)
    // Simulate trigger near bottom
    trigger.getBoundingClientRect = () => ({ left: 50, top: 1000, right: 70, bottom: 1020, width: 20, height: 20 } as DOMRect)

    const onSelect = vi.fn()
    const onClose = vi.fn()

    render(
      <EmojiPickerPopover open={true} onClose={onClose} onSelect={onSelect} anchorRef={{ current: trigger as HTMLButtonElement }} />
    )

    // Locate the portal container by finding the element that has the search input
    const input = screen.getByPlaceholderText('Search emojis')
    // Its containing fixed wrapper should have a computed top less than trigger.top (i.e., it flipped up)
    let wrapper: HTMLElement | null = input.closest('div[style]') as HTMLElement
    while (wrapper && !wrapper.style.top) {
      wrapper = wrapper.parentElement
    }
    expect(wrapper).not.toBeNull()
    const topVal = Number(wrapper!.style.top.replace('px', ''))
    expect(topVal).toBeLessThan(1000) // flipped above trigger
  })
})
