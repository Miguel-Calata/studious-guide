import { useState } from 'react'
import useSWR from 'swr'

import { useAuth } from '@/contexts/AuthContext'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
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
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Proyectos</h1>
          <p className="text-muted-foreground">
            Bienvenido, {user?.full_name ?? user?.email}
          </p>
        </div>
        <Button onClick={() => setDialogOpen(true)}>Nuevo proyecto</Button>
      </div>

      {error && (
        <Card>
          <CardContent className="pt-6 text-sm text-destructive">
            No se pudieron cargar los proyectos. Intenta de nuevo.
          </CardContent>
        </Card>
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
