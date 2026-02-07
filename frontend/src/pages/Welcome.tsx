import { useNavigate } from 'react-router-dom'
import { useAuthStore } from '../stores/authStore'
import { Sparkles } from 'lucide-react'

export default function Welcome() {
  const navigate = useNavigate()
  const { user, updateUser } = useAuthStore()

  const handleEnterWorkspace = () => {
    // Clear the first login flag
    updateUser({ is_first_login: false })
    // Navigate to home
    navigate('/')
  }

  return (
    <div className="min-h-screen bg-[#313338] flex items-center justify-center p-4">
      <div className="w-full max-w-2xl bg-[#2b2d31] rounded-lg p-12 shadow-lg text-center">
        <div className="flex items-center justify-center mb-8">
          <div className="bg-[#5865f2] p-4 rounded-full">
            <Sparkles size={48} className="text-white" />
          </div>
        </div>

        <h1 className="text-4xl font-bold text-white mb-4">
          السلام عليكم
        </h1>
        
        <p className="text-2xl text-[#b5bac1] mb-8">
          Peace be upon you
        </p>

        <div className="bg-[#1e1f22] rounded-lg p-6 mb-8">
          <p className="text-lg text-[#b5bac1] mb-4">
            Welcome to your workspace, <span className="text-white font-medium">{user?.display_name || user?.username}</span>
          </p>
          <p className="text-[#949ba4]">
            May your work be blessed and productive
          </p>
        </div>

        <button
          onClick={handleEnterWorkspace}
          className="bg-[#5865f2] hover:bg-[#4752c4] text-white text-lg font-medium py-3 px-8 rounded-lg transition-colors"
        >
          Enter Workspace
        </button>

        <div className="mt-8 text-[#72767d] text-sm">
          <p className="mb-2">بسم الله الرحمن الرحيم</p>
          <p>In the name of Allah, the Most Gracious, the Most Merciful</p>
        </div>
      </div>
    </div>
  )
}
