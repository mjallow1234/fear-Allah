// React import not required for JSX with the automatic runtime

export default function Message({ message }: { message: any }) {
  return (
    <div className="message p-2 border-b">
      <div className="flex items-baseline justify-between">
        <div className="author font-bold">{message.author}</div>
        {message.created_at && (
          <div className="text-xs text-gray-500 ml-2">
            {new Date(message.created_at).toLocaleString()}
          </div>
        )}
      </div>
      <div className="content mt-1">{message.content}</div>
    </div>
  )
} 
