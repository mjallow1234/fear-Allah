import { useEffect, useState, useRef } from 'react'

export default function useChatWs(channelId: number, token?: string) {
  const [messages, setMessages] = useState<any[]>([])
  const wsRef = useRef<WebSocket | null>(null)

  useEffect(() => {
    if (!channelId) return
    const wsUrl = `ws://localhost:8000/ws/chat/${channelId}?token=${token || ''}`
    const ws = new WebSocket(wsUrl)
    wsRef.current = ws
    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data)
        if (data.type === 'message') {
          setMessages(prev => [...prev, data])
        }
      } catch (e) {
        console.error(e)
      }
    }
    return () => {
      ws.close()
      wsRef.current = null
    }
  }, [channelId, token])

  function sendMessage(content: string) {
    if (!wsRef.current) return
    const payload = { type: 'message', content }
    wsRef.current.send(JSON.stringify(payload))
  }

  return { messages, sendMessage }
}
