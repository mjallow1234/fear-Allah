import { useState } from 'react'
import { useAuthStore } from '../stores/authStore'
import { useNavigate } from 'react-router-dom'
import { AlertCircle, Check, Lock } from 'lucide-react'
import api from '../services/api'

export default function Profile() {
  const user = useAuthStore((state) => state.user)
  const logout = useAuthStore((state) => state.logout)
  const updateUser = useAuthStore((state) => state.updateUser)
  const navigate = useNavigate()

  const [displayName, setDisplayName] = useState(user?.display_name || '')
  const [avatarUrl, setAvatarUrl] = useState(user?.avatar_url || '')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState(false)

  const hasChanges = displayName !== (user?.display_name || '') || avatarUrl !== (user?.avatar_url || '')

  const handleSave = async () => {
    setError(null)
    setSuccess(false)
    setLoading(true)

    try {
      const response = await api.put('/api/users/me', {
        display_name: displayName || null,
        avatar_url: avatarUrl || null,
      })

      // Update authStore with new data
      updateUser({
        display_name: response.data.display_name,
        avatar_url: response.data.avatar_url,
      })

      setSuccess(true)
      setTimeout(() => setSuccess(false), 3000)
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to update profile')
    } finally {
      setLoading(false)
    }
  }

  const handleLogout = () => {
    logout()
    navigate('/login')
  }

  const formatLastLogin = (lastLoginAt: string | null) => {
    if (!lastLoginAt) return 'First login'
    
    const now = new Date()
    const loginDate = new Date(lastLoginAt)
    const diffMs = now.getTime() - loginDate.getTime()
    const diffMins = Math.floor(diffMs / 60000)
    const diffHours = Math.floor(diffMins / 60)
    const diffDays = Math.floor(diffHours / 24)

    if (diffMins < 1) return 'Just now'
    if (diffMins < 60) return `${diffMins} minute${diffMins !== 1 ? 's' : ''} ago`
    if (diffHours < 24) return `${diffHours} hour${diffHours !== 1 ? 's' : ''} ago`
    if (diffDays < 7) return `${diffDays} day${diffDays !== 1 ? 's' : ''} ago`
    return loginDate.toLocaleDateString()
  }

  return (
    <div className="p-6 max-w-2xl mx-auto">
      <h1 className="text-2xl font-bold text-white mb-6">Profile</h1>
      
      <div className="bg-[#2b2d31] rounded-lg p-6 mb-6">
        <div className="flex items-center gap-4 mb-6">
          {avatarUrl ? (
            <img 
              src={avatarUrl} 
              alt="Avatar" 
              className="w-20 h-20 rounded-full object-cover"
              onError={(e) => {
                // Fallback to initials if image fails to load
                e.currentTarget.style.display = 'none'
                e.currentTarget.nextElementSibling?.classList.remove('hidden')
              }}
            />
          ) : null}
          <div 
            className={`w-20 h-20 rounded-full bg-[#5865f2] flex items-center justify-center text-white text-2xl font-bold ${avatarUrl ? 'hidden' : ''}`}
          >
            {displayName?.charAt(0) || user?.username?.charAt(0) || 'U'}
          </div>
          <div>
            <h2 className="text-xl font-semibold text-white">
              {displayName || user?.username}
            </h2>
            <p className="text-[#949ba4]">@{user?.username}</p>
            <p className="text-[#949ba4] text-sm">{user?.email}</p>
            <p className="text-[#72767d] text-xs mt-1">
              Last login: {formatLastLogin((user as any)?.last_login_at)}
            </p>
          </div>
        </div>

        <div className="space-y-4">
          <div>
            <label className="block text-[#b5bac1] text-sm font-medium mb-2">
              Username
            </label>
            <input
              type="text"
              value={user?.username || ''}
              className="w-full p-3 bg-[#1e1f22] border border-[#3f4147] rounded text-[#72767d] cursor-not-allowed"
              disabled
            />
            <p className="text-xs text-[#72767d] mt-1">Username cannot be changed</p>
          </div>

          <div>
            <label className="block text-[#b5bac1] text-sm font-medium mb-2">
              Display Name
            </label>
            <input
              type="text"
              value={displayName}
              onChange={(e) => setDisplayName(e.target.value)}
              className="w-full p-3 bg-[#1e1f22] border border-[#3f4147] rounded text-white focus:outline-none focus:border-[#5865f2]"
              placeholder="Enter display name"
            />
          </div>

          <div>
            <label className="block text-[#b5bac1] text-sm font-medium mb-2">
              Avatar URL
            </label>
            <input
              type="text"
              value={avatarUrl}
              onChange={(e) => setAvatarUrl(e.target.value)}
              className="w-full p-3 bg-[#1e1f22] border border-[#3f4147] rounded text-white focus:outline-none focus:border-[#5865f2]"
              placeholder="https://example.com/avatar.jpg"
            />
            <p className="text-xs text-[#72767d] mt-1">Enter an image URL for your avatar</p>
          </div>

          <div>
            <label className="block text-[#b5bac1] text-sm font-medium mb-2">
              Email
            </label>
            <input
              type="email"
              value={user?.email || ''}
              className="w-full p-3 bg-[#1e1f22] border border-[#3f4147] rounded text-[#72767d] cursor-not-allowed"
              disabled
            />
            <p className="text-xs text-[#72767d] mt-1">Email cannot be changed</p>
          </div>
        </div>

        {error && (
          <div className="mt-4 flex items-center gap-2 bg-red-500/10 border border-red-500/30 rounded p-3">
            <AlertCircle size={18} className="text-red-400 flex-shrink-0" />
            <span className="text-red-400 text-sm">{error}</span>
          </div>
        )}

        {success && (
          <div className="mt-4 flex items-center gap-2 bg-green-500/10 border border-green-500/30 rounded p-3">
            <Check size={18} className="text-green-400 flex-shrink-0" />
            <span className="text-green-400 text-sm">Profile updated successfully</span>
          </div>
        )}

        <div className="mt-6 flex gap-3">
          <button
            onClick={handleSave}
            disabled={!hasChanges || loading}
            className="px-4 py-2 bg-[#5865f2] text-white rounded hover:bg-[#4752c4] disabled:bg-[#4752c4]/50 disabled:cursor-not-allowed transition-colors"
          >
            {loading ? 'Saving...' : 'Save Changes'}
          </button>
          <button
            onClick={() => {
              setDisplayName(user?.display_name || '')
              setAvatarUrl(user?.avatar_url || '')
              setError(null)
              setSuccess(false)
            }}
            disabled={!hasChanges || loading}
            className="px-4 py-2 bg-transparent border border-[#3f4147] text-[#b5bac1] rounded hover:bg-[#1e1f22] disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            Reset
          </button>
        </div>
      </div>

      {/* Security Section */}
      <div className="bg-[#2b2d31] rounded-lg p-6 mb-6">
        <h2 className="text-lg font-semibold text-white mb-4">Security</h2>
        
        {user?.must_change_password && (
          <div className="mb-4 flex items-center gap-2 bg-yellow-500/10 border border-yellow-500/30 rounded p-3">
            <AlertCircle size={18} className="text-yellow-400 flex-shrink-0" />
            <span className="text-yellow-400 text-sm">You are required to change your password</span>
          </div>
        )}

        <button
          onClick={() => navigate('/change-password')}
          className="flex items-center gap-2 px-4 py-2 bg-[#1e1f22] border border-[#3f4147] text-white rounded hover:bg-[#313338] transition-colors"
        >
          <Lock size={18} />
          <span>Change Password</span>
        </button>
      </div>

      {/* Account Actions */}
      <div className="bg-[#2b2d31] rounded-lg p-6">
        <h2 className="text-lg font-semibold text-white mb-4">Account</h2>
        <button
          onClick={handleLogout}
          className="px-4 py-2 bg-red-600 text-white rounded hover:bg-red-700 transition-colors"
        >
          Sign Out
        </button>
      </div>
    </div>
  )
}
