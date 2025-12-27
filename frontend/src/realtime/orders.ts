/**
 * Order event subscriptions.
 * Phase 7.3 - Order UI
 * 
 * Subscribes to Socket.IO order events and updates the order store.
 * Read-only - no emits from frontend.
 */
import { onSocketEvent } from './socket'
import { useOrderStore } from '../stores/orderStore'

let orderSubscribed = false

interface OrderCreatedEvent {
  order_id: number
  status: string
}

interface OrderUpdatedEvent {
  order_id: number
  status: string
}

interface OrderCompletedEvent {
  order_id: number
}

/**
 * Subscribe to order events from Socket.IO.
 * Should be called once after socket connects.
 */
export function subscribeToOrders(): () => void {
  if (orderSubscribed) {
    console.log('[Orders] Already subscribed to order events')
    return () => {}
  }
  
  const store = useOrderStore.getState()
  
  // Listen for order creation
  const unsubCreated = onSocketEvent<OrderCreatedEvent>('order:created', (data) => {
    console.log('[Orders] Received order:created', data)
    store.handleOrderCreated(data)
  })
  
  // Listen for order updates
  const unsubUpdated = onSocketEvent<OrderUpdatedEvent>('order:updated', (data) => {
    console.log('[Orders] Received order:updated', data)
    store.handleOrderUpdated(data)
  })
  
  // Listen for order completion
  const unsubCompleted = onSocketEvent<OrderCompletedEvent>('order:completed', (data) => {
    console.log('[Orders] Received order:completed', data)
    store.handleOrderCompleted(data)
  })
  
  orderSubscribed = true
  console.log('[Orders] Subscribed to order events')
  
  // Return cleanup function
  return () => {
    unsubCreated()
    unsubUpdated()
    unsubCompleted()
    orderSubscribed = false
    console.log('[Orders] Unsubscribed from order events')
  }
}

/**
 * Reset order subscription state (for logout/disconnect).
 */
export function resetOrderSubscription(): void {
  orderSubscribed = false
  useOrderStore.getState().reset()
}
