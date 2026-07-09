import { Link, useParams } from 'react-router-dom'
import useSWR from 'swr'
import { Download, Loader2 } from 'lucide-react'

import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Separator } from '@/components/ui/separator'
import { MarkdownViewer } from '@/components/public/MarkdownViewer'
import {
  getPublicCompendium,
  getPublicSection,
  getPublicDownloadUrl,
} from '@/api/public'

export function PublicCompendiumDetailPage() {
  const { slug = '' } = useParams<{ slug: string }>()

  const { data: detail, error, isLoading } = useSWR(
    slug ? `/public/compendiums/${slug}` : null,
    () => getPublicCompendium(slug),
    { revalidateOnFocus: false }
  )

  if (isLoading) {
    return <p className="text-muted-foreground">Cargando compendio…</p>
  }

  if (error || !detail) {
    return (
      <div className="space-y-4">
        <Link to="/compendiums" className="text-sm text-primary underline">
          ← Volver a compendios
        </Link>
        <p className="text-destructive">No se encontró el compendio.</p>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <Link to="/compendiums" className="text-sm text-primary underline">
        ← Volver a compendios
      </Link>

      <div>
        <h1 className="text-2xl font-semibold tracking-tight">{detail.name}</h1>
        {detail.description && (
          <p className="mt-1 text-muted-foreground">{detail.description}</p>
        )}
        <div className="mt-3 flex flex-wrap items-center gap-3">
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
        </div>
      </div>

      <Separator />

      {/* TOC */}
      <nav className="space-y-1">
        <h2 className="text-sm font-semibold text-muted-foreground uppercase tracking-wider mb-2">
          Índice
        </h2>
        <div className="grid gap-1 sm:grid-cols-2">
          {detail.sections.map((s) => (
            <a
              key={s.section_number}
              href={`#section-${s.section_number}`}
              className="text-sm text-primary hover:underline truncate"
            >
              {s.section_number}. {s.section_name}
            </a>
          ))}
        </div>
      </nav>

      <Separator />

      {/* Secciones */}
      {detail.sections.map((s) => (
        <SectionBlock
          key={s.section_number}
          slug={slug}
          sectionNumber={s.section_number}
          sectionName={s.section_name}
        />
      ))}
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
    <section id={`section-${sectionNumber}`} className="scroll-mt-20 space-y-3">
      <h2 className="text-xl font-semibold border-b pb-2">
        {sectionNumber}. {sectionName}
      </h2>

      {isLoading && (
        <p className="text-sm text-muted-foreground flex items-center gap-2">
          <Loader2 className="h-3 w-3 animate-spin" />
          Cargando sección…
        </p>
      )}

      {error && (
        <p className="text-sm text-destructive">Error al cargar la sección.</p>
      )}

      {data && <MarkdownViewer content={data.content} />}
    </section>
  )
}
