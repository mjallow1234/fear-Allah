import api from './api'

export interface MarkNotificationsReadParams {
  direct_conversation_id?: number
  channel_id?: number
  parent_id?: number
  types?: string[]
}

export async function markNotificationsReadFiltered(params: MarkNotificationsReadParams) {
  return api.post('/api/notifications/read-filtered', params)
}
