import { usePresenceStore } from '../stores/presenceStore'

interface PresenceIndicatorProps {
  userId: number
  size?: 'sm' | 'md' | 'lg'
}

export default function PresenceIndicator({ userId, size = 'sm' }: PresenceIndicatorProps) {
  const isOnline = usePresenceStore((state) => state.isOnline(userId))
  
  if (!isOnline) return null
  
  const sizeClasses = {
    sm: 'w-2 h-2',
    md: 'w-3 h-3',
    lg: 'w-4 h-4',
  }
  
  return (
    <div 
      className={`${sizeClasses[size]} rounded-full bg-green-500 border-2 border-[#313338]`}
      title="Online"
    />
  )
}
