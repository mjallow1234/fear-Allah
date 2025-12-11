import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import rehypeSanitize from 'rehype-sanitize'
import { useMemo } from 'react'

interface MarkdownContentProps {
  content: string
  className?: string
}

// Process @mentions before markdown rendering
function processMentions(content: string): string {
  // Replace @username with a special markdown link that we can style
  // Using a custom protocol 'mention:' to identify mentions
  return content.replace(/@(\w+)/g, '[@$1](mention:$1)')
}

export default function MarkdownContent({ content, className = '' }: MarkdownContentProps) {
  // Process mentions in content
  const processedContent = useMemo(() => processMentions(content), [content])
  
  return (
    <ReactMarkdown
      remarkPlugins={[remarkGfm]}
      rehypePlugins={[rehypeSanitize]}
      className={`markdown-content ${className}`}
      components={{
        // Style code blocks
        code({ node, inline, className, children, ...props }: any) {
          if (inline) {
            return (
              <code
                className="bg-[#2e3035] px-1 py-0.5 rounded text-sm text-[#e87b35] font-mono"
                {...props}
              >
                {children}
              </code>
            )
          }
          return (
            <pre className="bg-[#2e3035] p-3 rounded my-2 overflow-x-auto">
              <code className="text-sm text-[#dcddde] font-mono" {...props}>
                {children}
              </code>
            </pre>
          )
        },
        // Style links - special handling for mentions
        a({ href, children, ...props }: any) {
          // Check if this is a mention link
          if (href?.startsWith('mention:')) {
            const username = href.replace('mention:', '')
            return (
              <span
                className="bg-[#5865f2]/30 text-[#dee0fc] px-1 rounded cursor-pointer hover:bg-[#5865f2]/50 font-medium"
                title={`View ${username}'s profile`}
                {...props}
              >
                {children}
              </span>
            )
          }
          return (
            <a
              href={href}
              target="_blank"
              rel="noopener noreferrer"
              className="text-[#00aff4] hover:underline"
              {...props}
            >
              {children}
            </a>
          )
        },
        // Style blockquotes
        blockquote({ children, ...props }: any) {
          return (
            <blockquote
              className="border-l-4 border-[#5865f2] pl-3 my-2 text-[#949ba4] italic"
              {...props}
            >
              {children}
            </blockquote>
          )
        },
        // Style lists
        ul({ children, ...props }: any) {
          return (
            <ul className="list-disc list-inside my-1 text-[#dcddde]" {...props}>
              {children}
            </ul>
          )
        },
        ol({ children, ...props }: any) {
          return (
            <ol className="list-decimal list-inside my-1 text-[#dcddde]" {...props}>
              {children}
            </ol>
          )
        },
        // Style headings
        h1({ children, ...props }: any) {
          return (
            <h1 className="text-xl font-bold text-white my-2" {...props}>
              {children}
            </h1>
          )
        },
        h2({ children, ...props }: any) {
          return (
            <h2 className="text-lg font-bold text-white my-2" {...props}>
              {children}
            </h2>
          )
        },
        h3({ children, ...props }: any) {
          return (
            <h3 className="text-base font-bold text-white my-1" {...props}>
              {children}
            </h3>
          )
        },
        // Style emphasis
        strong({ children, ...props }: any) {
          return (
            <strong className="font-bold text-white" {...props}>
              {children}
            </strong>
          )
        },
        em({ children, ...props }: any) {
          return (
            <em className="italic" {...props}>
              {children}
            </em>
          )
        },
        // Style strikethrough
        del({ children, ...props }: any) {
          return (
            <del className="line-through text-[#949ba4]" {...props}>
              {children}
            </del>
          )
        },
        // Style tables
        table({ children, ...props }: any) {
          return (
            <div className="overflow-x-auto my-2">
              <table className="border-collapse border border-[#3f4147]" {...props}>
                {children}
              </table>
            </div>
          )
        },
        th({ children, ...props }: any) {
          return (
            <th
              className="border border-[#3f4147] px-3 py-1 bg-[#2e3035] text-white font-medium"
              {...props}
            >
              {children}
            </th>
          )
        },
        td({ children, ...props }: any) {
          return (
            <td className="border border-[#3f4147] px-3 py-1 text-[#dcddde]" {...props}>
              {children}
            </td>
          )
        },
        // Style horizontal rule
        hr({ ...props }: any) {
          return <hr className="border-[#3f4147] my-3" {...props} />
        },
        // Style paragraphs
        p({ children, ...props }: any) {
          return (
            <p className="text-[#dcddde]" {...props}>
              {children}
            </p>
          )
        },
      }}
    >
      {processedContent}
    </ReactMarkdown>
  )
}
