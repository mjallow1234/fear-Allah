'use client'

import { useState } from 'react'

export default function RegisterPage() {
  const [username, setUsername] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setError(null)
    setLoading(true)

    const res = await fetch('/api/auth/register', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username, email, password }),
    })

    setLoading(false)

    if (!res.ok) {
      const data = await res.json()
      setError(data.detail || 'Registration failed')
      return
    }

    window.location.href = '/login'
  }

  return (
    <>
      <h1 className="text-2xl font-semibold mb-6">Create account</h1>

      {error && <div className="mb-4 text-sm text-red-600">{error}</div>}

      <form onSubmit={handleSubmit} className="space-y-4">
        <input
          type="text"
          placeholder="Username"
          value={username}
          onChange={e => setUsername(e.target.value)}
          required
          className="w-full border rounded px-3 py-2"
        />

        <input
          type="email"
          placeholder="Email"
          value={email}
          onChange={e => setEmail(e.target.value)}
          required
          className="w-full border rounded px-3 py-2"
        />

        <input
          type="password"
          placeholder="Password"
          value={password}
          onChange={e => setPassword(e.target.value)}
          required
          className="w-full border rounded px-3 py-2"
        />

        <button
          type="submit"
          disabled={loading}
          className="w-full bg-black text-white py-2 rounded"
        >
          {loading ? 'Creating…' : 'Create account'}
        </button>
      </form>

      <p className="mt-4 text-sm text-center">
        Already have an account? <a href="/login" className="underline">Sign in</a>
      </p>
    </>
  )
}
