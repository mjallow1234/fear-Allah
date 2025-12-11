// Browser Notification utilities

// Check if notifications are supported and request permission
export async function requestNotificationPermission(): Promise<boolean> {
  if (!('Notification' in window)) {
    console.log('This browser does not support notifications')
    return false
  }

  if (Notification.permission === 'granted') {
    return true
  }

  if (Notification.permission !== 'denied') {
    const permission = await Notification.requestPermission()
    return permission === 'granted'
  }

  return false
}

// Check if permission is already granted
export function hasNotificationPermission(): boolean {
  return 'Notification' in window && Notification.permission === 'granted'
}

// Show a browser notification
export function showBrowserNotification(
  title: string,
  options?: {
    body?: string
    icon?: string
    tag?: string
    onClick?: () => void
  }
): Notification | null {
  console.log('showBrowserNotification called:', title, options)
  
  if (!hasNotificationPermission()) {
    console.log('No notification permission')
    return null
  }

  try {
    const notification = new Notification(title, {
      body: options?.body,
      icon: options?.icon || '/favicon.ico',
      tag: options?.tag,
      silent: false,
    })

    if (options?.onClick) {
      notification.onclick = () => {
        window.focus()
        notification.close()
        options.onClick?.()
      }
    } else {
      notification.onclick = () => {
        window.focus()
        notification.close()
      }
    }

    // Auto-close after 5 seconds
    setTimeout(() => notification.close(), 5000)

    return notification
  } catch (error) {
    console.error('Failed to create notification:', error)
    return null
  }
}

// Show notification for a new message
export function notifyNewMessage(
  senderName: string,
  messageContent: string,
  channelName?: string,
  onClick?: () => void
) {
  console.log('notifyNewMessage called:', senderName, messageContent, channelName)
  
  const title = channelName 
    ? `${senderName} in #${channelName}`
    : `New message from ${senderName}`
  
  // Truncate message if too long
  const body = messageContent.length > 100 
    ? messageContent.slice(0, 100) + '...'
    : messageContent

  showBrowserNotification(title, {
    body,
    tag: 'new-message-' + Date.now(),
    onClick,
  })
}

// Show notification for a mention
export function notifyMention(
  senderName: string,
  messageContent: string,
  channelName?: string,
  onClick?: () => void
) {
  console.log('notifyMention called:', senderName, messageContent, channelName)
  
  const title = `${senderName} mentioned you${channelName ? ` in #${channelName}` : ''}`
  
  const body = messageContent.length > 100 
    ? messageContent.slice(0, 100) + '...'
    : messageContent

  showBrowserNotification(title, {
    body,
    tag: 'mention-' + Date.now(),
    onClick,
  })
}
