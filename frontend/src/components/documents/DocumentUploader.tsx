import { useCallback, useState } from 'react'
import { useDropzone } from 'react-dropzone'
import { UploadCloud } from 'lucide-react'

import { Button } from '@/components/ui/button'
import { uploadDocuments } from '@/api/documents'
import { inferDocumentType } from '@/lib/projects'
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
  const [progress, setProgress] = useState('')

  const onDrop = useCallback(
    async (accepted: File[]) => {
      if (accepted.length === 0) return
      if (accepted.length > MAX_FILES) {
        setError(`Máximo ${MAX_FILES} archivos por subida`)
        return
      }

      const byType = new Map<DocumentType, File[]>()
      for (const file of accepted) {
        const type = inferDocumentType(file.name)
        const list = byType.get(type) ?? []
        list.push(file)
        byType.set(type, list)
      }

      setState('uploading')
      setError(null)
      try {
        const groups = Array.from(byType.entries())
        let done = 0
        for (const [type, files] of groups) {
          setProgress(
            `Subiendo ${done + 1}/${groups.length} (${type === 'article' ? 'artículos' : type})…`
          )
          await uploadDocuments(projectId, files, type)
          done += 1
        }
        setProgress('')
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
  })

  return (
    <div className="space-y-3">
      <div
        {...getRootProps()}
        className={`rounded-xl border border-dashed p-8 text-center transition-colors ${
          isDragActive ? 'border-primary bg-primary/5' : 'border-input'
        }`}
      >
        <input {...getInputProps()} />
        <UploadCloud className="mx-auto mb-3 h-8 w-8 text-muted-foreground" />
        <p className="text-sm font-medium">
          {isDragActive
            ? 'Suelta los PDF aquí…'
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
        >
          Seleccionar archivos
        </Button>
      </div>
      {state === 'uploading' && (
        <p className="text-sm text-muted-foreground" role="status">
          {progress || 'Subiendo…'}
        </p>
      )}
      {error && (
        <p className="text-sm text-destructive" role="alert">
          {error}
        </p>
      )}
    </div>
  )
}
