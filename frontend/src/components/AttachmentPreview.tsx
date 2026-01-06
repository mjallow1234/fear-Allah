import { X, FileText, Image as ImageIcon, Video, Music, File } from 'lucide-react'
import { formatFileSize, isImageFile, isVideoFile } from '../services/attachments'

export interface StagedFile {
  id: string  // Unique ID for tracking
  file: File
  preview?: string  // Data URL for image previews
  error?: string
}

export interface UploadingFile extends StagedFile {
  progress: number  // 0-100
  uploading: boolean
  completed: boolean
}

interface AttachmentPreviewProps {
  files: (StagedFile | UploadingFile)[]
  onRemove: (id: string) => void
  disabled?: boolean
}

function FileIcon({ mimeType, size = 24 }: { mimeType: string; size?: number }) {
  if (mimeType.startsWith('image/')) return <ImageIcon size={size} className="text-blue-400" />
  if (mimeType.startsWith('video/')) return <Video size={size} className="text-purple-400" />
  if (mimeType.startsWith('audio/')) return <Music size={size} className="text-green-400" />
  if (mimeType === 'application/pdf') return <FileText size={size} className="text-red-400" />
  return <File size={size} className="text-gray-400" />
}

function isUploadingFile(file: StagedFile | UploadingFile): file is UploadingFile {
  return 'uploading' in file
}

export default function AttachmentPreview({ files, onRemove, disabled }: AttachmentPreviewProps) {
  if (files.length === 0) return null

  return (
    <div className="flex flex-wrap gap-2 p-3 bg-gray-800 border-t border-gray-700 rounded-t-lg">
      {files.map((file) => {
        const isImage = isImageFile(file.file.type)
        const isVideo = isVideoFile(file.file.type)
        const uploading = isUploadingFile(file) && file.uploading
        const completed = isUploadingFile(file) && file.completed
        const progress = isUploadingFile(file) ? file.progress : 0

        return (
          <div
            key={file.id}
            className={`relative group flex items-center gap-2 bg-gray-700 rounded-lg overflow-hidden ${
              file.error ? 'border-2 border-red-500' : ''
            } ${completed ? 'opacity-50' : ''}`}
          >
            {/* Preview thumbnail or icon */}
            {isImage && file.preview ? (
              <div className="w-16 h-16 flex-shrink-0">
                <img
                  src={file.preview}
                  alt={file.file.name}
                  className="w-full h-full object-cover"
                />
              </div>
            ) : isVideo && file.preview ? (
              <div className="w-16 h-16 flex-shrink-0 relative">
                <video
                  src={file.preview}
                  className="w-full h-full object-cover"
                />
                <div className="absolute inset-0 flex items-center justify-center bg-black/50">
                  <Video size={24} className="text-white" />
                </div>
              </div>
            ) : (
              <div className="w-16 h-16 flex-shrink-0 flex items-center justify-center bg-gray-600">
                <FileIcon mimeType={file.file.type} size={28} />
              </div>
            )}

            {/* File info */}
            <div className="flex-1 py-2 pr-8 min-w-0">
              <div className="text-sm text-white truncate max-w-[150px]" title={file.file.name}>
                {file.file.name}
              </div>
              <div className="text-xs text-gray-400">
                {formatFileSize(file.file.size)}
              </div>
              {file.error && (
                <div className="text-xs text-red-400 truncate" title={file.error}>
                  {file.error}
                </div>
              )}
            </div>

            {/* Progress overlay */}
            {uploading && (
              <div className="absolute inset-0 bg-black/50 flex items-center justify-center">
                <div className="text-center">
                  <div className="w-12 h-12 relative">
                    <svg className="w-full h-full transform -rotate-90">
                      <circle
                        cx="24"
                        cy="24"
                        r="20"
                        stroke="currentColor"
                        strokeWidth="4"
                        fill="none"
                        className="text-gray-600"
                      />
                      <circle
                        cx="24"
                        cy="24"
                        r="20"
                        stroke="currentColor"
                        strokeWidth="4"
                        fill="none"
                        strokeDasharray={`${2 * Math.PI * 20}`}
                        strokeDashoffset={`${2 * Math.PI * 20 * (1 - progress / 100)}`}
                        className="text-blue-500 transition-all duration-200"
                      />
                    </svg>
                    <div className="absolute inset-0 flex items-center justify-center text-xs text-white font-medium">
                      {progress}%
                    </div>
                  </div>
                </div>
              </div>
            )}

            {/* Remove button */}
            {!disabled && !uploading && !completed && (
              <button
                onClick={() => onRemove(file.id)}
                className="absolute top-1 right-1 p-1 bg-gray-800/80 hover:bg-red-600 rounded-full transition-colors opacity-0 group-hover:opacity-100"
                title="Remove file"
              >
                <X size={14} className="text-white" />
              </button>
            )}
          </div>
        )
      })}
    </div>
  )
}
