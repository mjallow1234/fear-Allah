// React import not required for JSX with the automatic runtime

export default function Sidebar() {
  return (
    <aside className="p-4 border-r">
      <h3 className="font-bold mb-2">Channels</h3>
      <ul>
        <li># general</li>
        <li># random</li>
        <li># dev</li>
      </ul>
    </aside>
  )
}
