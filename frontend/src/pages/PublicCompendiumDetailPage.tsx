import { useCallback, useEffect, useRef, useState } from 'react'
import {
  Link,
  useLocation,
  useNavigate,
  useParams,
  useSearchParams,
} from 'react-router-dom'
import useSWR from 'swr'
import { Download, ExternalLink, List, Loader2, NotepadText } from 'lucide-react'

import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Skeleton } from '@/components/ui/skeleton'
import { MarkdownViewer } from '@/components/public/MarkdownViewer'
import { SourcesPanel } from '@/components/compendium/SourcesPanel'
import {
  getPublicCompendium,
  getPublicSection,
  getPublicDownloadUrl,
} from '@/api/public'
import {
  exportPublicNoteToNotion,
  getNotionStatus,
  startNotionOAuth,
} from '@/api/notion'
import { useAuth } from '@/contexts/AuthContext'
import { notifyError, notifySuccess } from '@/lib/notify'
import { cn } from '@/lib/utils'
import type { PublicSectionSummary } from '@/types/public'

export function PublicCompendiumDetailPage() {
  const { slug = '' } = useParams<{ slug: string }>()
  const location = useLocation()
  const navigate = useNavigate()
  const [searchParams, setSearchParams] = useSearchParams()
  const { user, isLoading: authLoading } = useAuth()

  const { data: detail, error, isLoading } = useSWR(
    slug ? `/public/compendiums/${slug}` : null,
    () => getPublicCompendium(slug),
    { revalidateOnFocus: false }
  )

  const [activeSection, setActiveSection] = useState<number | null>(null)
  const [exporting, setExporting] = useState(false)
  const [notionUrl, setNotionUrl] = useState<string | null>(null)
  const oauthHandled = useRef(false)

  const runExport = useCallback(async () => {
    if (!slug) return
    setExporting(true)
    try {
      const res = await exportPublicNoteToNotion(slug)
      setNotionUrl(res.notion_url)
      notifySuccess('Nota añadida a Notion')
    } catch (err) {
      notifyError(err, 'No se pudo añadir a Notion')
    } finally {
      setExporting(false)
    }
  }, [slug])

  const connectAndReturn = useCallback(async () => {
    const returnTo = `/compendiums/${slug}`
    try {
      const { authorize_url } = await startNotionOAuth(returnTo)
      window.location.href = authorize_url
    } catch (err) {
      notifyError(err, 'No se pudo iniciar la conexión con Notion')
    }
  }, [slug])

  const handleAddToNotion = useCallback(async () => {
    if (authLoading || exporting) return
    if (!user) {
      navigate('/login', { state: { from: location } })
      return
    }
    setExporting(true)
    try {
      const status = await getNotionStatus()
      if (!status.is_connected || status.needs_reconnect) {
        await connectAndReturn()
        return
      }
      const res = await exportPublicNoteToNotion(slug)
      setNotionUrl(res.notion_url)
      notifySuccess('Nota añadida a Notion')
    } catch (err) {
      notifyError(err, 'No se pudo añadir a Notion')
    } finally {
      setExporting(false)
    }
  }, [
    authLoading,
    exporting,
    user,
    navigate,
    location,
    connectAndReturn,
    slug,
  ])

  useEffect(() => {
    if (!slug || authLoading || oauthHandled.current) return
    const notionParam = searchParams.get('notion')
    if (!notionParam) return
    oauthHandled.current = true
    const next = new URLSearchParams(searchParams)
    next.delete('notion')
    next.delete('msg')
    setSearchParams(next, { replace: true })

    if (notionParam === 'error') {
      const msg = searchParams.get('msg') ?? 'Error al conectar con Notion'
      notifyError(new Error(msg))
      return
    }
    if (notionParam === 'connected' && user) {
      notifySuccess('Notion conectado')
      void runExport()
    }
  }, [slug, authLoading, user, searchParams, setSearchParams, runExport])

  useEffect(() => {
    if (!detail?.sections.length) return

    const nodes = detail.sections
      .map((s) => document.getElementById(`section-${s.section_number}`))
      .filter((el): el is HTMLElement => el !== null)

    if (nodes.length === 0) return

    const visible = new Map<number, number>()

    const observer = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          const id = entry.target.id
          const num = Number(id.replace('section-', ''))
          if (!Number.isFinite(num)) continue
          if (entry.isIntersecting) {
            visible.set(num, entry.intersectionRatio)
          } else {
            visible.delete(num)
          }
        }
        if (visible.size === 0) return
        const best = [...visible.entries()].sort((a, b) => b[1] - a[1])[0]?.[0]
        if (best != null) setActiveSection(best)
      },
      {
        rootMargin: '-15% 0px -55% 0px',
        threshold: [0, 0.15, 0.35, 0.6, 1],
      }
    )

    for (const node of nodes) observer.observe(node)
    return () => observer.disconnect()
  }, [detail])

  if (isLoading) {
    return (
      <div className="space-y-8" aria-busy="true" aria-label="Cargando nota">
        <Skeleton className="h-4 w-28" />
        <div className="space-y-3">
          <Skeleton className="h-9 w-2/3 max-w-md" />
          <Skeleton className="h-5 w-full max-w-lg" />
          <Skeleton className="h-8 w-48" />
        </div>
        <div className="grid gap-10 lg:grid-cols-[14rem_minmax(0,1fr)]">
          <div className="hidden space-y-2 lg:block">
            {Array.from({ length: 6 }).map((_, i) => (
              <Skeleton key={i} className="h-4 w-full" />
            ))}
          </div>
          <div className="space-y-4">
            <Skeleton className="h-7 w-1/2" />
            <Skeleton className="h-24 w-full" />
            <Skeleton className="h-24 w-full" />
          </div>
        </div>
      </div>
    )
  }

  if (error || !detail) {
    return (
      <div className="space-y-4">
        <Link
          to="/compendiums"
          className="text-sm font-medium text-foreground underline-offset-4 hover:underline"
        >
          ← Volver a notas
        </Link>
        <p className="text-destructive" role="alert">
          No se encontró la nota.
        </p>
      </div>
    )
  }

  return (
    <div className="space-y-8">
      <Link
        to="/compendiums"
        className="inline-block text-sm font-medium text-foreground underline-offset-4 hover:underline"
      >
        ← Volver a notas
      </Link>

      <header className="space-y-3">
        <h1 className="text-3xl font-semibold tracking-tight sm:text-4xl">
          {detail.name}
        </h1>
        {detail.description && (
          <p className="max-w-2xl text-base text-muted-foreground sm:text-lg">
            {detail.description}
          </p>
        )}
        <div className="flex flex-wrap items-center gap-3">
          <Badge variant="info">{detail.section_count} secciones</Badge>
          {detail.published_at && (
            <span className="text-sm text-muted-foreground">
              Publicado el{' '}
              {new Date(detail.published_at).toLocaleDateString('es-ES', {
                year: 'numeric',
                month: 'long',
                day: 'numeric',
              })}
            </span>
          )}
          <Button variant="outline" size="sm" asChild>
            <a href={getPublicDownloadUrl(slug)} download>
              <Download className="mr-1 h-3 w-3" />
              Descargar .md
            </a>
          </Button>
          <Button
            variant="outline"
            size="sm"
            onClick={() => void handleAddToNotion()}
            disabled={exporting || authLoading}
          >
            {exporting ? (
              <Loader2 className="mr-1 h-3 w-3 animate-spin" />
            ) : (
              <NotepadText className="mr-1 h-3 w-3" />
            )}
            {exporting ? 'Añadiendo…' : 'Añadir a Notion'}
          </Button>
          {notionUrl && (
            <Button variant="secondary" size="sm" asChild>
              <a href={notionUrl} target="_blank" rel="noopener noreferrer">
                <ExternalLink className="mr-1 h-3 w-3" />
                Abrir en Notion
              </a>
            </Button>
          )}
        </div>
      </header>

      <div className="grid items-start gap-10 lg:grid-cols-[14rem_minmax(0,1fr)]">
        <NoteToc
          sections={detail.sections}
          activeSection={activeSection}
        />

        <div className="min-w-0 space-y-14">
          {detail.sections.map((s) => (
            <SectionBlock
              key={s.section_number}
              slug={slug}
              sectionNumber={s.section_number}
              sectionName={s.section_name}
            />
          ))}
        </div>
      </div>

      <SourcesPanel slug={slug} />
    </div>
  )
}

