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
  order_type?: string
}

interface OrderUpdatedEvent {
  order_id: number
  status: string
  order_type?: string
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
    return () => {}
  }
  
  const store = useOrderStore.getState()
  
  // Listen for order creation
  const unsubCreated = onSocketEvent<OrderCreatedEvent>('order:created', (data) => {
    store.handleOrderCreated(data)
  })
  
  const unsubUpdated = onSocketEvent<OrderUpdatedEvent>('order:updated', (data) => {
    store.handleOrderUpdated(data)
  })
  
  const unsubCompleted = onSocketEvent<OrderCompletedEvent>('order:completed', (data) => {
    store.handleOrderCompleted(data)
  })
  
  orderSubscribed = true
  
  return () => {
    unsubCreated()
    unsubUpdated()
    unsubCompleted()
    orderSubscribed = false
  }
}

/**
 * Reset order subscription state (for logout/disconnect).
 */
export function resetOrderSubscription(): void {
  orderSubscribed = false
  useOrderStore.getState().reset()
}
