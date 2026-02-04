/**
 * Notification Intensity Configuration
 * 
 * Defines how different notification types should behave:
 * - critical: Sound + Toast (interrupting, requires attention)
 * - important: Toast only (notable but not urgent)
 * - silent: No toast, no sound (background updates)
 */

export type NotificationIntensity = 'critical' | 'important' | 'silent'

export const NOTIFICATION_INTENSITY: Record<string, NotificationIntensity> = {
  // Critical: Sound + Toast
  task_assigned: 'critical',
  task_step_completed: 'critical',
  task_overdue: 'critical',
  order_completed: 'critical',

  // Important: Toast only
  order_created: 'important',
  task_completed: 'important',

  // Silent: No interruption
  task_auto_closed: 'silent',
  task_claimed: 'silent',
  
  // Chat notifications (keep existing behavior)
  mention: 'important',
  reply: 'silent',
  dm: 'important',
  reaction: 'silent',
  
  // Other
  low_stock: 'critical',
  inventory_restocked: 'silent',
  sale_recorded: 'silent',
  system: 'important',
}

export function getNotificationIntensity(type: string): NotificationIntensity {
  return NOTIFICATION_INTENSITY[type] || 'silent'
}

export function shouldPlaySound(type: string): boolean {
  return getNotificationIntensity(type) === 'critical'
}

export function shouldShowToast(type: string): boolean {
  const intensity = getNotificationIntensity(type)
  return intensity === 'critical' || intensity === 'important'
}
