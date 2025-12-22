import api from './api'

export type ChannelSummary = {
  id: number
  name: string
  display_name?: string | null
  description?: string | null
  type?: string
  team_id?: number | null
}

export type ChannelDetail = ChannelSummary & {
  is_archived?: boolean
  archived_at?: string | null
  retention_days?: number
  created_at?: string | null
  updated_at?: string | null
}

let channelsCache: Promise<ChannelSummary[]> | null = null

export async function fetchChannels(): Promise<ChannelSummary[]> {
  if (channelsCache) return channelsCache
  channelsCache = api.get('/api/channels/').then((res) => {
    const data = res.data.channels ?? res.data
    // normalize to array of channel summaries
    return (Array.isArray(data) ? data : []) as ChannelSummary[]
  }).catch((err) => {
    channelsCache = null
    throw err
  })
  return channelsCache
}

export async function fetchChannelById(channelId: number): Promise<ChannelDetail> {
  const res = await api.get(`/api/channels/${channelId}`)
  return res.data as ChannelDetail
}

export async function fetchChannelMessages(channelId: number, before?: number | null, limit = 50): Promise<{ messages: any[]; has_more: boolean }> {
  const params = new URLSearchParams()
  params.append('limit', String(limit))
  if (before) params.append('before', String(before))
  const res = await api.get(`/api/channels/${channelId}/messages?${params.toString()}`)
  return { messages: res.data.messages ?? [], has_more: Boolean(res.data.has_more) }
}

// For tests or development: allow clearing cache
export function clearChannelsCache() {
  channelsCache = null
}