function NoteToc({
  sections,
  activeSection,
}: {
  sections: PublicSectionSummary[]
  activeSection: number | null
}) {
  return (
    <div className="lg:sticky lg:top-6 lg:max-h-[calc(100vh-3rem)] lg:overflow-y-auto">
      {/* Mobile */}
      <nav
        aria-label="Índice"
        className="rounded-2xl border border-border p-4 lg:hidden"
      >
        <p className="mb-3 flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
          <List className="size-3.5" />
          Índice
        </p>
        <ol className="grid gap-1 sm:grid-cols-2">
          {sections.map((s) => (
            <li key={s.section_number}>
              <a
                href={`#section-${s.section_number}`}
                className={cn(
                  'block truncate rounded-md px-2 py-1.5 text-sm transition-colors',
                  activeSection === s.section_number
                    ? 'bg-foreground/[0.06] font-medium text-foreground'
                    : 'text-muted-foreground hover:text-foreground'
                )}
              >
                <span className="tabular-nums text-muted-foreground">
                  {s.section_number}.
                </span>{' '}
                {s.section_name}
              </a>
            </li>
          ))}
        </ol>
      </nav>

      {/* Desktop */}
      <nav aria-label="Índice" className="hidden lg:block">
        <p className="mb-3 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
          Índice
        </p>
        <ol className="space-y-0.5 border-l border-border">
          {sections.map((s) => {
            const active = activeSection === s.section_number
            return (
              <li key={s.section_number}>
                <a
                  href={`#section-${s.section_number}`}
                  className={cn(
                    '-ml-px block border-l-2 py-1.5 pl-3 text-sm leading-snug transition-colors',
                    active
                      ? 'border-foreground font-medium text-foreground'
                      : 'border-transparent text-muted-foreground hover:text-foreground'
                  )}
                >
                  <span className="tabular-nums opacity-60">
                    {s.section_number}.
                  </span>{' '}
                  {s.section_name}
                </a>
              </li>
            )
          })}
        </ol>
      </nav>
    </div>
  )
}

