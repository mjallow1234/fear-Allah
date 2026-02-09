import { usePreferencesStore } from '../stores/preferencesStore'

export default function Settings() {
  const { preferences, setPreference } = usePreferencesStore()

  return (
    <div className="p-6 max-w-2xl mx-auto">
      <h1 className="text-2xl font-bold text-white mb-6">Settings</h1>
      
      <div className="space-y-6">
        <section className="bg-[#2b2d31] rounded-lg p-4">
          <h2 className="text-lg font-semibold text-white mb-4">Appearance</h2>
          <div className="space-y-3">
            <label className="flex items-center justify-between">
              <span className="text-[#b5bac1]">Dark Mode</span>
              <input
                type="checkbox"
                checked={preferences.dark_mode}
                onChange={(e) => setPreference('dark_mode', e.target.checked)}
                className="w-5 h-5"
              />
            </label>
            <label className="flex items-center justify-between">
              <span className="text-[#b5bac1]">Compact Mode</span>
              <input
                type="checkbox"
                checked={preferences.compact_mode}
                onChange={(e) => setPreference('compact_mode', e.target.checked)}
                className="w-5 h-5"
              />
            </label>
          </div>
        </section>

        <section className="bg-[#2b2d31] rounded-lg p-4">
          <h2 className="text-lg font-semibold text-white mb-4">Notifications</h2>
          <div className="space-y-3">
            <label className="flex items-center justify-between">
              <span className="text-[#b5bac1]">Enable Notifications</span>
              <input
                type="checkbox"
                checked={preferences.notifications}
                onChange={(e) => setPreference('notifications', e.target.checked)}
                className="w-5 h-5"
              />
            </label>
            <label className="flex items-center justify-between">
              <span className="text-[#b5bac1]">Sound</span>
              <input
                type="checkbox"
                checked={preferences.sound}
                onChange={(e) => setPreference('sound', e.target.checked)}
                className="w-5 h-5"
              />
            </label>
          </div>
        </section>
      </div>
    </div>
  )
}
