import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { useState } from 'react'

import { Alert, AlertDescription } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import {
  projectCreateSchema,
  type ProjectCreateFormValues,
} from '@/schemas/project'
import { createProject } from '@/api/projects'
import { ApiError } from '@/api/client'
import type { Project } from '@/types/project'

export function CreateProjectDialog({
  open,
  onOpenChange,
  onCreated,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  onCreated: (project: Project) => void
}) {
  const [error, setError] = useState<string | null>(null)

  const {
    register,
    handleSubmit,
    reset,
    formState: { errors, isSubmitting },
  } = useForm<ProjectCreateFormValues>({
    resolver: zodResolver(projectCreateSchema),
    defaultValues: { name: '', description: '' },
  })

  async function onSubmit(values: ProjectCreateFormValues) {
    setError(null)
    try {
      const project = await createProject({
        name: values.name,
        description: values.description || undefined,
      })
      reset()
      onOpenChange(false)
      onCreated(project)
    } catch (e) {
      if (e instanceof ApiError) {
        setError(e.message)
      } else {
        setError('No se pudo crear el proyecto')
      }
    }
  }

  return (
    <Dialog
      open={open}
      onOpenChange={(o) => {
        reset()
        setError(null)
        onOpenChange(o)
      }}
    >
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Nuevo proyecto</DialogTitle>
          <DialogDescription>
            Crea un compendio para una patología o tema clínico.
          </DialogDescription>
        </DialogHeader>
        <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
          {error && (
            <Alert variant="destructive">
              <AlertDescription role="alert">{error}</AlertDescription>
            </Alert>
          )}
          <div className="space-y-2">
            <Label htmlFor="name">Nombre</Label>
            <Input id="name" autoFocus {...register('name')} />
            {errors.name && (
              <p className="text-sm text-destructive">{errors.name.message}</p>
            )}
          </div>
          <div className="space-y-2">
            <Label htmlFor="description">Descripción (opcional)</Label>
            <Textarea
              id="description"
              rows={3}
              {...register('description')}
            />
            {errors.description && (
              <p className="text-sm text-destructive">
                {errors.description.message}
              </p>
            )}
          </div>
          <DialogFooter>
            <Button type="submit" disabled={isSubmitting}>
              {isSubmitting ? 'Creando…' : 'Crear proyecto'}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}
