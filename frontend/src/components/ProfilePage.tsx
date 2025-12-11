import { useAuthStore } from '../stores/authStore'

export default function ProfilePage() {
  const user = useAuthStore((state) => state.user)

  return (
    <div className="p-6">
      <h2 className="text-xl font-bold text-white mb-4">Profile Page</h2>
      <div className="bg-[#2b2d31] rounded-lg p-6">
        <div className="flex items-center gap-4">
          <div className="w-16 h-16 rounded-full bg-[#5865f2] flex items-center justify-center text-white text-xl font-bold">
            {user?.display_name?.charAt(0) || 'U'}
          </div>
          <div>
            <h3 className="text-lg font-semibold text-white">{user?.display_name}</h3>
            <p className="text-[#949ba4]">@{user?.username}</p>
          </div>
        </div>
      </div>
    </div>
  )
}
