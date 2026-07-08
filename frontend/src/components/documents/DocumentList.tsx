import { useState } from 'react'
import { MoreVertical, Trash2 } from 'lucide-react'

import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { documentTypeLabel } from '@/lib/projects'
import { documentStatusLabel, documentStatusVariant } from '@/lib/pipeline'
import { deleteDocument } from '@/api/documents'
import type { SourceDocument } from '@/types/document'

function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

export function DocumentList({
  documents,
  isLoading,
  onChanged,
}: {
  documents: SourceDocument[]
  isLoading: boolean
  onChanged: () => void
}) {
  const [pendingDelete, setPendingDelete] = useState<SourceDocument | null>(
    null
  )
  const [deleting, setDeleting] = useState(false)

  async function confirmDelete() {
    if (!pendingDelete) return
    setDeleting(true)
    try {
      await deleteDocument(pendingDelete.id)
      setPendingDelete(null)
      onChanged()
    } finally {
      setDeleting(false)
    }
  }

  if (isLoading) {
    return <p className="text-sm text-muted-foreground">Cargando documentos…</p>
  }

  if (documents.length === 0) {
    return (
      <p className="text-sm text-muted-foreground">
        Aún no hay documentos en este proyecto.
      </p>
    )
  }

  return (
    <>
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Archivo</TableHead>
            <TableHead>Tipo</TableHead>
            <TableHead>Estado</TableHead>
            <TableHead>Tamaño</TableHead>
            <TableHead className="w-12" />
          </TableRow>
        </TableHeader>
        <TableBody>
          {documents.map((doc) => (
            <TableRow key={doc.id}>
              <TableCell className="font-medium">{doc.filename}</TableCell>
               <TableCell>
                 <Badge variant="secondary">
                   {documentTypeLabel(doc.document_type)}
                 </Badge>
               </TableCell>
               <TableCell>
                 <Badge variant={documentStatusVariant(doc.status)}>
                   {documentStatusLabel(doc.status)}
                 </Badge>
               </TableCell>
               <TableCell className="text-muted-foreground">
                 {formatSize(doc.file_size)}
               </TableCell>
              <TableCell>
                <DropdownMenu>
                  <DropdownMenuTrigger asChild>
                    <Button variant="ghost" size="icon">
                      <MoreVertical className="h-4 w-4" />
                      <span className="sr-only">Acciones</span>
                    </Button>
                  </DropdownMenuTrigger>
                  <DropdownMenuContent align="end">
                    <DropdownMenuItem
                      className="text-destructive focus:text-destructive"
                      onSelect={() => setPendingDelete(doc)}
                    >
                      <Trash2 className="mr-2 h-4 w-4" />
                      Eliminar
                    </DropdownMenuItem>
                  </DropdownMenuContent>
                </DropdownMenu>
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>

      <Dialog
        open={pendingDelete !== null}
        onOpenChange={(o) => !o && setPendingDelete(null)}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Eliminar documento</DialogTitle>
            <DialogDescription>
              ¿Seguro que quieres eliminar{' '}
              <span className="font-medium">{pendingDelete?.filename}</span>?
              Esta acción no se puede deshacer.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => setPendingDelete(null)}
              disabled={deleting}
            >
              Cancelar
            </Button>
            <Button
              variant="destructive"
              onClick={confirmDelete}
              disabled={deleting}
            >
              {deleting ? 'Eliminando…' : 'Eliminar'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  )
}
