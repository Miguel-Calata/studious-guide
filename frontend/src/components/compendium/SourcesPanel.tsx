import { Link } from 'react-router-dom'
import useSWR from 'swr'
import { ExternalLink, FileText, Lock, LogIn } from 'lucide-react'

import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import { listCompendiumSources, getSourceDownloadUrl } from '@/api/public'
import { useAuth } from '@/contexts/AuthContext'
import { cn } from '@/lib/utils'

interface SourcesPanelProps {
  slug: string
}

const DOCUMENT_TYPE_LABELS: Record<string, string> = {
  bmj: 'BMJ',
  guideline: 'Guía',
  article: 'Artículo',
}

function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

export function SourcesPanel({ slug }: SourcesPanelProps) {
  const { user, isLoading: authLoading } = useAuth()

  const { data: sources, error, isLoading } = useSWR(
    user ? `/public/compendiums/${slug}/sources` : null,
    () => listCompendiumSources(slug),
    { revalidateOnFocus: false }
  )

  if (authLoading) return null

  if (!user) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-base">
            <FileText className="h-4 w-4" />
            Documentos fuente
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex flex-col items-center gap-3 py-4 text-center">
            <Lock className="h-8 w-8 text-muted-foreground/50" />
            <p className="text-sm text-muted-foreground">
              Inicia sesión para acceder a los PDFs fuente del compendio.
            </p>
            <Button variant="outline" size="sm" asChild>
              <Link to="/login">
                <LogIn className="mr-1 h-3 w-3" />
                Iniciar sesión
              </Link>
            </Button>
          </div>
        </CardContent>
      </Card>
    )
  }

  if (isLoading) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-base">
            <FileText className="h-4 w-4" />
            Documentos fuente
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          {Array.from({ length: 3 }).map((_, i) => (
            <div key={i} className="flex items-center gap-3">
              <Skeleton className="h-4 w-4" />
              <div className="flex-1 space-y-1">
                <Skeleton className="h-4 w-3/4" />
                <Skeleton className="h-3 w-1/4" />
              </div>
            </div>
          ))}
        </CardContent>
      </Card>
    )
  }

  if (error) return null

  if (!sources || sources.length === 0) return null

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-base">
          <FileText className="h-4 w-4" />
          Documentos fuente
          <Badge variant="secondary" className="ml-auto text-xs font-normal">
            {sources.length}
          </Badge>
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-2">
        {sources.map((doc) => (
          <a
            key={doc.id}
            href={getSourceDownloadUrl(slug, doc.id)}
            target="_blank"
            rel="noopener noreferrer"
            className={cn(
              'flex items-center gap-3 rounded-xl border border-border/60 p-3',
              'transition-colors hover:bg-accent'
            )}
          >
            <FileText className="h-5 w-5 shrink-0 text-muted-foreground" />
            <div className="min-w-0 flex-1">
              <p className="truncate text-sm font-medium leading-snug">
                {doc.filename}
              </p>
              <div className="mt-0.5 flex items-center gap-2 text-xs text-muted-foreground">
                <span>{formatFileSize(doc.file_size)}</span>
                <Badge variant="outline" className="text-[10px] font-normal">
                  {DOCUMENT_TYPE_LABELS[doc.document_type] ?? doc.document_type}
                </Badge>
              </div>
            </div>
            <ExternalLink className="h-4 w-4 shrink-0 text-muted-foreground/60" />
          </a>
        ))}
      </CardContent>
    </Card>
  )
}
