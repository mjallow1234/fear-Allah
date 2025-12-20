// React import not required for JSX with the automatic runtime
import Composer from './Composer'
import Message from './Message'

export default function ChannelView() {
  // Placeholder UI, would fetch messages via API
  const messages = [{ id: 1, content: 'Hello World', author: 'user1' }]
  return (
    <div className="flex-1 p-4">
      <h2 className="font-bold mb-2">Channel</h2>
      <div className="messages mb-4">
        {messages.map(m => <Message key={m.id} message={m} />)}
      </div>
      <Composer />
    </div>
  )
}
