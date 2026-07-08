import { useState } from 'react'
import { RefreshCw, Play } from 'lucide-react'

import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { ProgressBar } from '@/components/pipeline/ProgressBar'
import { extractAllForProject } from '@/api/extractions'
import { notifyError, notifySuccess } from '@/lib/notify'
import { documentStatusLabel } from '@/lib/pipeline'
import type { ProjectStatus } from '@/types/project'
import type { SourceDocument } from '@/types/document'

const CAN_EXTRACT: ProjectStatus[] = ['draft', 'extracting']

export function ExtractionCard({
  projectId,
  projectStatus,
  documents,
  onMutate,
}: {
  projectId: string
  projectStatus: ProjectStatus
  documents: SourceDocument[]
  onMutate: () => void
}) {
  const [busy, setBusy] = useState(false)

  const canExtract = CAN_EXTRACT.includes(projectStatus)
  const completed = documents.filter((d) => d.status === 'extracted').length
  const failed = documents.filter((d) => d.status === 'error').length
  const hasDocs = documents.length > 0

  async function runExtractAll() {
    setBusy(true)
    try {
      const res = await extractAllForProject(projectId)
      notifySuccess(
        `Extracción iniciada: ${res.enqueued} en cola${
          res.skipped > 0 ? `, ${res.skipped} omitidos` : ''
        }.`
      )
      onMutate()
    } catch (err) {
      notifyError(err, 'No se pudo iniciar la extracción.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Extracción</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        {!hasDocs ? (
          <p className="text-sm text-muted-foreground">
            Sube al menos un documento para poder extraer.
          </p>
        ) : (
          <>
            <ProgressBar
              value={completed}
              total={documents.length}
              label="Documentos extraídos"
            />
            <div className="flex flex-wrap items-center gap-2">
              <Button
                onClick={runExtractAll}
                disabled={!canExtract || busy}
              >
                <Play className="mr-2 h-4 w-4" />
                {busy ? 'Iniciando…' : 'Extraer todo'}
              </Button>
              {failed > 0 && (
                <Button
                  variant="outline"
                  onClick={runExtractAll}
                  disabled={busy || projectStatus === 'archived'}
                >
                  <RefreshCw className="mr-2 h-4 w-4" />
                  Reintentar fallidos ({failed})
                </Button>
              )}
            </div>
            {!canExtract && (
              <p className="text-xs text-muted-foreground">
                La extracción no está disponible en el estado actual del
                proyecto ({documentStatusLabel(projectStatus)}).
              </p>
            )}
          </>
        )}
      </CardContent>
    </Card>
  )
}
