import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, act } from '@testing-library/react'
import { MemoryRouter, Routes, Route } from 'react-router-dom'
import ChannelView from './ChannelView'
import api from '../services/api'

vi.mock('../services/api', () => ({
  default: { get: vi.fn(), post: vi.fn() }
}))

describe('ChannelView', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders messages correctly', async () => {
    ;(api.get as any).mockImplementation((url: string) => {
      if (url === '/api/channels/1') return Promise.resolve({ data: { id: 1, name: 'ch1', display_name: 'Ch 1' } })
      if (url.includes('/channels/1/messages')) return Promise.resolve({ data: { channel_id: 1, messages: [{ id: 5, content: 'Hello', author_username: 'alice', author_id: 10, created_at: new Date().toISOString() }], has_more: false } })
      if (url.includes('/channels/1/reads')) return Promise.resolve({ data: {} })
      if (url.includes('/upload-limits')) return Promise.resolve({ data: { max_file_size: 10485760, allowed_types: ['*/*'] } })
      return Promise.resolve({ data: {} })
    })

    await act(async () => {
      render(
        <MemoryRouter initialEntries={["/channels/1"]}>
          <Routes>
            <Route path="/channels/:channelId" element={<ChannelView />} />
          </Routes>
        </MemoryRouter>
      )
    })

    await waitFor(() => expect(screen.getByText('Hello')).toBeInTheDocument(), { timeout: 2000 })
    await waitFor(() => expect(screen.getByText(/alice/i)).toBeInTheDocument())
  })

  it('shows empty state when no messages', async () => {
    ;(api.get as any).mockImplementation((url: string) => {
      if (url === '/api/channels/2') return Promise.resolve({ data: { id: 2, name: 'empty', display_name: 'Empty' } })
      if (url.includes('/channels/2/messages')) return Promise.resolve({ data: { channel_id: 2, messages: [], has_more: false } })
      if (url.includes('/channels/2/reads')) return Promise.resolve({ data: {} })
      if (url.includes('/upload-limits')) return Promise.resolve({ data: { max_file_size: 10485760, allowed_types: ['*/*'] } })
      return Promise.resolve({ data: {} })
    })

    await act(async () => {
      render(
        <MemoryRouter initialEntries={["/channels/2"]}>
          <Routes>
            <Route path="/channels/:channelId" element={<ChannelView />} />
          </Routes>
        </MemoryRouter>
      )
    })

    await waitFor(() => expect(screen.getByText(/No messages yet/i)).toBeInTheDocument())
  })

  it('shows error state when messages load fails', async () => {
    ;(api.get as any).mockImplementation((url: string) => {
      if (url === '/api/channels/3') return Promise.resolve({ data: { id: 3, name: 'err', display_name: 'Err' } })
      if (url.includes('/channels/3/messages')) return Promise.reject(new Error('Network error'))
      if (url.includes('/channels/3/reads')) return Promise.resolve({ data: {} })
      if (url.includes('/upload-limits')) return Promise.resolve({ data: { max_file_size: 10485760, allowed_types: ['*/*'] } })
      return Promise.resolve({ data: {} })
    })

    await act(async () => {
      render(
        <MemoryRouter initialEntries={["/channels/3"]}>
          <Routes>
            <Route path="/channels/:channelId" element={<ChannelView />} />
          </Routes>
        </MemoryRouter>
      )
    })

    await waitFor(() => expect(screen.getByText('Failed to load messages')).toBeInTheDocument())
  })

  it('loads older messages when Load older clicked', async () => {
    let callCount = 0
    ;(api.get as any).mockImplementation((url: string) => {
      if (url === '/api/channels/1') return Promise.resolve({ data: { id: 1, name: 'ch1', display_name: 'Ch 1' } })
      if (url.includes('/channels/1/messages')) {
        callCount++
        if (callCount === 1 || !url.includes('before')) {
          return Promise.resolve({ data: { channel_id: 1, messages: [{ id: 4, content: 'Newer', author_username: 'alice', author_id: 10, created_at: new Date().toISOString() }, { id: 5, content: 'Newest', author_username: 'bob', author_id: 11, created_at: new Date().toISOString() }], has_more: true } })
        }
        // Second call with before param
        return Promise.resolve({ data: { channel_id: 1, messages: [{ id: 2, content: 'Older', author_username: 'carol', author_id: 12, created_at: new Date().toISOString() }], has_more: false } })
      }
      if (url.includes('/channels/1/reads')) return Promise.resolve({ data: {} })
      if (url.includes('/upload-limits')) return Promise.resolve({ data: { max_file_size: 10485760, allowed_types: ['*/*'] } })
      return Promise.resolve({ data: {} })
    })

    await act(async () => {
      render(
        <MemoryRouter initialEntries={["/channels/1"]}>
          <Routes>
            <Route path="/channels/:channelId" element={<ChannelView />} />
          </Routes>
        </MemoryRouter>
      )
    })

    // Initial messages visible
    await waitFor(() => expect(screen.getByText('Newest')).toBeInTheDocument())
    
    // Has more should be true, so Load older button should be visible
    const loadBtn = await screen.findByRole('button', { name: /load older messages/i })
    expect(loadBtn).toBeInTheDocument()

    // Click and expect older message added
    await act(async () => {
      loadBtn.click()
    })
    await waitFor(() => expect(screen.getByText('Older')).toBeInTheDocument())

    // Button should be hidden since has_more false
    expect(screen.queryByRole('button', { name: /load older messages/i })).toBeNull()
  })
})
