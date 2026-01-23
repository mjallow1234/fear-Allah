/// <reference types="vitest" />
import { render, screen, fireEvent } from '@testing-library/react'
import TaskCard from './TaskCard'
import { useAuthStore } from '../../stores/authStore'
import { useTaskStore } from '../../stores/taskStore'
import { describe, it, beforeEach, vi, expect } from 'vitest'

const baseTask = {
  id: 1,
  task_type: 'restock',
  status: 'OPEN',
  title: 'Claimable Task',
  description: null,
  created_by_id: 1,
  related_order_id: null,
  metadata: null,
  created_at: new Date().toISOString(),
  updated_at: null,
  assignments: [],
  required_role: 'delivery',
  claimed_by: null,
}

describe('TaskCard claim UI', () => {
  beforeEach(() => {
    // default non-admin delivery user
    useAuthStore.setState({ currentUser: { id: 2, username: 'u2', email: 'u2', display_name: 'U2', avatar_url: null, is_system_admin: false, role: 'delivery' } })
    // reset store claimTask stub
    useTaskStore.setState({ claimTaskId: null, claimTask: vi.fn().mockResolvedValue(true) })
  })

  it('shows Claim button for eligible role when OPEN', () => {
    render(
      <TaskCard
        task={baseTask as any}
        currentUserId={2}
        isCompleting={false}
        onComplete={() => {}}
        onClick={() => {}}
      />
    )

    expect(screen.getByText('Claim')).toBeInTheDocument()
  })

  it('calls claimTask when Claim is clicked', async () => {
    const mockClaim = vi.fn().mockResolvedValue(true)
    useTaskStore.setState({ claimTask: mockClaim, claimTaskId: null })

    render(
      <TaskCard
        task={baseTask as any}
        currentUserId={2}
        isCompleting={false}
        onComplete={() => {}}
        onClick={() => {}}
      />
    )

    const btn = screen.getByText('Claim')
    fireEvent.click(btn)
    expect(mockClaim).toHaveBeenCalledWith(baseTask.id, false)
  })

  it('shows Override Claim for admins when CLAIMED', () => {
    // admin user
    useAuthStore.setState({ currentUser: { id: 9, username: 'admin', email: 'a', display_name: 'Admin', avatar_url: null, is_system_admin: true, role: 'admin' } })
    const claimedTask = { ...baseTask, status: 'CLAIMED', claimed_by: { id: 2, username: 'u2', display_name: 'U2' } }

    render(
      <TaskCard
        task={claimedTask as any}
        currentUserId={9}
        isCompleting={false}
        onComplete={() => {}}
        onClick={() => {}}
      />

    )

    expect(screen.getByText('Override Claim')).toBeInTheDocument()
  })
})