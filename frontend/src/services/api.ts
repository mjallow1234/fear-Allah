import axios from 'axios'
import { useAuthStore } from '../stores/authStore'

// Use environment override when set (local dev with API proxy)
// Fallback to current hostname on :8000 for LAN access
const API_BASE_URL = import.meta.env.VITE_API_URL || `http://${window.location.hostname}:8000`

const api = axios.create({
  baseURL: API_BASE_URL,
  withCredentials: true,
})

// Request interceptor to add auth token
api.interceptors.request.use((config) => {
  const token = useAuthStore.getState().token
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

// Response interceptor for error handling
// Don't automatically retry or swallow 4xx errors. Let callers handle these failures.
api.interceptors.response.use(
  (response) => response,
  (error) => {
    const status = error.response?.status
    if (status && status >= 400 && status < 500) {
      if (status === 401) {
        useAuthStore.getState().logout()
        window.location.href = '/login'
      }
      // Reject all 4xx errors immediately (no auto-retry)
      return Promise.reject(error)
    }
    // For network or 5xx errors, still reject so higher-level logic can decide to retry
    return Promise.reject(error)
  }
)

export default api
