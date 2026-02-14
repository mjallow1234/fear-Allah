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

// Mock socket events (onSocketEvent) so tests can trigger message/thread/receipt:update handlers
const socketEventHandlers: Record<string, ((data: any) => void) | undefined> = {}
vi.mock('../realtime', () => ({
  onSocketEvent: (event: string, handler: (data: any) => void) => {
    socketEventHandlers[event] = handler
    return () => { delete socketEventHandlers[event] }
  }
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
      if (path.startsWith('/api/channels/')) return Promise.resolve({ data: [{ id: 10, name: 'chan', display_name: 'Chan', type: 'O', team_id: 1, unread_count: 2 }] })
      if (path === '/api/channels/?team_id=1') return Promise.resolve({ data: [{ id: 10, name: 'chan', display_name: 'Chan', type: 'O', team_id: 1, unread_count: 2 }] })
      return Promise.resolve({ data: [] })
    })

    render(
      <MemoryRouter>
        <Sidebar />
      </MemoryRouter>
    )

    // Wait for initial channel to appear
    await waitFor(() => expect(screen.getByText('Chan')).toBeInTheDocument())
    // Ensure unread badge from server is rendered
    expect(screen.getByTestId('channel-unread-10')).toHaveTextContent('2')

    // Simulate presence event
    expect(eventHandler).not.toBeNull()
    const newChannel = { id: 11, name: 'newchan', display_name: 'New Channel', type: 'O', team_id: 1 }

    // Call handler
    eventHandler!({ type: 'channel_created', channel: newChannel })

    // Now the new channel should appear in the sidebar
    await waitFor(() => expect(screen.getByText('New Channel')).toBeInTheDocument())
  })

  it('refetches channels on receipt:update socket event (server authoritative)', async () => {
    // Return a channel with unread_count 3 initially, then 0 after receipt:update
    let channelsCall = 0
    mockedApi.get.mockImplementation((path: string) => {
      if (path === '/api/teams/') return Promise.resolve({ data: [{ id: 1, name: 'team1', display_name: 'Team 1' }] })
      if (path.startsWith('/api/channels/')) {
        channelsCall += 1
        const unread = channelsCall === 1 ? 3 : 0
        return Promise.resolve({ data: [{ id: 20, name: 'chan2', display_name: 'Chan2', type: 'O', team_id: 1, unread_count: unread }] })
      }
      if (path === '/api/channels/?team_id=1') return Promise.resolve({ data: [] })
      return Promise.resolve({ data: [] })
    })

    render(
      <MemoryRouter>
        <Sidebar />
      </MemoryRouter>
    )

    // Initial unread badge should show 3
    await waitFor(() => expect(screen.getByTestId('channel-unread-20')).toHaveTextContent('3'))

    // Simulate receipt:update socket event
    expect(socketEventHandlers['receipt:update']).toBeDefined()
    socketEventHandlers['receipt:update']!({ channel_id: 20, user_id: 2, last_read_message_id: null })

    // Sidebar should refetch and remove the unread badge for that channel
    await waitFor(() => expect(screen.queryByTestId('channel-unread-20')).toBeNull())
  })

  it('refetches channels on unread_update presence event (server authoritative)', async () => {
    // Return a channel with unread_count 4 initially, then 0 after unread_update
    let channelsCall = 0
    mockedApi.get.mockImplementation((path: string) => {
      if (path === '/api/teams/') return Promise.resolve({ data: [{ id: 1, name: 'team1', display_name: 'Team 1' }] })
      if (path.startsWith('/api/channels/')) {
        channelsCall += 1
        const unread = channelsCall === 1 ? 4 : 0
        return Promise.resolve({ data: [{ id: 21, name: 'chan3', display_name: 'Chan3', type: 'O', team_id: 1, unread_count: unread }] })
      }
      if (path === '/api/channels/?team_id=1') return Promise.resolve({ data: [] })
      return Promise.resolve({ data: [] })
    })

    render(
      <MemoryRouter>
        <Sidebar />
      </MemoryRouter>
    )

    // Initial unread badge should show 4
    await waitFor(() => expect(screen.getByTestId('channel-unread-21')).toHaveTextContent('4'))

    // Simulate presence unread_update event
    expect(eventHandler).not.toBeNull()
    eventHandler!({ type: 'unread_update', channel_id: 21, unread_count: 0 })

    // Sidebar should refetch and remove the unread badge for that channel
    await waitFor(() => expect(screen.queryByTestId('channel-unread-21')).toBeNull())
  })

  it('refetches channels when a channels:refetch event is dispatched', async () => {
    let channelsCall = 0
    mockedApi.get.mockImplementation((path: string) => {
      if (path === '/api/teams/') return Promise.resolve({ data: [{ id: 1, name: 'team1', display_name: 'Team 1' }] })
      if (path.startsWith('/api/channels/')) {
        channelsCall += 1
        const unread = channelsCall === 1 ? 5 : 0
        return Promise.resolve({ data: [{ id: 22, name: 'chan4', display_name: 'Chan4', type: 'O', team_id: 1, unread_count: unread }] })
      }
      if (path === '/api/channels/?team_id=1') return Promise.resolve({ data: [] })
      return Promise.resolve({ data: [] })
    })

    render(
      <MemoryRouter>
        <Sidebar />
      </MemoryRouter>
    )

    // Initial unread badge should show 5
    await waitFor(() => expect(screen.getByTestId('channel-unread-22')).toHaveTextContent('5'))

    // Dispatch the custom event (this simulates readReceipts triggering a refetch after POST)
    window.dispatchEvent(new CustomEvent('channels:refetch', { detail: { channel_id: 22 } }))

    // Sidebar should refetch and remove the unread badge for that channel
    await waitFor(() => expect(screen.queryByTestId('channel-unread-22')).toBeNull())
  })
})
