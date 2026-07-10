import { useState, useEffect } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { ExternalLink, Globe, Loader2, NotepadText, Search, Unlink } from 'lucide-react'
import useSWR from 'swr'

import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Separator } from '@/components/ui/separator'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { publishProject } from '@/api/publishing'
import {
  getNotionStatus,
  startNotionOAuth,
  disconnectNotion,
  searchNotionPages,
  updateNotionConfig,
  publishToNotion,
} from '@/api/notion'
import { notifyError, notifySuccess } from '@/lib/notify'
import type { Project } from '@/types/project'
import type { CompendiumSection } from '@/types/compendium'
import type { NotionStatusResponse, PublishNotionResponse } from '@/types/notion'
import type { PublishResponse } from '@/types/publishing'

import { getPublicDownloadUrl } from '@/api/public'

interface PublishCardProps {
  project: Project
  sections: CompendiumSection[]
  onMutate: () => void
}

export function PublishCard({ project, sections, onMutate }: PublishCardProps) {
  const canPublish =
    (project.status === 'review' || project.status === 'completed') &&
    sections.length === 11 &&
    sections.every((s) => s.status === 'completed' || s.status === 'approved')

  const failedCount = sections.filter((s) => s.status === 'failed').length
  const doneCount = sections.filter(
    (s) => s.status === 'completed' || s.status === 'approved'
  ).length
  const publishGateMessage =
    failedCount > 0
      ? `${failedCount} sección(es) fallaron. Regenera las secciones antes de publicar.`
      : doneCount < 11
        ? `Generando compendio... (${doneCount}/11 secciones)`
        : 'Necesitas generar y revisar las 11 secciones antes de publicar.'

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Publicación</CardTitle>
      </CardHeader>
      <CardContent className="space-y-6">
        <WebPublishSection
          project={project}
          canPublish={canPublish}
          publishGateMessage={publishGateMessage}
          onMutate={onMutate}
        />
        <Separator />
        <NotionPublishSection
          project={project}
          canPublish={canPublish}
          publishGateMessage={publishGateMessage}
        />
      </CardContent>
    </Card>
  )
}

/* ─── Publicación web (S3) ─── */

