// React import not required for JSX with the automatic runtime

export default function Message({ message }: { message: any }) {
  return (
    <div className="message p-2 border-b">
      <div className="author font-bold">{message.author}</div>
      <div className="content">{message.content}</div>
    </div>
  )
}
