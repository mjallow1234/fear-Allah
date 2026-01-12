import api from './api'

type SystemStatus = {
  setup_completed: boolean | null
  system_ready: boolean | null
}

let statusPromise: Promise<SystemStatus> | null = null

export function fetchSystemStatus() {
  if (!statusPromise) {
    statusPromise = api
      .get('/api/system/status')
      .then((r) => ({ setup_completed: r.data.setup_completed, system_ready: r.data.system_ready }))
      .catch((err) => {
        const status = err?.response?.status
        // Treat 429 as "unknown" (null) rather than false so it doesn't redirect to /setup
        if (status === 429) {
          return { setup_completed: null, system_ready: null }
        }
        // On other errors, treat as unknown as well to avoid accidental redirects to /setup
        return { setup_completed: null, system_ready: null }
      })
  }
  return statusPromise
}