function WebPublishSection({
  project,
  canPublish,
  publishGateMessage,
  onMutate,
}: {
  project: Project
  canPublish: boolean
  publishGateMessage: string
  onMutate: () => void
}) {
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState<PublishResponse | null>(null)

  const handlePublish = async () => {
    setLoading(true)
    try {
      const res = await publishProject(project.id)
      setResult(res)
      notifySuccess('Compendio publicado correctamente')
      onMutate()
    } catch (err) {
      notifyError(err)
    } finally {
      setLoading(false)
    }
  }

  const published = project.is_published || result !== null
  const slug = result?.slug ?? project.slug

  return (
    <div className="space-y-3">
      <h4 className="text-sm font-medium flex items-center gap-2">
        <Globe className="h-4 w-4" />
        Web pública
      </h4>

      {published ? (
        <div className="space-y-2">
          <Badge variant="success">Publicado</Badge>
          <p className="text-sm text-muted-foreground">
            El compendio está disponible públicamente.
          </p>
          <div className="flex flex-wrap gap-2">
            <Button variant="outline" size="sm" asChild>
              <Link to={`/compendiums/${slug}`}>Ver visor público</Link>
            </Button>
            <Button variant="outline" size="sm" asChild>
              <a href={getPublicDownloadUrl(slug)} download>
                Descargar .md
              </a>
            </Button>
            <Button
              variant="secondary"
              size="sm"
              disabled={!canPublish || loading}
              onClick={handlePublish}
            >
              {loading && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              Republicar
            </Button>
          </div>
        </div>
      ) : (
        <div className="space-y-2">
          <p className="text-sm text-muted-foreground">
            Publica el compendio para hacerlo accesible públicamente.
          </p>
          <Button
            disabled={!canPublish || loading}
            onClick={handlePublish}
          >
            {loading && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
            Publicar
          </Button>
          {!canPublish && project.status !== 'completed' && (
            <p className="text-xs text-muted-foreground">
              {publishGateMessage}
            </p>
          )}
        </div>
      )}
    </div>
  )
}

/* ─── Notion ─── */

function NotionPublishSection({
  project,
  canPublish,
  publishGateMessage,
}: {
  project: Project
  canPublish: boolean
  publishGateMessage: string
}) {
  const { data: notionStatus, mutate: mutateNotion } = useSWR(
    '/notion/status',
    getNotionStatus,
    { revalidateOnFocus: false }
  )

  const [searchParams, setSearchParams] = useSearchParams()

  // Handle OAuth callback redirect ?notion=connected or ?notion=error
  useEffect(() => {
    const notionParam = searchParams.get('notion')
    if (notionParam === 'connected') {
      notifySuccess('Notion conectado correctamente')
      mutateNotion()
      setSearchParams({}, { replace: true })
    } else if (notionParam === 'error') {
      const msg = searchParams.get('msg') ?? 'Error al conectar con Notion'
      notifyError(new Error(msg))
      setSearchParams({}, { replace: true })
    }
  }, [searchParams, setSearchParams, mutateNotion])

  if (!notionStatus) {
    return (
      <div className="space-y-3">
        <h4 className="text-sm font-medium flex items-center gap-2">
          <NotepadText className="h-4 w-4" />
          Notion
        </h4>
        <p className="text-sm text-muted-foreground">Cargando estado…</p>
      </div>
    )
  }

  return (
    <div className="space-y-3">
      <h4 className="text-sm font-medium flex items-center gap-2">
        <NotepadText className="h-4 w-4" />
        Notion
      </h4>

      {notionStatus.is_connected ? (
        <NotionConnectedBlock
          project={project}
          canPublish={canPublish}
          publishGateMessage={publishGateMessage}
          status={notionStatus}
          onStatusChange={mutateNotion}
        />
      ) : (
        <NotionConnectBlock />
      )}
    </div>
  )
}

/* ─── Conectar Notion (OAuth) ─── */

function NotionConnectBlock() {
  const [loading, setLoading] = useState(false)

  const handleConnect = async () => {
    setLoading(true)
    try {
      const { authorize_url } = await startNotionOAuth()
      window.location.href = authorize_url
    } catch (err) {
      notifyError(err)
      setLoading(false)
    }
  }

  return (
    <div className="space-y-2">
      <p className="text-sm text-muted-foreground">
        Conecta tu cuenta de Notion para publicar compendios directamente en tu workspace.
      </p>
      <Button size="sm" disabled={loading} onClick={handleConnect}>
        {loading && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
        Conectar con Notion
      </Button>
    </div>
  )
}

/* ─── Notion conectado ─── */

function NotionConnectedBlock({
  project,
  canPublish,
  publishGateMessage,
  status,
  onStatusChange,
}: {
  project: Project
  canPublish: boolean
  publishGateMessage: string
  status: NotionStatusResponse
  onStatusChange: () => void
}) {
  const [publishing, setPublishing] = useState(false)
  const [notionResult, setNotionResult] = useState<PublishNotionResponse | null>(null)
  const [parentPageId, setParentPageId] = useState(status.default_parent_page_id ?? '')
  const [searchQuery, setSearchQuery] = useState('')
  const [showSearch, setShowSearch] = useState(false)
  const [disconnecting, setDisconnecting] = useState(false)

  const { data: searchResults } = useSWR(
    showSearch && searchQuery.length >= 2
      ? ['/notion/search', searchQuery]
      : null,
    ([, q]) => searchNotionPages(q),
    { dedupingInterval: 500 }
  )

  const handleSetDefault = async () => {
    if (!parentPageId.trim()) return
    try {
      await updateNotionConfig({ default_parent_page_id: parentPageId.trim() })
      notifySuccess('Página padre configurada')
      onStatusChange()
    } catch (err) {
      notifyError(err)
    }
  }

  const handlePublish = async () => {
    setPublishing(true)
    try {
      const res = await publishToNotion(
        project.id,
        parentPageId.trim() || undefined
      )
      setNotionResult(res)
      notifySuccess('Compendio publicado en Notion')
    } catch (err) {
      notifyError(err)
    } finally {
      setPublishing(false)
    }
  }

  const handleDisconnect = async () => {
    setDisconnecting(true)
    try {
      await disconnectNotion()
      notifySuccess('Notion desconectado')
      onStatusChange()
    } catch (err) {
      notifyError(err)
    } finally {
      setDisconnecting(false)
    }
  }

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          {status.needs_reconnect ? (
            <Badge variant="destructive">Sesión expirada</Badge>
          ) : (
            <Badge variant="success">Conectado</Badge>
          )}
          {status.workspace_name && (
            <span className="text-sm text-muted-foreground">
              {status.workspace_name}
            </span>
          )}
          {status.owner_email && (
            <span className="text-xs text-muted-foreground">
              ({status.owner_email})
            </span>
          )}
        </div>
        <Button
          variant="ghost"
          size="sm"
          className="text-xs h-7 px-2 text-destructive hover:text-destructive"
          disabled={disconnecting}
          onClick={handleDisconnect}
        >
          {disconnecting ? (
            <Loader2 className="mr-1 h-3 w-3 animate-spin" />
          ) : (
            <Unlink className="mr-1 h-3 w-3" />
          )}
          Desconectar
        </Button>
      </div>

      {status.needs_reconnect && (
        <div className="rounded-md bg-destructive/10 p-3 text-sm text-destructive">
          Tu sesión de Notion ha expirado. Desconecta y vuelve a conectar para
          seguir publicando.
        </div>
      )}

      {/* Selector de página padre */}
      <div className="space-y-2">
        <Label htmlFor="parent-page" className="text-xs">
          Página padre
        </Label>
        <div className="flex gap-2">
          <Input
            id="parent-page"
            placeholder="ID de página de Notion"
            value={parentPageId}
            onChange={(e) => setParentPageId(e.target.value)}
          />
          <Button
            variant="outline"
            size="sm"
            disabled={!parentPageId.trim()}
            onClick={handleSetDefault}
          >
            Guardar
          </Button>
        </div>

        <Button
          variant="ghost"
          size="sm"
          className="text-xs h-7 px-2"
          onClick={() => setShowSearch(!showSearch)}
        >
          <Search className="mr-1 h-3 w-3" />
          {showSearch ? 'Ocultar búsqueda' : 'Buscar páginas'}
        </Button>

        {showSearch && (
          <div className="space-y-2">
            <Input
              placeholder="Buscar en Notion…"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
            />
            {searchResults && searchResults.length > 0 && (
              <div className="border rounded-md divide-y max-h-40 overflow-auto">
                {searchResults.map((r) => (
                  <button
                    key={r.id}
                    className="w-full text-left px-3 py-2 text-sm hover:bg-accent transition-colors"
                    onClick={() => {
                      setParentPageId(r.id)
                      setShowSearch(false)
                    }}
                  >
                    <span className="font-medium">{r.title || 'Sin título'}</span>
                    <span className="ml-2 text-xs text-muted-foreground">
                      {r.object}
                    </span>
                  </button>
                ))}
              </div>
            )}
            {searchResults && searchResults.length === 0 && searchQuery.length >= 2 && (
              <p className="text-xs text-muted-foreground">Sin resultados</p>
            )}
          </div>
        )}
      </div>

      {/* Botón publicar */}
      <div className="flex flex-wrap items-center gap-2">
        <Button
          disabled={!canPublish || publishing || status.needs_reconnect}
          onClick={handlePublish}
        >
          {publishing && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
          {publishing
            ? 'Publicando en Notion…'
            : 'Publicar en Notion'}
        </Button>
        {publishing && (
          <span className="text-xs text-muted-foreground">
            Puede tardar hasta 30 segundos
          </span>
        )}
      </div>

      {/* Resultado */}
      {notionResult && (
        <div className="flex items-center gap-2">
          <Button variant="outline" size="sm" asChild>
            <a
              href={notionResult.notion_url}
              target="_blank"
              rel="noopener noreferrer"
            >
              <ExternalLink className="mr-1 h-3 w-3" />
              Abrir en Notion
            </a>
          </Button>
          <span className="text-xs text-muted-foreground">
            {notionResult.sections_published.length} secciones publicadas
          </span>
        </div>
      )}

      {!canPublish && (
        <p className="text-xs text-muted-foreground">
          {publishGateMessage}
        </p>
      )}
    </div>
  )
}
