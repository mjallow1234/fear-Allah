/**
 * Merge messages by ID, preserving attachments from both sources.
 * Used to prevent realtime-added attachments from being lost on re-fetch.
 */

interface Attachment {
  id: number
  filename: string
  file_size?: number
  mime_type?: string
  url: string
  created_at?: string
}

interface MessageWithAttachments {
  id: number
  attachments?: Attachment[]
  [key: string]: any
}

/**
 * Merge two arrays of attachments by ID.
 * Attachments from `incoming` take precedence, but any attachments
 * in `existing` that aren't in `incoming` are preserved.
 */
function mergeAttachments(
  existing: Attachment[] | undefined,
  incoming: Attachment[] | undefined
): Attachment[] {
  if (!existing?.length && !incoming?.length) return []
  if (!existing?.length) return incoming || []
  if (!incoming?.length) return existing

  const merged = new Map<number, Attachment>()
  
  // Add existing attachments first
  for (const att of existing) {
    merged.set(att.id, att)
  }
  
  // Incoming attachments override existing ones with same ID
  for (const att of incoming) {
    merged.set(att.id, att)
  }
  
  return Array.from(merged.values())
}

/**
 * Merge two arrays of messages by ID.
 * - Messages from `incoming` take precedence for all fields except attachments
 * - Attachments are merged to preserve realtime-added ones
 * - Messages only in `existing` are dropped (they may have been deleted)
 * - Messages only in `incoming` are added
 */
export function mergeMessagesById<T extends MessageWithAttachments>(
  existing: T[] | null | undefined,
  incoming: T[]
): T[] {
  if (!existing?.length) return incoming
  if (!incoming?.length) return existing

  // Build a map of existing messages for quick lookup
  const existingMap = new Map<number, T>()
  for (const msg of existing) {
    existingMap.set(msg.id, msg)
  }

  // Merge incoming messages with existing ones
  return incoming.map((incomingMsg) => {
    const existingMsg = existingMap.get(incomingMsg.id)
    
    if (!existingMsg) {
      // New message, just use incoming
      return incomingMsg
    }

    // Merge attachments from both sources
    const mergedAttachments = mergeAttachments(
      existingMsg.attachments,
      incomingMsg.attachments
    )

    return {
      ...incomingMsg,
      attachments: mergedAttachments.length > 0 ? mergedAttachments : undefined,
    }
  })
}
