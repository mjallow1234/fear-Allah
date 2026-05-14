/**
 * Operational Real-Time WebSocket Client
 *
 * Connects to the backend /ws/ops endpoint and dispatches domain events to
 * registered handlers.  Automatically reconnects with exponential back-off
 * when the connection drops.
 *
 * Usage:
 *   const unsub = connectOpsRealtime()   // call on mount
 *   unsub()                              // call on unmount / logout
 */

import { useTaskStore } from '../stores/taskStore'

// ─── Types ────────────────────────────────────────────────────────────────────

export type OpsEventType =
  | 'ORDER_CREATED'
  | 'ORDER_UPDATED'
  | 'SALE_CREATED'
  | 'SALE_REVERSED'

export interface OpsEvent {
  type: OpsEventType
  order_id?: number
  sale_id?: number
  [key: string]: unknown
}

// ─── Config ───────────────────────────────────────────────────────────────────

const INITIAL_RECONNECT_MS = 1_000
const MAX_RECONNECT_MS = 30_000
const BACKOFF_FACTOR = 2

function getOpsWsUrl(): string {
  const apiUrl = import.meta.env.VITE_API_URL as string | undefined
  if (apiUrl) {
    // Convert http(s):// → ws(s)://
    return apiUrl.replace(/^http/, 'ws') + '/ws/ops'
  }
  // Fall back to current page host so the WebSocket goes through Vite's proxy
  // (/ws/* → localhost:18002).  On mobile this resolves to the LAN IP:3000.
  const proto = window.location.protocol === 'https:' ? 'wss' : 'ws'
  return `${proto}://${window.location.host}/ws/ops`
}

// ─── Connection manager ───────────────────────────────────────────────────────

let ws: WebSocket | null = null
let reconnectTimer: ReturnType<typeof setTimeout> | null = null
let reconnectDelay = INITIAL_RECONNECT_MS
let destroyed = false  // set to true when the caller calls the returned cleanup fn

function clearReconnectTimer() {
  if (reconnectTimer !== null) {
    clearTimeout(reconnectTimer)
    reconnectTimer = null
  }
}

function handleEvent(event: OpsEvent) {
  const store = useTaskStore.getState()

  switch (event.type) {
    case 'ORDER_CREATED':
    case 'ORDER_UPDATED':
    case 'SALE_CREATED':
    case 'SALE_REVERSED':
      // Refresh the task list so order/sale status is up to date
      store.fetchMyTasks().catch(() => {})
      break
    default:
      console.warn('[opsRealtime] Unknown event type:', (event as any).type)
  }
}

function connect() {
  if (destroyed) return

  const url = getOpsWsUrl()

  ws = new WebSocket(url)

  ws.onopen = () => {
    reconnectDelay = INITIAL_RECONNECT_MS  // reset back-off on successful connect
  }

  ws.onmessage = (msg) => {
    try {
      const event: OpsEvent = JSON.parse(msg.data)
      handleEvent(event)
    } catch (e) {
      console.warn('[opsRealtime] failed to parse message', msg.data, e)
    }
  }

  ws.onerror = (err) => {
    console.warn('[opsRealtime] error', err)
    // onclose fires immediately after onerror; reconnect is handled there
  }

  ws.onclose = () => {
    ws = null
    if (destroyed) return
    reconnectTimer = setTimeout(() => {
      reconnectDelay = Math.min(reconnectDelay * BACKOFF_FACTOR, MAX_RECONNECT_MS)
      connect()
    }, reconnectDelay)
  }
}

/**
 * Open the /ws/ops connection.
 * Returns a cleanup function — call it on component unmount to close the
 * socket and cancel any pending reconnect timer.
 */
export function connectOpsRealtime(): () => void {
  destroyed = false
  connect()

  return () => {
    destroyed = true
    clearReconnectTimer()
    if (ws) {
      ws.close()
      ws = null
    }
  }
}
