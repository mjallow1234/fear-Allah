import { useState } from 'react'

export default function Composer() {
  const [text, setText] = useState('')
  const send = () => {
    // placeholder - integrate with useChatWs
    console.log('send', text)
    setText('')
  }
  return (
    <div className="composer">
      <input value={text} onChange={e => setText(e.target.value)} className="border p-1 w-full" placeholder="Type a message" />
      <button onClick={send} className="ml-2 px-2 py-1 bg-blue-500 text-white">Send</button>
    </div>
  )
}
