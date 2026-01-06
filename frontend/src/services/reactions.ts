/**
 * Reactions API service
 * Phase 9.4 - Emoji Reactions Frontend
 * 
 * Provides methods for interacting with the reactions API.
 */
import api from './api'

export interface Reaction {
  emoji: string
  count: number
  users: number[]
}

export interface ToggleReactionResponse {
  action: 'added' | 'removed'
  emoji: string
  message_id: number
  reactions: Reaction[]
}

/**
 * Toggle a reaction on a message.
 * If reaction exists, it's removed. If not, it's added.
 */
export async function toggleReaction(
  messageId: number, 
  emoji: string
): Promise<ToggleReactionResponse> {
  const response = await api.post<ToggleReactionResponse>(
    `/api/messages/${messageId}/reactions`,
    { emoji }
  )
  return response.data
}

/**
 * Get all reactions for a message (grouped by emoji).
 */
export async function getReactions(messageId: number): Promise<Reaction[]> {
  const response = await api.get<Reaction[]>(`/api/messages/${messageId}/reactions`)
  return response.data
}

/**
 * Remove a specific reaction (explicit DELETE).
 */
export async function removeReaction(
  messageId: number, 
  emoji: string
): Promise<void> {
  await api.delete(`/api/messages/${messageId}/reactions/${encodeURIComponent(emoji)}`)
}
