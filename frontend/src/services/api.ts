import axios from 'axios'
import { useAuthStore } from '../stores/authStore'

// Use backend URL directly - always use current hostname for LAN access
// Do NOT use VITE_API_URL to avoid stale ngrok URLs
const API_BASE_URL = `http://${window.location.hostname}:8000`

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
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      useAuthStore.getState().logout()
      window.location.href = '/login'
    }
    return Promise.reject(error)
  }
)

export default api
