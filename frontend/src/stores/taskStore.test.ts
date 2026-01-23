/// <reference types="vitest" />
import { beforeEach, describe, expect, it, vi } from 'vitest'
import api from '../services/api'
import { useTaskStore } from './taskStore'
import { useAuthStore } from './authStore'

vi.mock('../services/api')
const mockedApi = api as unknown as { post: any; get: any }

describe('taskStore.claimTask', () => {
  beforeEach(() => {
    // reset store state
    useTaskStore.getState().reset()
    useAuthStore.setState({ currentUser: { id: 2, username: 'u2', email: 'u2@example.com', display_name: 'U2', avatar_url: null, is_system_admin: false, role: 'delivery' } })
    mockedApi.post.mockReset()
    mockedApi.get.mockReset()
  })

  it('succeeds and refreshes tasks on 200', async () => {
    const taskId = 123
    // api.post resolves
    mockedApi.post.mockResolvedValue({ data: {} })
    // api.get for fetchMyTasks returns updated tasks
    mockedApi.get.mockImplementation((path: string) => {
      if (path === '/api/automation/tasks') return Promise.resolve({ data: [{ id: taskId, title: 'T1' }] })
      return Promise.resolve({ data: [] })
    })

    const result = await useTaskStore.getState().claimTask(taskId, false)
    expect(result).toBe(true)
    // ensure tasks were refreshed
    expect(useTaskStore.getState().tasks.find(t => t.id === taskId)).toBeDefined()
    expect(useTaskStore.getState().claimTaskId).toBeNull()
  })

  it('handles 409 conflict by setting error and refetching', async () => {
    const taskId = 200
    mockedApi.post.mockRejectedValue({ response: { status: 409, data: { detail: 'Task already claimed' } } })
    // ensure fetchMyTasks is callable
    mockedApi.get.mockResolvedValue({ data: [] })

    const result = await useTaskStore.getState().claimTask(taskId, false)
    expect(result).toBe(false)
    const errVal = useTaskStore.getState().error
    const errStr = typeof errVal === 'string' ? errVal : JSON.stringify(errVal)
    expect(errStr).toMatch(/already claimed/i)
    expect(useTaskStore.getState().claimTaskId).toBeNull()
  })
})