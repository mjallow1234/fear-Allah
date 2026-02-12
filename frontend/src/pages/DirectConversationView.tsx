import { useEffect, useState } from 'react'
import ConversationMessageView from '../components/ConversationMessageView'
import { useParams } from 'react-router-dom'
import api from '../services/api'

export default function DirectConversationView() {
  const { convId } = useParams<{ convId: string }>()
  const convNum = convId ? Number(convId) : undefined

  const [memberUsernames, setMemberUsernames] = useState<Record<number, string> | null>(null)

  useEffect(() => {
    if (!convNum) return

    // Fetch the conversation list and resolve participant usernames
    api.get('/api/direct-conversations/')
      .then((res: any) => {
        const convs = Array.isArray(res.data) ? res.data : []
        const conv = convs.find((c: any) => c.id === convNum)
        if (!conv) return
        const ids: number[] = conv.participant_ids || []
        // Fetch each user and build map
        Promise.all(ids.map(id => api.get(`/api/users/${id}`).then((r: any) => r.data).catch(() => null)))
          .then((users: any[]) => {
            const map: Record<number, string> = {}
            for (const u of users) {
              if (u && u.id) map[u.id] = u.username
            }
            setMemberUsernames(map)
          })
      })
      .catch(() => setMemberUsernames(null))
  }, [convNum])

  if (!convNum) return <div />

  return (
    <div className="flex h-full">
      <div className="flex flex-col flex-1 h-full">
        <ConversationMessageView
          mode="direct"
          conversationId={convNum}
          memberUsernames={memberUsernames || undefined}
        />
      </div>
    </div>
  )
}
