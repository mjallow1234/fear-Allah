import { useAuthStore } from '../stores/authStore'
import { useNavigate } from 'react-router-dom'

export default function Profile() {
  const user = useAuthStore((state) => state.user)
  const logout = useAuthStore((state) => state.logout)
  const navigate = useNavigate()

  const handleLogout = () => {
    logout()
    navigate('/login')
  }

  return (
    <div className="p-6 max-w-2xl mx-auto">
      <h1 className="text-2xl font-bold text-white mb-6">Profile</h1>
      
      <div className="bg-[#2b2d31] rounded-lg p-6">
        <div className="flex items-center gap-4 mb-6">
          <div className="w-20 h-20 rounded-full bg-[#5865f2] flex items-center justify-center text-white text-2xl font-bold">
            {user?.display_name?.charAt(0) || user?.username?.charAt(0) || 'U'}
          </div>
          <div>
            <h2 className="text-xl font-semibold text-white">
              {user?.display_name || user?.username}
            </h2>
            <p className="text-[#949ba4]">@{user?.username}</p>
            <p className="text-[#949ba4] text-sm">{user?.email}</p>
          </div>
        </div>

        <div className="space-y-4">
          <div>
            <label className="block text-[#b5bac1] text-sm font-medium mb-2">
              Display Name
            </label>
            <input
              type="text"
              defaultValue={user?.display_name || ''}
              className="w-full p-3 bg-[#1e1f22] border border-[#3f4147] rounded text-white focus:outline-none focus:border-[#5865f2]"
            />
          </div>

          <div>
            <label className="block text-[#b5bac1] text-sm font-medium mb-2">
              Email
            </label>
            <input
              type="email"
              defaultValue={user?.email || ''}
              className="w-full p-3 bg-[#1e1f22] border border-[#3f4147] rounded text-white focus:outline-none focus:border-[#5865f2]"
              disabled
            />
          </div>
        </div>

        <div className="mt-6 pt-6 border-t border-[#3f4147]">
          <button
            onClick={handleLogout}
            className="px-4 py-2 bg-red-600 text-white rounded hover:bg-red-700 transition-colors"
          >
            Sign Out
          </button>
        </div>
      </div>
    </div>
  )
}