function SectionBlock({
  slug,
  sectionNumber,
  sectionName,
}: {
  slug: string
  sectionNumber: number
  sectionName: string
}) {
  const { data, error, isLoading } = useSWR(
    `/public/compendiums/${slug}/sections/${sectionNumber}`,
    () => getPublicSection(slug, sectionNumber),
    { revalidateOnFocus: false }
  )

  return (
    <section
      id={`section-${sectionNumber}`}
      className="scroll-mt-8 space-y-4"
    >
      <h2 className="border-b border-border pb-2 text-xl font-semibold tracking-tight sm:text-2xl">
        <span className="tabular-nums text-muted-foreground">
          {sectionNumber}.
        </span>{' '}
        {sectionName}
      </h2>

      {isLoading && (
        <div className="space-y-3" aria-busy="true" aria-label="Cargando sección">
          <Skeleton className="h-4 w-full max-w-prose" />
          <Skeleton className="h-4 w-full max-w-prose" />
          <Skeleton className="h-4 w-4/5 max-w-prose" />
          <Skeleton className="h-4 w-full max-w-prose" />
          <Skeleton className="h-4 w-2/3 max-w-prose" />
        </div>
      )}

      {error && (
        <p className="text-sm text-destructive" role="alert">
          Error al cargar la sección.
        </p>
      )}

      {data && <MarkdownViewer content={data.content} />}
    </section>
  )
}
