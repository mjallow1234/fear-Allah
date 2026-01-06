import { Download, ExternalLink, FileText, Image as ImageIcon, Video, Music, File, X } from 'lucide-react'
import { useState } from 'react'
import { formatFileSize, isImageFile, isVideoFile, getDownloadUrl } from '../services/attachments'
import type { Attachment } from '../services/attachments'

interface MessageAttachmentsProps {
  attachments: Attachment[]
  onDelete?: (attachmentId: number) => void
  canDelete?: boolean
}

function FileIcon({ mimeType, size = 20 }: { mimeType: string; size?: number }) {
  if (mimeType.startsWith('image/')) return <ImageIcon size={size} className="text-blue-400" />
  if (mimeType.startsWith('video/')) return <Video size={size} className="text-purple-400" />
  if (mimeType.startsWith('audio/')) return <Music size={size} className="text-green-400" />
  if (mimeType === 'application/pdf') return <FileText size={size} className="text-red-400" />
  return <File size={size} className="text-gray-400" />
}

function ImagePreview({ attachment }: { attachment: Attachment }) {
  const [expanded, setExpanded] = useState(false)
  const url = getDownloadUrl(attachment)

  return (
    <>
      <div 
        className="relative cursor-pointer group"
        onClick={() => setExpanded(true)}
      >
        <img
          src={url}
          alt={attachment.filename}
          className="max-w-xs max-h-64 rounded-lg object-cover hover:opacity-90 transition-opacity"
          loading="lazy"
        />
        <div className="absolute inset-0 bg-black/0 group-hover:bg-black/20 transition-colors rounded-lg flex items-center justify-center">
          <ExternalLink 
            size={24} 
            className="text-white opacity-0 group-hover:opacity-100 transition-opacity drop-shadow-lg" 
          />
        </div>
      </div>
      
      {/* Fullscreen modal */}
      {expanded && (
        <div 
          className="fixed inset-0 z-50 bg-black/90 flex items-center justify-center p-4"
          onClick={() => setExpanded(false)}
        >
          <button 
            className="absolute top-4 right-4 p-2 bg-gray-800 hover:bg-gray-700 rounded-full transition-colors"
            onClick={() => setExpanded(false)}
          >
            <X size={24} className="text-white" />
          </button>
          <img
            src={url}
            alt={attachment.filename}
            className="max-w-full max-h-full object-contain"
            onClick={(e) => e.stopPropagation()}
          />
          <div className="absolute bottom-4 left-1/2 -translate-x-1/2 flex items-center gap-4 bg-gray-800/90 rounded-lg px-4 py-2">
            <span className="text-white text-sm">{attachment.filename}</span>
            <a
              href={url}
              download={attachment.filename}
              className="text-blue-400 hover:text-blue-300 flex items-center gap-1 text-sm"
              onClick={(e) => e.stopPropagation()}
            >
              <Download size={16} />
              Download
            </a>
          </div>
        </div>
      )}
    </>
  )
}

function VideoPreview({ attachment }: { attachment: Attachment }) {
  const url = getDownloadUrl(attachment)

  return (
    <video
      src={url}
      controls
      className="max-w-xs max-h-64 rounded-lg"
      preload="metadata"
    >
      Your browser does not support video playback.
    </video>
  )
}

function AudioPreview({ attachment }: { attachment: Attachment }) {
  const url = getDownloadUrl(attachment)

  return (
    <div className="flex items-center gap-3 bg-gray-700 rounded-lg p-3">
      <Music size={24} className="text-green-400 flex-shrink-0" />
      <div className="flex-1 min-w-0">
        <div className="text-sm text-white truncate">{attachment.filename}</div>
        <audio src={url} controls className="w-full mt-1 h-8" preload="metadata" />
      </div>
    </div>
  )
}

function FilePreview({ attachment, onDelete, canDelete }: { 
  attachment: Attachment
  onDelete?: (id: number) => void
  canDelete?: boolean 
}) {
  const url = getDownloadUrl(attachment)

  return (
    <div className="flex items-center gap-3 bg-gray-700 rounded-lg p-3 group relative">
      <FileIcon mimeType={attachment.mime_type} size={24} />
      <div className="flex-1 min-w-0">
        <div className="text-sm text-white truncate" title={attachment.filename}>
          {attachment.filename}
        </div>
        <div className="text-xs text-gray-400">
          {formatFileSize(attachment.file_size)}
        </div>
      </div>
      <a
        href={url}
        download={attachment.filename}
        className="p-2 hover:bg-gray-600 rounded-full transition-colors"
        title="Download"
      >
        <Download size={18} className="text-blue-400" />
      </a>
      {canDelete && onDelete && (
        <button
          onClick={() => onDelete(attachment.id)}
          className="p-2 hover:bg-red-600/20 rounded-full transition-colors opacity-0 group-hover:opacity-100"
          title="Delete attachment"
        >
          <X size={18} className="text-red-400" />
        </button>
      )}
    </div>
  )
}

export default function MessageAttachments({ attachments, onDelete, canDelete }: MessageAttachmentsProps) {
  if (!attachments || attachments.length === 0) return null

  // Group attachments by type for better layout
  const images = attachments.filter(a => isImageFile(a.mime_type))
  const videos = attachments.filter(a => isVideoFile(a.mime_type))
  const audio = attachments.filter(a => a.mime_type.startsWith('audio/'))
  const files = attachments.filter(a => 
    !isImageFile(a.mime_type) && 
    !isVideoFile(a.mime_type) && 
    !a.mime_type.startsWith('audio/')
  )

  return (
    <div className="mt-2 space-y-2">
      {/* Image grid */}
      {images.length > 0 && (
        <div className={`flex flex-wrap gap-2 ${images.length > 1 ? 'grid grid-cols-2 max-w-md' : ''}`}>
          {images.map((attachment) => (
            <ImagePreview key={attachment.id} attachment={attachment} />
          ))}
        </div>
      )}

      {/* Videos */}
      {videos.length > 0 && (
        <div className="space-y-2">
          {videos.map((attachment) => (
            <VideoPreview key={attachment.id} attachment={attachment} />
          ))}
        </div>
      )}

      {/* Audio */}
      {audio.length > 0 && (
        <div className="space-y-2 max-w-sm">
          {audio.map((attachment) => (
            <AudioPreview key={attachment.id} attachment={attachment} />
          ))}
        </div>
      )}

      {/* Other files */}
      {files.length > 0 && (
        <div className="space-y-1 max-w-sm">
          {files.map((attachment) => (
            <FilePreview 
              key={attachment.id} 
              attachment={attachment}
              onDelete={onDelete}
              canDelete={canDelete}
            />
          ))}
        </div>
      )}
    </div>
  )
}
