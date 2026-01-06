import api from './api'
import { useAuthStore } from '../stores/authStore'

// Get base URL from api instance
const getBaseUrl = () => {
  return api.defaults.baseURL || `http://${window.location.hostname}:8000`
}

export interface AttachmentLimits {
  max_file_size: number
  allowed_mime_types: string[]
  max_files_per_message: number
}

export interface Attachment {
  id: number
  message_id: number | null
  channel_id: number
  user_id: number
  filename: string
  file_size: number
  mime_type: string
  url: string
  thumbnail_url?: string
  created_at: string
  uploader_username?: string
}

export interface UploadProgress {
  loaded: number
  total: number
  percentage: number
}

// Blocked extensions that backend rejects
const BLOCKED_EXTENSIONS = [
  '.exe', '.bat', '.cmd', '.com', '.msi', '.scr', '.pif', '.vbs',
  '.js', '.jse', '.ws', '.wsf', '.ps1', '.reg', '.dll', '.sh'
]

/**
 * Validates a file before upload
 * Returns error message if invalid, null if valid
 */
export function validateFile(file: File, limits: AttachmentLimits): string | null {
  // Check file size
  if (file.size > limits.max_file_size) {
    const maxMB = Math.round(limits.max_file_size / (1024 * 1024))
    return `File too large. Maximum size is ${maxMB}MB`
  }

  // Check extension (client-side quick check)
  const filename = file.name.toLowerCase()
  for (const ext of BLOCKED_EXTENSIONS) {
    if (filename.endsWith(ext)) {
      return `File type ${ext} is not allowed`
    }
  }

  // Check MIME type
  if (limits.allowed_mime_types.length > 0) {
    const isAllowed = limits.allowed_mime_types.some(allowed => {
      if (allowed.endsWith('/*')) {
        // Wildcard match (e.g., image/*)
        const category = allowed.slice(0, -2)
        return file.type.startsWith(category + '/')
      }
      return file.type === allowed
    })
    
    if (!isAllowed) {
      return `File type ${file.type || 'unknown'} is not allowed`
    }
  }

  return null
}

/**
 * Fetch upload limits from server
 */
export async function getUploadLimits(): Promise<AttachmentLimits> {
  const response = await api.get('/api/attachments/limits')
  return response.data
}

/**
 * Upload a file to a channel with progress tracking
 * Uses XMLHttpRequest for progress events
 */
export function uploadFile(
  file: File,
  channelId: number,
  messageId?: number,
  onProgress?: (progress: UploadProgress) => void
): Promise<Attachment> {
  return new Promise((resolve, reject) => {
    const formData = new FormData()
    formData.append('file', file)
    formData.append('channel_id', channelId.toString())
    if (messageId) {
      formData.append('message_id', messageId.toString())
    }

    const xhr = new XMLHttpRequest()
    
    // Track upload progress
    xhr.upload.addEventListener('progress', (event) => {
      if (event.lengthComputable && onProgress) {
        onProgress({
          loaded: event.loaded,
          total: event.total,
          percentage: Math.round((event.loaded / event.total) * 100)
        })
      }
    })

    xhr.addEventListener('load', () => {
      if (xhr.status >= 200 && xhr.status < 300) {
        try {
          const data = JSON.parse(xhr.responseText)
          resolve(data)
        } catch {
          reject(new Error('Invalid response from server'))
        }
      } else {
        try {
          const error = JSON.parse(xhr.responseText)
          reject(new Error(error.detail || `Upload failed with status ${xhr.status}`))
        } catch {
          reject(new Error(`Upload failed with status ${xhr.status}`))
        }
      }
    })

    xhr.addEventListener('error', () => {
      reject(new Error('Network error during upload'))
    })

    xhr.addEventListener('abort', () => {
      reject(new Error('Upload cancelled'))
    })

    // Open connection
    xhr.open('POST', `${getBaseUrl()}/api/attachments/upload`)
    
    // Add auth token
    const token = useAuthStore.getState().token
    if (token) {
      xhr.setRequestHeader('Authorization', `Bearer ${token}`)
    }

    // Send
    xhr.send(formData)
  })
}

/**
 * Upload multiple files with progress tracking
 */
export async function uploadFiles(
  files: File[],
  channelId: number,
  messageId?: number,
  onProgress?: (fileIndex: number, progress: UploadProgress) => void,
  onFileComplete?: (fileIndex: number, attachment: Attachment) => void,
  onFileError?: (fileIndex: number, error: string) => void
): Promise<Attachment[]> {
  const attachments: Attachment[] = []

  for (let i = 0; i < files.length; i++) {
    try {
      const attachment = await uploadFile(
        files[i],
        channelId,
        messageId,
        (progress) => onProgress?.(i, progress)
      )
      attachments.push(attachment)
      onFileComplete?.(i, attachment)
    } catch (err) {
      const error = err instanceof Error ? err.message : 'Upload failed'
      onFileError?.(i, error)
      // Continue with remaining files
    }
  }

  return attachments
}

/**
 * Get attachments for a channel
 */
export async function getChannelAttachments(channelId: number, limit = 50, offset = 0): Promise<Attachment[]> {
  const response = await api.get(`/api/attachments/channel/${channelId}`, {
    params: { limit, offset }
  })
  return response.data
}

/**
 * Delete an attachment
 */
export async function deleteAttachment(attachmentId: number): Promise<void> {
  await api.delete(`/api/attachments/${attachmentId}`)
}

/**
 * Get download URL for an attachment
 */
export function getDownloadUrl(attachment: Attachment): string {
  // The url field from the server already contains the full path
  if (attachment.url.startsWith('http')) {
    return attachment.url
  }
  return `${getBaseUrl()}${attachment.url}`
}

/**
 * Determine if a file is an image based on MIME type
 */
export function isImageFile(mimeType: string): boolean {
  return mimeType.startsWith('image/')
}

/**
 * Determine if a file is a video based on MIME type
 */
export function isVideoFile(mimeType: string): boolean {
  return mimeType.startsWith('video/')
}

/**
 * Get a human-readable file size string
 */
export function formatFileSize(bytes: number): string {
  if (bytes === 0) return '0 B'
  
  const units = ['B', 'KB', 'MB', 'GB']
  const k = 1024
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  
  return `${parseFloat((bytes / Math.pow(k, i)).toFixed(1))} ${units[i]}`
}

/**
 * Get file icon based on MIME type
 */
export function getFileIcon(mimeType: string): string {
  if (mimeType.startsWith('image/')) return '🖼️'
  if (mimeType.startsWith('video/')) return '🎬'
  if (mimeType.startsWith('audio/')) return '🎵'
  if (mimeType === 'application/pdf') return '📄'
  if (mimeType.includes('word') || mimeType.includes('document')) return '📝'
  if (mimeType.includes('excel') || mimeType.includes('spreadsheet')) return '📊'
  if (mimeType.includes('zip') || mimeType.includes('tar') || mimeType.includes('compressed')) return '📦'
  if (mimeType.startsWith('text/')) return '📃'
  return '📎'
}
