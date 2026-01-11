import api from './api'

let statusPromise: Promise<{ initialized: boolean }> | null = null

export function fetchSystemStatus() {
  if (!statusPromise) {
    statusPromise = api.get('/api/system/status').then((r) => r.data)
  }
  return statusPromise
}
