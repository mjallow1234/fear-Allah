import { useState } from 'react'
import api from '../services/api'
import { useNavigate } from 'react-router-dom'

export default function Register() {
  const navigate = useNavigate()
  const [email, setEmail] = useState('')
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      const res = await api.post('/api/auth/register', { email, password, username })
      if (res?.data?.access_token) {
        // navigate to login page
        navigate('/login')
      }
    } catch (err: any) {
      setError(err?.response?.data?.detail || 'Registration failed')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-900">
      <div className="max-w-md w-full bg-[#111215] p-8 rounded">
        <h1 className="text-2xl text-white font-bold mb-4">Register</h1>
        {error && <div className="text-red-400 mb-2">{error}</div>}
        <form onSubmit={handleSubmit}>
          <label className="block text-sm text-gray-200 mb-1">Email</label>
          <input required type="email" value={email} onChange={(e) => setEmail(e.target.value)} className="w-full p-3 bg-[#1e1f22] border border-[#3f4147] rounded text-white focus:outline-none mb-3" />
          <label className="block text-sm text-gray-200 mb-1">Username</label>
          <input required type="text" value={username} onChange={(e) => setUsername(e.target.value)} className="w-full p-3 bg-[#1e1f22] border border-[#3f4147] rounded text-white focus:outline-none mb-3" />
          <label className="block text-sm text-gray-200 mb-1">Password</label>
          <input required type="password" value={password} onChange={(e) => setPassword(e.target.value)} className="w-full p-3 bg-[#1e1f22] border border-[#3f4147] rounded text-white focus:outline-none mb-4" />
          <button type="submit" disabled={loading} className="w-full p-3 bg-[#5865f2] text-white font-medium rounded hover:bg-[#4752c4] transition-colors">
            {loading ? 'Registering...' : 'Register'}
          </button>
        </form>
      </div>
    </div>
  )
}

