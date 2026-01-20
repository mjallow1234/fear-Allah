import { Link } from 'react-router-dom'

export default function Unauthorized() {
  return (
    <div style={{ padding: 40 }}>
      <h1 style={{ fontSize: 24, marginBottom: 8 }}>Unauthorized</h1>
      <p style={{ marginBottom: 16 }}>You do not have permission to access this page.</p>
      <p>
        <Link to="/">Return home</Link>
      </p>
    </div>
  )
}
