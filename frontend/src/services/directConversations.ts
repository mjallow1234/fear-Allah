import api from './api'

export type DirectConversationSummary = {
  id: number
  created_by_user_id: number
  participant_ids: number[]
  created_at: string
}

export async function fetchDirectConversations(): Promise<DirectConversationSummary[]> {
  const res = await api.get('/api/direct-conversations/')
  return Array.isArray(res.data) ? res.data : []
}

export async function createDirectConversation(otherUserId: number): Promise<DirectConversationSummary> {
  const res = await api.post('/api/direct-conversations/', { other_user_id: otherUserId })
  return res.data
}

export async function fetchDirectConversationMessages(convId: number, before?: number | null, limit = 50): Promise<{ messages: any[]; has_more: boolean }> {
  const params = new URLSearchParams()
  params.append('limit', String(limit))
  if (before) params.append('before', String(before))
  const res = await api.get(`/api/direct-conversations/${convId}/messages?${params.toString()}`)
  return { messages: res.data ?? [], has_more: false }
}

export async function postDirectConversationMessage(convId: number, content: string, parentId?: number | null) {
  const payload: any = { content }
  if (parentId) payload.parent_id = parentId
  const res = await api.post(`/api/direct-conversations/${convId}/messages`, payload)
  return res.data
}

export async function fetchDirectConversationReads(convId: number) {
  const res = await api.get(`/api/direct-conversations/${convId}/reads`)
  return Array.isArray(res.data) ? res.data : []
}

export async function markDirectConversationRead(convId: number, last_read_message_id: number) {
  const res = await api.post(`/api/direct-conversations/${convId}/read`, { last_read_message_id })
  return res.data
}
