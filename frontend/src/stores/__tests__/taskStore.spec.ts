import { describe, it, expect, vi, beforeEach } from 'vitest'
import { act } from '@testing-library/react'
import { useTaskStore } from '../taskStore'
import api from '../../services/api'

vi.mock('../../services/api')

describe('TaskStore available tasks and claim', () => {
  beforeEach(() => {
    // Reset store
    act(() => {
      useTaskStore.getState().reset()
    })
    vi.resetAllMocks()
  })

  it('fetchAvailableTasks should call API with role param and set availableTasks', async () => {
    const mockResponse = { data: { tasks: [{ id: 1, title: 'T', required_role: 'foreman', status: 'PENDING', created_at: new Date().toISOString(), created_by_id: 1, assignments: [] }] } }
    ;(api.get as unknown as vi.Mock).mockResolvedValueOnce(mockResponse)

    await useTaskStore.getState().fetchAvailableTasks('foreman')

    expect(api.get).toHaveBeenCalledWith('/api/automation/available-tasks', { params: { role: 'foreman' } })
    expect(useTaskStore.getState().availableTasks.length).toBe(1)
  })

  it('claimTask should post to claim endpoint and refresh assignments/available', async () => {
    ;(api.post as unknown as vi.Mock).mockResolvedValueOnce({ data: {} })
    ;(api.get as unknown as vi.Mock).mockResolvedValue({ data: [] }) // used by fetchMyAssignments/fetchAvailableTasks

    const ok = await useTaskStore.getState().claimTask(12345)
    expect(ok).toBe(true)
    expect(api.post).toHaveBeenCalledWith('/api/automation/tasks/12345/claim', {})
    // fetchMyAssignments and fetchAvailableTasks invoked (api.get called at least)
    expect(api.get).toHaveBeenCalled()
  })
})