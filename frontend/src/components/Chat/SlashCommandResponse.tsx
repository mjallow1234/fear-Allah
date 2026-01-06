/**
 * SlashCommandResponse - Renders formatted slash command system messages
 * 
 * Features:
 * - Color-coded containers: red (error), green (success), blue (dry-run)
 * - Collapsible automation debug panel
 * - Consistent formatting
 */
import { useState } from 'react'
import { ChevronDown, ChevronRight, AlertCircle, CheckCircle, Search, Bug } from 'lucide-react'

interface SlashCommandResponseProps {
  content: string
}

type ResponseType = 'error' | 'success' | 'dry-run' | 'info'

function detectResponseType(content: string): ResponseType {
  const lowerContent = content.toLowerCase()
  
  // Error detection
  if (content.startsWith('❌') || lowerContent.includes('error') || lowerContent.includes('permission denied') || lowerContent.includes('invalid')) {
    return 'error'
  }
  
  // Dry-run detection
  if (content.includes('🔍') || lowerContent.includes('dry-run') || lowerContent.includes('dry_run') || lowerContent.includes('preview')) {
    return 'dry-run'
  }
  
  // Success detection
  if (content.startsWith('✅') || lowerContent.includes('created') || lowerContent.includes('completed') || lowerContent.includes('recorded')) {
    return 'success'
  }
  
  return 'info'
}

function parseContent(content: string): { mainMessage: string; debugInfo: string | null } {
  // Look for automation debug section
  const debugMarkers = [
    '📊 **Automation Debug:**',
    '📊 **Automation Debug**',
    '**Automation Debug:**',
    '**Automation Debug**',
    'Automation Debug:',
  ]
  
  let mainMessage = content
  let debugInfo: string | null = null
  
  for (const marker of debugMarkers) {
    const idx = content.indexOf(marker)
    if (idx !== -1) {
      mainMessage = content.substring(0, idx).trim()
      debugInfo = content.substring(idx).trim()
      break
    }
  }
  
  return { mainMessage, debugInfo }
}

const responseStyles: Record<ResponseType, { 
  container: string
  border: string
  icon: typeof CheckCircle
  iconColor: string
  header: string
  headerBg: string
}> = {
  'error': {
    container: 'bg-red-950/30',
    border: 'border-red-500/50',
    icon: AlertCircle,
    iconColor: 'text-red-400',
    header: 'ERROR',
    headerBg: 'bg-red-500/20 text-red-300',
  },
  'success': {
    container: 'bg-green-950/30',
    border: 'border-green-500/50',
    icon: CheckCircle,
    iconColor: 'text-green-400',
    header: 'SUCCESS',
    headerBg: 'bg-green-500/20 text-green-300',
  },
  'dry-run': {
    container: 'bg-blue-950/30',
    border: 'border-blue-500/50',
    icon: Search,
    iconColor: 'text-blue-400',
    header: 'DRY-RUN PREVIEW',
    headerBg: 'bg-blue-500/20 text-blue-300',
  },
  'info': {
    container: 'bg-gray-800/50',
    border: 'border-gray-600/50',
    icon: CheckCircle,
    iconColor: 'text-gray-400',
    header: 'INFO',
    headerBg: 'bg-gray-500/20 text-gray-300',
  },
}

function formatMainMessage(text: string): string {
  // Clean up markdown-style formatting for display
  return text
    .replace(/\*\*(.+?)\*\*/g, '$1') // Remove bold markers (we'll style differently)
    .replace(/`(.+?)`/g, '$1') // Remove code markers
    .trim()
}

export default function SlashCommandResponse({ content }: SlashCommandResponseProps) {
  const [debugExpanded, setDebugExpanded] = useState(false)
  
  const responseType = detectResponseType(content)
  const { mainMessage, debugInfo } = parseContent(content)
  const styles = responseStyles[responseType]
  const Icon = styles.icon
  
  return (
    <div className={`rounded-lg border ${styles.container} ${styles.border} overflow-hidden`}>
      {/* Status Header */}
      <div className={`px-3 py-1.5 flex items-center gap-2 ${styles.headerBg} border-b ${styles.border}`}>
        <Icon size={14} className={styles.iconColor} />
        <span className="text-xs font-semibold tracking-wide">{styles.header}</span>
      </div>
      
      {/* Main Message */}
      <div className="px-3 py-2">
        <div className="text-sm text-gray-100 whitespace-pre-wrap leading-relaxed">
          {mainMessage.split('\n').map((line, i) => {
            // Style different line types
            if (line.startsWith('•') || line.startsWith('→')) {
              return (
                <div key={i} className="ml-2 text-gray-300">
                  {line}
                </div>
              )
            }
            if (line.includes('**') || line.startsWith('Order type:') || line.startsWith('Product:') || line.startsWith('Workflow')) {
              return (
                <div key={i} className="font-medium text-gray-200">
                  {formatMainMessage(line)}
                </div>
              )
            }
            if (line.trim() === '') {
              return <div key={i} className="h-2" />
            }
            return <div key={i}>{formatMainMessage(line)}</div>
          })}
        </div>
      </div>
      
      {/* Collapsible Debug Section */}
      {debugInfo && (
        <div className="border-t border-gray-700/50">
          <button
            onClick={() => setDebugExpanded(!debugExpanded)}
            className="w-full px-3 py-2 flex items-center gap-2 text-xs text-gray-400 hover:text-gray-300 hover:bg-gray-800/30 transition-colors"
          >
            {debugExpanded ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
            <Bug size={12} />
            <span>Automation Debug (click to expand)</span>
          </button>
          
          {debugExpanded && (
            <div className="px-3 pb-3 pt-1">
              <div className="bg-gray-900/50 rounded p-2 text-xs text-gray-400 font-mono whitespace-pre-wrap">
                {debugInfo.split('\n').map((line, i) => {
                  // Highlight specific fields
                  if (line.includes('Event:')) {
                    return <div key={i} className="text-purple-400">{line}</div>
                  }
                  if (line.includes('Tasks')) {
                    return <div key={i} className="text-blue-400">{line}</div>
                  }
                  if (line.includes('Assigned')) {
                    return <div key={i} className="text-green-400">{line}</div>
                  }
                  if (line.includes('Notification')) {
                    return <div key={i} className="text-yellow-400">{line}</div>
                  }
                  if (line.includes('Dry-run')) {
                    return <div key={i} className="text-cyan-400">{line}</div>
                  }
                  if (line.includes('⚠️') || line.includes('Validation')) {
                    return <div key={i} className="text-orange-400">{line}</div>
                  }
                  return <div key={i}>{line}</div>
                })}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

/**
 * Utility to check if a message should use the SlashCommandResponse renderer
 */
export function isSlashCommandResponse(message: { system?: boolean; content?: string }): boolean {
  if (!message.system) return false
  const content = message.content || ''
  
  // Detect slash command response patterns
  return (
    content.startsWith('✅') ||
    content.startsWith('❌') ||
    content.startsWith('🔍') ||
    content.includes('Order created') ||
    content.includes('Sale recorded') ||
    content.includes('DRY-RUN') ||
    content.includes('Automation Debug') ||
    content.includes('Permission denied') ||
    content.includes('Invalid arguments')
  )
}
