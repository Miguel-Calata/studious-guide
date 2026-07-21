import { Link, useParams } from 'react-router-dom'
import { useEffect, useRef } from 'react'
import useSWR from 'swr'

import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Separator } from '@/components/ui/separator'
import { Skeleton } from '@/components/ui/skeleton'
import { DocumentUploader } from '@/components/documents/DocumentUploader'
import { DocumentList } from '@/components/documents/DocumentList'
import { ExtractionCard } from '@/components/pipeline/ExtractionCard'
import { EcosMapCard } from '@/components/pipeline/EcosMapCard'
import { CompendiumCard } from '@/components/pipeline/CompendiumCard'
import { PublishCard } from '@/components/publish/PublishCard'
import { getDocuments } from '@/api/documents'
import { getSections } from '@/api/compendiums'
import { useProjectPolling } from '@/hooks/useProjectPolling'
import { statusLabel, statusVariant } from '@/lib/projects'
import { isProjectBusy, POLL_INTERVAL_MS } from '@/lib/pipeline'
import { toast } from 'sonner'
import type { SourceDocument as Doc } from '@/types/document'
import type { CompendiumSection } from '@/types/compendium'

export function ProjectDetailPage() {
  const { id = '' } = useParams<{ id: string }>()
  const { project, error: projectError, mutate: mutateProject } =
    useProjectPolling(id || undefined)

  const {
    data: documents,
    error: docsError,
    isLoading: docsLoading,
    mutate: mutateDocs,
  } = useSWR<Doc[]>(
    id ? `/projects/${id}/documents` : null,
    () => getDocuments(id),
    {
      refreshInterval: () =>
        project && isProjectBusy(project.status) ? POLL_INTERVAL_MS : 0,
      revalidateOnFocus: false,
    }
  )

  const prevStatuses = useRef<Map<string, string>>(new Map())
  useEffect(() => {
    if (!documents) return
    for (const doc of documents) {
      const prev = prevStatuses.current.get(doc.id)
      if (prev && prev !== 'error' && doc.status === 'error') {
        toast.error(`Error al extraer "${doc.filename}": ${doc.error_message || 'Error desconocido'}`)
      }
      prevStatuses.current.set(doc.id, doc.status)
    }
  }, [documents])

  const {
    data: sections,
    mutate: mutateSections,
  } = useSWR<CompendiumSection[]>(
    id ? `/projects/${id}/sections` : null,
    () => getSections(id),
    {
      refreshInterval: () =>
        project && isProjectBusy(project.status) ? POLL_INTERVAL_MS : 0,
      revalidateOnFocus: false,
    }
  )

  const prevProjectRef = useRef(project?.status)
  useEffect(() => {
    const prev = prevProjectRef.current
    prevProjectRef.current = project?.status
    if (prev && project && isProjectBusy(prev) && !isProjectBusy(project.status)) {
      mutateSections()
    }
  }, [project, mutateSections])

  if (projectError) {
    return (
      <div className="space-y-4">
        <Link
          to="/app"
          className="text-sm font-medium text-foreground underline-offset-4 hover:underline"
        >
          ← Volver a proyectos
        </Link>
        <p className="text-sm text-destructive" role="alert">
          No se encontró el proyecto.
        </p>
      </div>
    )
  }

  if (!project) {
    return (
      <div className="space-y-8" aria-busy="true" aria-label="Cargando proyecto">
        <div className="space-y-3">
          <Skeleton className="h-4 w-32" />
          <Skeleton className="h-9 w-64" />
          <Skeleton className="h-5 w-48" />
        </div>
        <Skeleton className="h-40 w-full rounded-2xl" />
        <Skeleton className="h-32 w-full rounded-2xl" />
      </div>
    )
  }

  const refreshAll = () => {
    mutateProject()
    mutateDocs()
    mutateSections()
  }

  const hasExtractedDocs = (documents ?? []).some(
    (d) => d.status === 'extracted'
  )

  return (
    <div className="space-y-8">
      <div className="space-y-3">
        <Link
          to="/app"
          className="text-sm font-medium text-foreground underline-offset-4 hover:underline"
        >
          ← Volver a proyectos
        </Link>
        <div className="flex flex-wrap items-center gap-3">
          <h1 className="text-3xl font-semibold tracking-tight">
            {project.name}
          </h1>
          <Badge variant={statusVariant(project.status)}>
            {statusLabel(project.status)}
          </Badge>
          {project.is_published && (
            <Badge variant="success">Publicado</Badge>
          )}
        </div>
        {project.description && (
          <p className="max-w-2xl text-base font-medium text-muted-foreground">
            {project.description}
          </p>
        )}
      </div>

      <Separator />

      <Card>
        <CardHeader>
          <CardTitle className="text-lg tracking-tight">
            Subir documentos (PDF)
          </CardTitle>
        </CardHeader>
        <CardContent>
          <DocumentUploader projectId={id} onUploaded={() => mutateDocs()} />
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-lg tracking-tight">Documentos</CardTitle>
        </CardHeader>
        <CardContent>
          {docsError ? (
            <p className="text-sm text-destructive">
              No se pudieron cargar los documentos.
            </p>
          ) : (
            <DocumentList
              documents={documents ?? []}
              isLoading={docsLoading}
              onChanged={() => mutateDocs()}
            />
          )}
        </CardContent>
      </Card>

      <ExtractionCard
        projectId={id}
        projectStatus={project.status}
        documents={documents ?? []}
        onMutate={refreshAll}
      />

      <EcosMapCard project={project} onMutate={refreshAll} />

      <CompendiumCard
        project={project}
        hasExtractedDocs={hasExtractedDocs}
        onMutate={refreshAll}
      />

      <PublishCard
        project={project}
        sections={sections ?? []}
        onMutate={refreshAll}
      />
    </div>
  )
}
