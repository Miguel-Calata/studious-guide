import { useCallback, useState } from 'react'
import { useDropzone, type FileRejection } from 'react-dropzone'
import { AlertCircle, FileText, Loader2, UploadCloud } from 'lucide-react'

import { Alert, AlertDescription } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Progress } from '@/components/ui/progress'
import { uploadDocuments } from '@/api/documents'
import { inferDocumentType } from '@/lib/projects'
import { cn } from '@/lib/utils'
import type { DocumentType } from '@/types/document'

const MAX_FILE_SIZE = 50 * 1024 * 1024
const MAX_FILES = 15

type UploadState = 'idle' | 'uploading' | 'error'

export function DocumentUploader({
  projectId,
  onUploaded,
}: {
  projectId: string
  onUploaded: () => void
}) {
  const [state, setState] = useState<UploadState>('idle')
  const [error, setError] = useState<string | null>(null)
  const [progressLabel, setProgressLabel] = useState('')
  const [progressValue, setProgressValue] = useState(0)
  const [progressTotal, setProgressTotal] = useState(0)
  const [queuedNames, setQueuedNames] = useState<string[]>([])

  const onDrop = useCallback(
    async (accepted: File[], rejected: FileRejection[]) => {
      if (rejected.length > 0) {
        const tooBig = rejected.some((r) =>
          r.errors.some((e) => e.code === 'file-too-large')
        )
        setError(
          tooBig
            ? `Algún archivo supera el límite de 50MB`
            : 'Solo se admiten archivos PDF'
        )
        setState('error')
        return
      }

      if (accepted.length === 0) return
      if (accepted.length > MAX_FILES) {
        setError(`Máximo ${MAX_FILES} archivos por subida`)
        setState('error')
        return
      }

      const byType = new Map<DocumentType, File[]>()
      for (const file of accepted) {
        const type = inferDocumentType(file.name)
        const list = byType.get(type) ?? []
        list.push(file)
        byType.set(type, list)
      }

      const groups = Array.from(byType.entries())
      setQueuedNames(accepted.map((f) => f.name))
      setState('uploading')
      setError(null)
      setProgressTotal(groups.length)
      setProgressValue(0)

      try {
        let done = 0
        for (const [type, files] of groups) {
          setProgressLabel(
            `Subiendo ${done + 1}/${groups.length} (${type === 'article' ? 'artículos' : type})…`
          )
          await uploadDocuments(projectId, files, type)
          done += 1
          setProgressValue(done)
        }
        setProgressLabel('')
        setQueuedNames([])
        setState('idle')
        onUploaded()
      } catch (e) {
        setError(
          e instanceof Error ? e.message : 'No se pudieron subir los archivos'
        )
        setState('error')
      }
    },
    [projectId, onUploaded]
  )

  const { getRootProps, getInputProps, isDragActive, open } = useDropzone({
    onDrop,
    accept: { 'application/pdf': ['.pdf'] },
    maxSize: MAX_FILE_SIZE,
    multiple: true,
    noClick: true,
    noKeyboard: true,
    disabled: state === 'uploading',
  })

  return (
    <div className="space-y-3">
      <div
        {...getRootProps()}
        className={cn(
          'rounded-2xl border border-dashed p-8 text-center transition-colors',
          isDragActive && 'border-foreground bg-foreground/[0.03]',
          !isDragActive && state !== 'error' && 'border-border',
          state === 'error' && 'border-destructive/50',
          state === 'uploading' && 'pointer-events-none opacity-70'
        )}
      >
        <input {...getInputProps()} />
        {state === 'uploading' ? (
          <Loader2 className="mx-auto mb-3 h-8 w-8 animate-spin text-muted-foreground" />
        ) : (
          <UploadCloud className="mx-auto mb-3 h-8 w-8 text-muted-foreground" />
        )}
        <p className="text-sm font-medium">
          {isDragActive
            ? 'Suelta los PDF aquí…'
            : state === 'uploading'
              ? 'Subiendo documentos…'
              : 'Arrastra y suelta tus PDF aquí'}
        </p>
        <p className="text-xs text-muted-foreground">
          o selecciónalos manualmente. Máximo {MAX_FILES} archivos, 50MB c/u.
        </p>
        <Button
          type="button"
          variant="outline"
          size="sm"
          className="mt-4"
          onClick={open}
          disabled={state === 'uploading'}
        >
          Seleccionar archivos
        </Button>
      </div>

      {state === 'uploading' && (
        <div className="space-y-2" role="status">
          <div className="flex items-center justify-between text-xs text-muted-foreground">
            <span>{progressLabel || 'Subiendo…'}</span>
            <span className="tabular-nums">
              {progressValue}/{progressTotal || 1}
            </span>
          </div>
          <Progress value={progressValue} max={progressTotal || 1} />
          {queuedNames.length > 0 && (
            <ul className="max-h-24 space-y-1 overflow-auto text-left text-xs text-muted-foreground">
              {queuedNames.slice(0, 6).map((name) => (
                <li key={name} className="flex items-center gap-1.5 truncate">
                  <FileText className="size-3 shrink-0" />
                  <span className="truncate">{name}</span>
                </li>
              ))}
              {queuedNames.length > 6 && (
                <li>+{queuedNames.length - 6} más</li>
              )}
            </ul>
          )}
        </div>
      )}

      {error && (
        <Alert variant="destructive">
          <AlertCircle />
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}
    </div>
  )
}
