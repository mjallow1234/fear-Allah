/// <reference types="vitest" />
import { render, screen, waitFor } from '@testing-library/react'
import Sidebar from './Sidebar'
import { MemoryRouter } from 'react-router-dom'
import { vi, describe, it, expect, beforeEach } from 'vitest'
import api from '../services/api'
import { useAuthStore } from '../stores/authStore'

let eventHandler: ((data: any) => void) | null = null

vi.mock('../services/useWebSocket', () => ({
  usePresence: () => ({
    isConnected: true,
    onlineUsers: [],
    isUserOnline: () => false,
    onEvent: (handler: (data: any) => void) => {
      eventHandler = handler
      return () => { eventHandler = null }
    },
  }),
}))

vi.mock('../services/api')

const mockedApi = api as unknown as { get: any }

describe('Sidebar presence events', () => {
  beforeEach(() => {
    // set authenticated admin-like user so channels can be fetched
    useAuthStore.setState({ user: { id: 1, username: 'u', email: 'u@example.com', display_name: 'U', avatar_url: null, is_system_admin: true }, token: 'tok', isAuthenticated: true })
    mockedApi.get.mockReset()
  })

  it('adds a channel when a channel_created presence event is received', async () => {
    mockedApi.get.mockImplementation((path: string) => {
      if (path === '/api/teams/') return Promise.resolve({ data: [{ id: 1, name: 'team1', display_name: 'Team 1' }] })
      if (path.startsWith('/api/channels/')) return Promise.resolve({ data: [{ id: 10, name: 'chan', display_name: 'Chan', type: 'O', team_id: 1 }] })
      if (path === '/api/channels/?team_id=1') return Promise.resolve({ data: [{ id: 10, name: 'chan', display_name: 'Chan', type: 'O', team_id: 1 }] })
      return Promise.resolve({ data: [] })
    })

    render(
      <MemoryRouter>
        <Sidebar />
      </MemoryRouter>
    )

    // Wait for initial channel to appear
    await waitFor(() => expect(screen.getByText('Chan')).toBeInTheDocument())

    // Simulate presence event
    expect(eventHandler).not.toBeNull()
    const newChannel = { id: 11, name: 'newchan', display_name: 'New Channel', type: 'O', team_id: 1 }

    // Call handler
    eventHandler!({ type: 'channel_created', channel: newChannel })

    // Now the new channel should appear in the sidebar
    await waitFor(() => expect(screen.getByText('New Channel')).toBeInTheDocument())
  })
})
