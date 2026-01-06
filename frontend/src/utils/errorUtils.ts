/**
 * Extract a user-friendly error message from an API error response.
 * Backend HTTPException detail can be either:
 * - A string: "Simple error message"
 * - An object: { error: "error_code", message: "Human readable message" }
 * 
 * @param detail - The detail field from the error response
 * @param fallback - Default message if no error can be extracted
 * @returns A string suitable for display to users
 */
export function extractErrorMessage(detail: unknown, fallback: string = 'An error occurred'): string {
  if (!detail) {
    return fallback
  }
  
  if (typeof detail === 'string') {
    return detail
  }
  
  if (typeof detail === 'object' && detail !== null) {
    // Handle { error: "...", message: "..." } format
    const obj = detail as Record<string, unknown>
    if (typeof obj.message === 'string') {
      return obj.message
    }
    if (typeof obj.error === 'string') {
      return obj.error
    }
    // Handle { detail: "..." } nested format
    if (typeof obj.detail === 'string') {
      return obj.detail
    }
  }
  
  return fallback
}

/**
 * Extract error message from an Axios error object
 */
export function extractAxiosError(err: unknown, fallback: string = 'An error occurred'): string {
  if (!err || typeof err !== 'object') {
    return fallback
  }
  
  const axiosErr = err as { response?: { data?: { detail?: unknown } } }
  return extractErrorMessage(axiosErr.response?.data?.detail, fallback)
}
