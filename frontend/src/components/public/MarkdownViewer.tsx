import { useEffect, useMemo, useRef } from 'react'
import { marked } from 'marked'
import DOMPurify from 'dompurify'

import { cn } from '@/lib/utils'
import './MarkdownViewer.css'

interface MarkdownViewerProps {
  content: string
  className?: string
}

export function MarkdownViewer({ content, className }: MarkdownViewerProps) {
  const ref = useRef<HTMLDivElement>(null)

  const html = useMemo(() => {
    const raw = marked.parse(content, { async: false }) as string
    return DOMPurify.sanitize(raw, {
      ADD_TAGS: ['iframe'],
      ADD_ATTR: ['target', 'rel'],
    })
  }, [content])

  useEffect(() => {
    if (!ref.current) return
    ref.current.querySelectorAll('a').forEach((a) => {
      a.setAttribute('target', '_blank')
      a.setAttribute('rel', 'noopener noreferrer')
    })
  }, [html])

  return (
    <div
      ref={ref}
      className={cn('markdown-viewer', className)}
      dangerouslySetInnerHTML={{ __html: html }}
    />
  )
}
