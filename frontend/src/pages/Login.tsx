import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuthStore } from '../stores/authStore'
import api from '../services/api'
import { extractAxiosError } from '../utils/errorUtils'

export default function Login() {
  const [identifier, setIdentifier] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const navigate = useNavigate()
  const login = useAuthStore((state) => state.login)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    setIsLoading(true)

    try {
      const response = await api.post('/api/auth/login', {
        identifier,
        password,
      })
      login(response.data.access_token, response.data.user)
      navigate('/')
    } catch (err: any) {
      setError(extractAxiosError(err, 'Login failed'))
    } finally {
      setIsLoading(false)
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-[#313338]">
      <div className="bg-[#1e1f22] p-8 rounded-lg shadow-xl w-full max-w-md">
        <h1 className="text-2xl font-bold text-white text-center mb-6">
          fear-Allah
        </h1>
        <p className="text-[#b5bac1] text-center mb-8">
          Welcome back! Sign in to continue.
        </p>

        {error && (
          <div className="bg-red-500/20 text-red-400 p-3 rounded mb-4 text-sm">
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-[#b5bac1] text-sm font-medium mb-2">
              Email or Username
            </label>
            <input
              type="text"
              value={identifier}
              onChange={(e) => setIdentifier(e.target.value)}
              className="w-full p-3 bg-[#1e1f22] border border-[#3f4147] rounded text-white focus:outline-none focus:border-[#5865f2]"
              required
            />
          </div>

          <div>
            <label className="block text-[#b5bac1] text-sm font-medium mb-2">
              Password
            </label>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="w-full p-3 bg-[#1e1f22] border border-[#3f4147] rounded text-white focus:outline-none focus:border-[#5865f2]"
              required
            />
          </div>

          <button
            type="submit"
            disabled={isLoading}
            className="w-full p-3 bg-[#5865f2] text-white font-medium rounded hover:bg-[#4752c4] transition-colors disabled:opacity-50"
          >
            {isLoading ? 'Signing in...' : 'Sign In'}
          </button>
        </form>

        <p className="text-[#b5bac1] text-sm text-center mt-6">
          Don't have an account?{' '}
          <a href="/register" className="text-[#5865f2] hover:underline">
            Register
          </a>
        </p>
      </div>
    </div>
  )
}
