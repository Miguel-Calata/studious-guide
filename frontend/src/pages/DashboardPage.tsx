import { useState } from 'react'
import useSWR from 'swr'

import { useAuth } from '@/contexts/AuthContext'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { ProjectList } from '@/components/projects/ProjectList'
import { CreateProjectDialog } from '@/components/projects/CreateProjectDialog'
import { getProjects } from '@/api/projects'
import type { Project } from '@/types/project'

export function DashboardPage() {
  const { user } = useAuth()
  const [dialogOpen, setDialogOpen] = useState(false)
  const { data: projects, error, isLoading, mutate } = useSWR<Project[]>(
    '/projects',
    getProjects
  )

  return (
    <div className="space-y-8">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
        <div className="space-y-2">
          <h1 className="text-3xl font-semibold tracking-tight sm:text-4xl">
            Proyectos
          </h1>
          <p className="max-w-xl text-base font-medium text-muted-foreground sm:text-lg">
            Hola, {user?.full_name ?? user?.email}. Genera notas clínicas a
            partir de tus fuentes.
          </p>
        </div>
        <Button onClick={() => setDialogOpen(true)}>Nuevo proyecto</Button>
      </div>

      {error && (
        <Alert variant="destructive">
          <AlertDescription>
            No se pudieron cargar los proyectos. Intenta de nuevo.
          </AlertDescription>
        </Alert>
      )}

      <ProjectList projects={projects ?? []} isLoading={isLoading} />

      <CreateProjectDialog
        open={dialogOpen}
        onOpenChange={setDialogOpen}
        onCreated={() => mutate()}
      />
    </div>
  )
}
