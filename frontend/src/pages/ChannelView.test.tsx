import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter, Routes, Route } from 'react-router-dom'
import ChannelView from './ChannelView'
import api from '../services/api'

vi.mock('../services/api', () => ({
  default: { get: vi.fn() }
}))

describe('ChannelView', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders messages correctly', async () => {
    ;(api.get as any).mockImplementation((url: string) => {
      if (url === '/api/channels/1') return Promise.resolve({ data: { id: 1, name: 'ch1', display_name: 'Ch 1' } })
      if (url.startsWith('/api/channels/1/messages')) return Promise.resolve({ data: { channel_id: 1, messages: [{ id: 5, content: 'Hello', author_username: 'alice', created_at: new Date().toISOString() }] } })
      return Promise.reject(new Error('not found'))
    })

    render(
      <MemoryRouter initialEntries={["/channels/1"]}>
        <Routes>
          <Route path="/channels/:channelId" element={<ChannelView />} />
        </Routes>
      </MemoryRouter>
    )

    await waitFor(() => expect(screen.getByText('Hello')).toBeInTheDocument())
    expect(screen.getByText('alice')).toBeInTheDocument()
  })

  it('shows empty state when no messages', async () => {
    ;(api.get as any).mockImplementation((url: string) => {
      if (url === '/api/channels/2') return Promise.resolve({ data: { id: 2, name: 'empty', display_name: 'Empty' } })
      if (url.startsWith('/api/channels/2/messages')) return Promise.resolve({ data: { channel_id: 2, messages: [] } })
      return Promise.reject(new Error('not found'))
    })

    render(
      <MemoryRouter initialEntries={["/channels/2"]}>
        <Routes>
          <Route path="/channels/:channelId" element={<ChannelView />} />
        </Routes>
      </MemoryRouter>
    )

    await waitFor(() => expect(screen.getByText('No messages yet')).toBeInTheDocument())
  })

  it('shows error state when messages load fails', async () => {
    ;(api.get as any).mockImplementation((url: string) => {
      if (url === '/api/channels/3') return Promise.resolve({ data: { id: 3, name: 'err', display_name: 'Err' } })
      if (url.startsWith('/api/channels/3/messages')) return Promise.reject(new Error('Network error'))
      return Promise.reject(new Error('not found'))
    })

    render(
      <MemoryRouter initialEntries={["/channels/3"]}>
        <Routes>
          <Route path="/channels/:channelId" element={<ChannelView />} />
        </Routes>
      </MemoryRouter>
    )

    await waitFor(() => expect(screen.getByText('Failed to load messages')).toBeInTheDocument())
  })
})