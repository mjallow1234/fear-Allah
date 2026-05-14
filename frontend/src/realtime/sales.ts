/**
 * Sale event subscriptions.
 * Subscribes to Socket.IO sale events and refreshes inventory/sales stores.
 * Read-only - no emits from frontend.
 */
import { onSocketEvent } from './socket'
import { useInventoryStore } from '../stores/inventoryStore'
import { useSalesStore } from '../stores/salesStore'

let saleSubscribed = false

interface SaleCreatedEvent {
  sale_id: number
  product_id: number
  quantity: number
  user_id?: number
  channel?: string
}

/**
 * Subscribe to sale events from Socket.IO.
 * Should be called once after socket connects.
 */
export function subscribeToSales(): () => void {
  if (saleSubscribed) {
    return () => {}
  }

  const unsubCreated = onSocketEvent<SaleCreatedEvent>('sale:created', (_data) => {
    useInventoryStore.getState().fetchTransactions()
    useInventoryStore.getState().fetchInventory()
    useSalesStore.getState().fetchSummary()
  })

  saleSubscribed = true

  return () => {
    unsubCreated()
    saleSubscribed = false
  }
}

/**
 * Reset sale subscription state (for logout/disconnect).
 */
export function resetSaleSubscription(): void {
  saleSubscribed = false
}
