import { render, screen, fireEvent } from '@testing-library/react'
import { useRef, useState } from 'react'
import EmojiPickerPopover, { EmojiPickerTrigger } from './EmojiPickerPopover'

function TestComposer() {
  const ref = useRef<HTMLButtonElement | null>(null)
  const [open, setOpen] = useState(false)

  return (
    <div>
      <EmojiPickerTrigger
        ref={ref}
        onClick={() => {
          console.log('[Emoji] Trigger clicked')
          setOpen(true)
        }}
      />
      <EmojiPickerPopover
        anchorRef={ref}
        open={open}
        onClose={() => setOpen(false)}
        onSelect={(emoji) => {
          // no-op
          setOpen(false)
        }}
      />
    </div>
  )
}

describe('Composer emoji trigger hotfix', () => {
  test('clicking emoji trigger logs and opens popover', () => {
    const log = vi.spyOn(console, 'log')
    render(<TestComposer />)
    const button = screen.getByTitle('Add reaction') as HTMLButtonElement
    fireEvent.click(button)
    expect(log).toHaveBeenCalledWith('[Emoji] Trigger clicked')
    // Popover should render search box
    expect(screen.getByPlaceholderText('Search emojis')).toBeInTheDocument()
    log.mockRestore()
  })
})
