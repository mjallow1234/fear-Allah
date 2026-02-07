import { useNavigate } from 'react-router-dom'
import { useAuthStore } from '../stores/authStore'
import { Sparkles } from 'lucide-react'
import { useState } from 'react'
import api from '../services/api'

export default function Welcome() {
  const navigate = useNavigate()
  const { user, updateUser } = useAuthStore()
  const [loading, setLoading] = useState(false)

  const handleEnterWorkspace = async () => {
    setLoading(true)
    
    try {
      // Mark welcome as dismissed in localStorage
      localStorage.setItem('welcome_dismissed', 'true')
      
      // Clear the first login flag
      updateUser({ is_first_login: false })
      
      // Find best channel to redirect to
      // 1. Try to get most recent DM
      const dmResponse = await api.get('/api/channels/direct/list')
      const dmChannels = Array.isArray(dmResponse.data) ? dmResponse.data : []
      
      if (dmChannels.length > 0) {
        // Redirect to first DM
        navigate(`/channels/${dmChannels[0].id}`)
        return
      }
      
      // 2. Try to find #general channel
      const channelsResponse = await api.get('/api/channels/')
      const channels = Array.isArray(channelsResponse.data) ? channelsResponse.data : []
      
      const generalChannel = channels.find(c => c.name === 'general')
      if (generalChannel) {
        navigate(`/channels/${generalChannel.id}`)
        return
      }
      
      // 3. Fallback to first available channel
      if (channels.length > 0) {
        navigate(`/channels/${channels[0].id}`)
        return
      }
      
      // 4. Ultimate fallback to home
      navigate('/')
    } catch (error) {
      console.error('Failed to find channel:', error)
      // Fallback to home on error
      navigate('/')
    } finally {
      setLoading(false)
    }
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
          disabled={loading}
          className="bg-[#5865f2] hover:bg-[#4752c4] disabled:bg-[#4752c4]/50 disabled:cursor-not-allowed text-white text-lg font-medium py-3 px-8 rounded-lg transition-colors"
        >
          {loading ? 'Loading...' : 'Enter Workspace'}
        </button>

        <div className="mt-8 text-[#72767d] text-sm">
          <p className="mb-2">بسم الله الرحمن الرحيم</p>
          <p>In the name of Allah, the Most Gracious, the Most Merciful</p>
        </div>
      </div>
    </div>
  )
}
