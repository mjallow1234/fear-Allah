import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuthStore } from '../stores/authStore'
import api from '../services/api'
import { AlertCircle, Lock } from 'lucide-react'

export default function ChangePassword() {
  const navigate = useNavigate()
  const { user, updateUser } = useAuthStore()
  
  const [currentPassword, setCurrentPassword] = useState('')
  const [newPassword, setNewPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError(null)

    // Validation
    if (!currentPassword || !newPassword || !confirmPassword) {
      setError('All fields are required')
      return
    }

    if (newPassword !== confirmPassword) {
      setError('New passwords do not match')
      return
    }

    if (newPassword.length < 8) {
      setError('New password must be at least 8 characters')
      return
    }

    if (newPassword === currentPassword) {
      setError('New password must be different from current password')
      return
    }

    setLoading(true)

    try {
      const response = await api.post('/api/auth/change-password', {
        current_password: currentPassword,
        new_password: newPassword,
      })

      // Update user state to clear must_change_password flag
      updateUser({ must_change_password: false })

      // Redirect to home
      navigate('/')
    } catch (err: any) {
      const message = err.response?.data?.detail || 'Failed to change password'
      setError(message)
    } finally {
      setLoading(false)
    }
  }

  const isForced = user?.must_change_password === true

  return (
    <div className="min-h-screen bg-[#313338] flex items-center justify-center p-4">
      <div className="w-full max-w-md bg-[#2b2d31] rounded-lg p-8 shadow-lg">
        <div className="flex items-center justify-center mb-6">
          <div className="bg-[#5865f2] p-3 rounded-full">
            <Lock size={32} className="text-white" />
          </div>
        </div>

        <h1 className="text-2xl font-bold text-white text-center mb-2">
          Change Password
        </h1>
        
        {isForced && (
          <div className="bg-yellow-500/10 border border-yellow-500/30 rounded p-3 mb-4">
            <p className="text-yellow-400 text-sm text-center">
              Your administrator has required you to change your password.
            </p>
          </div>
        )}

        <p className="text-[#b5bac1] text-center mb-6">
          {isForced 
            ? 'Please choose a new password to continue.'
            : 'Update your account password.'}
        </p>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-[#b5bac1] mb-2">
              Current Password
            </label>
            <input
              type="password"
              value={currentPassword}
              onChange={(e) => setCurrentPassword(e.target.value)}
              className="w-full px-3 py-2 bg-[#1e1f22] border border-[#1e1f22] rounded text-white focus:outline-none focus:border-[#5865f2]"
              required
              disabled={loading}
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-[#b5bac1] mb-2">
              New Password
            </label>
            <input
              type="password"
              value={newPassword}
              onChange={(e) => setNewPassword(e.target.value)}
              className="w-full px-3 py-2 bg-[#1e1f22] border border-[#1e1f22] rounded text-white focus:outline-none focus:border-[#5865f2]"
              required
              disabled={loading}
              minLength={8}
            />
            <p className="text-xs text-[#72767d] mt-1">Minimum 8 characters</p>
          </div>

          <div>
            <label className="block text-sm font-medium text-[#b5bac1] mb-2">
              Confirm New Password
            </label>
            <input
              type="password"
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
              className="w-full px-3 py-2 bg-[#1e1f22] border border-[#1e1f22] rounded text-white focus:outline-none focus:border-[#5865f2]"
              required
              disabled={loading}
            />
          </div>

          {error && (
            <div className="flex items-center gap-2 bg-red-500/10 border border-red-500/30 rounded p-3">
              <AlertCircle size={18} className="text-red-400 flex-shrink-0" />
              <span className="text-red-400 text-sm">{error}</span>
            </div>
          )}

          <button
            type="submit"
            disabled={loading}
            className="w-full bg-[#5865f2] hover:bg-[#4752c4] disabled:bg-[#4752c4]/50 text-white font-medium py-2 px-4 rounded transition-colors"
          >
            {loading ? 'Changing Password...' : 'Change Password'}
          </button>

          {!isForced && (
            <button
              type="button"
              onClick={() => navigate(-1)}
              disabled={loading}
              className="w-full bg-transparent hover:bg-[#1e1f22] text-[#b5bac1] font-medium py-2 px-4 rounded transition-colors"
            >
              Cancel
            </button>
          )}
        </form>
      </div>
    </div>
  )
}
