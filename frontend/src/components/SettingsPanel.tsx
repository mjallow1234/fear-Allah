export default function SettingsPanel() {
  return (
    <div className="p-4 bg-[#2b2d31] rounded-lg">
      <h3 className="text-lg font-semibold text-white mb-4">Quick Settings</h3>
      <div className="space-y-2">
        <button className="w-full text-left px-3 py-2 text-[#b5bac1] hover:bg-[#35373c] rounded transition-colors">
          Notifications
        </button>
        <button className="w-full text-left px-3 py-2 text-[#b5bac1] hover:bg-[#35373c] rounded transition-colors">
          Privacy
        </button>
        <button className="w-full text-left px-3 py-2 text-[#b5bac1] hover:bg-[#35373c] rounded transition-colors">
          Appearance
        </button>
      </div>
    </div>
  )
}
