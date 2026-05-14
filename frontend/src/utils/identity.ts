/**
 * Centralized identity resolution for human-readable display names.
 *
 * ALL systems that need to show a sender/author name MUST use these helpers.
 * Never construct inline "user_N" fallback strings for user-visible output.
 */

/**
 * Resolve best human-readable name for a user object.
 * Priority: display_name > username > full_name > "Unknown"
 */
export function resolveDisplayName(user: {
  display_name?: string | null
  username?: string | null
  full_name?: string | null
} | null | undefined): string {
  if (!user) return 'Unknown'

  return (
    user.display_name?.trim()
    || user.username?.trim()
    || user.full_name?.trim()
    || 'Unknown'
  )
}

/**
 * Resolve best human-readable sender/author name from a realtime payload.
 *
 * Accepts any payload shape that may carry identity fields — notification:new,
 * message:new, thread:reply, mention events — and returns the first non-empty name.
 * Priority: sender_display_name > sender_username > author_display_name > author_username > "Unknown"
 */
export function resolveSenderName(payload: {
  sender_display_name?: string | null
  sender_username?: string | null
  author_display_name?: string | null
  author_username?: string | null
} | null | undefined): string {
  if (!payload) return 'Unknown'

  return (
    payload.sender_display_name?.trim()
    || payload.sender_username?.trim()
    || payload.author_display_name?.trim()
    || payload.author_username?.trim()
    || 'Unknown'
  )
}

/**
 * Repair already-corrupted notification titles stored in the database.
 *
 * ONLY repairs titles matching the known "New message from ...", "New reply from ...",
 * and "@... mentioned you" patterns. All other titles are returned unchanged.
 *
 * This provides backward compatibility for notifications created before the
 * identity resolution fix was deployed.
 */
/**
 * Resolve the best navigation route for a notification.
 *
 * Accepts any notification-shaped object and returns the route string to navigate to,
 * or null if no route can be determined (caller should handle gracefully — no crash).
 *
 * Priority:
 *   0. extra_data.action_url  (automation / inventory custom routes)
 *   1. dm_reply  → /direct/:conv_id?message=:parent_id
 *   2. dm_message / dm  → /direct/:conv_id
 *   3. channel_reply  → /channels/:channel_id?message=:parent_id
 *   4. order_id  → /order-snapshot/:order_id
 *   5. task_id  → /tasks?task=:task_id
 *   6. channel_id  → /channels/:channel_id (+ ?message= if present)
 *   7. extra_data.direct_conversation_id  → /direct/:conv_id (synthetic DM messages)
 */
export function resolveNotificationRoute(notification: {
  type?: string | null
  extra_data?: string | Record<string, unknown> | null
  channel_id?: number | null
  message_id?: number | null
  task_id?: number | null
  order_id?: number | null
  sale_id?: number | null
}): string | null {
  // Parse extra_data — accept both serialised string (from DB/API) and pre-parsed object (from realtime)
  let extra: Record<string, unknown> | null = null
  try {
    if (notification.extra_data) {
      extra = typeof notification.extra_data === 'string'
        ? JSON.parse(notification.extra_data)
        : (notification.extra_data as Record<string, unknown>)
    }
  } catch { /* ignore malformed JSON */ }

  // Priority 0: explicit action_url
  if (extra?.action_url && typeof extra.action_url === 'string') {
    return extra.action_url
  }

  // Priority 1: DM reply
  if (notification.type === 'dm_reply') {
    const convId = extra?.direct_conversation_id
    const parentId = extra?.parent_id
    if (convId && parentId) return `/direct/${convId}?message=${parentId}`
    if (convId) return `/direct/${convId}`
  }

  // Priority 2: DM message
  if (notification.type === 'dm_message' || notification.type === 'dm') {
    const convId = extra?.direct_conversation_id
    if (convId) return `/direct/${convId}`
  }

  // Priority 3: channel reply
  if (notification.type === 'channel_reply') {
    const channelId = notification.channel_id ?? (extra?.channel_id as number | undefined) ?? null
    const parentId = extra?.parent_id
    if (channelId && parentId) return `/channels/${channelId}?message=${parentId}`
    if (channelId) return `/channels/${channelId}`
  }

  // Priority 4: order
  if (notification.order_id) return `/order-snapshot/${notification.order_id}`

  // Priority 4.5: sale
  if (notification.sale_id) return `/sales/${notification.sale_id}`
  const extraSaleId = extra?.sale_id
  if (extraSaleId) return `/sales/${extraSaleId}`

  // Priority 5: task (standalone)
  if (notification.task_id) return `/tasks?task=${notification.task_id}`

  // Priority 6: channel message
  if (notification.channel_id) {
    if (notification.message_id) return `/channels/${notification.channel_id}?message=${notification.message_id}`
    return `/channels/${notification.channel_id}`
  }

  // Priority 7: DM via extra_data (covers synthetic message:new notifications)
  if (extra?.direct_conversation_id) {
    const parentId = extra?.parent_id
    if (parentId) return `/direct/${extra.direct_conversation_id}?message=${parentId}`
    return `/direct/${String(extra.direct_conversation_id)}`
  }

  return null
}

export function repairNotificationTitle(
  title: string,
  senderName: string
): string {
  if (!title || !senderName || senderName === 'Unknown') return title

  if (title.startsWith('New message from ')) {
    return `New message from ${senderName}`
  }

  if (title.startsWith('New reply from ')) {
    return `New reply from ${senderName}`
  }

  if (title.includes('mentioned you')) {
    return `@${senderName} mentioned you`
  }

  return title
}
