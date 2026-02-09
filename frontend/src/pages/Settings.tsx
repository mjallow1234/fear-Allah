import { usePreferencesStore } from '../stores/preferencesStore'

export default function Settings() {
  const { preferences, setPreference } = usePreferencesStore()

  return (
    <div className="p-6 max-w-2xl mx-auto">
      <h1 className="text-2xl font-bold mb-6" style={{ color: 'var(--text-primary)' }}>Settings</h1>
      
      <div className="space-y-6">
        <section className="rounded-lg p-4" style={{ backgroundColor: 'var(--sidebar-bg)' }}>
          <h2 className="text-lg font-semibold mb-4" style={{ color: 'var(--text-primary)' }}>Appearance</h2>
          <div className="space-y-3">
            <label className="flex items-center justify-between">
              <span style={{ color: 'var(--text-muted)' }}>Dark Mode</span>
              <input
                type="checkbox"
                checked={preferences.dark_mode}
                onChange={(e) => setPreference('dark_mode', e.target.checked)}
                className="w-5 h-5"
              />
            </label>
            <label className="flex items-center justify-between">
              <span style={{ color: 'var(--text-muted)' }}>Compact Mode</span>
              <input
                type="checkbox"
                checked={preferences.compact_mode}
                onChange={(e) => setPreference('compact_mode', e.target.checked)}
                className="w-5 h-5"
              />
            </label>
          </div>
        </section>

        <section className="rounded-lg p-4" style={{ backgroundColor: 'var(--sidebar-bg)' }}>
          <h2 className="text-lg font-semibold mb-4" style={{ color: 'var(--text-primary)' }}>Notifications</h2>
          <div className="space-y-3">
            <label className="flex items-center justify-between">
              <span style={{ color: 'var(--text-muted)' }}>Enable Notifications</span>
              <input
                type="checkbox"
                checked={preferences.notifications}
                onChange={(e) => setPreference('notifications', e.target.checked)}
                className="w-5 h-5"
              />
            </label>
            <label className="flex items-center justify-between">
              <span style={{ color: 'var(--text-muted)' }}>Sound</span>
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
