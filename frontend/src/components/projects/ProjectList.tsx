import { FolderOpen } from 'lucide-react'

import { Skeleton } from '@/components/ui/skeleton'
import { ProjectCard } from './ProjectCard'
import type { Project } from '@/types/project'

export function ProjectList({
  projects,
  isLoading,
}: {
  projects: Project[]
  isLoading: boolean
}) {
  if (isLoading) {
    return (
      <div
        className="grid gap-6 sm:grid-cols-2 lg:grid-cols-3"
        aria-busy="true"
        aria-label="Cargando proyectos"
      >
        {Array.from({ length: 3 }).map((_, i) => (
          <div
            key={i}
            className="overflow-hidden rounded-2xl border border-black/10 shadow-card"
          >
            <Skeleton className="h-24 w-full rounded-none" />
            <div className="space-y-3 p-5">
              <div className="flex items-start justify-between gap-3">
                <Skeleton className="h-6 w-2/3" />
                <Skeleton className="h-5 w-16" />
              </div>
              <Skeleton className="h-10 w-full" />
              <Skeleton className="h-3 w-28" />
            </div>
          </div>
        ))}
      </div>
    )
  }

  if (projects.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center rounded-2xl border border-dashed border-black/15 py-16 text-center">
        <FolderOpen className="mb-3 h-10 w-10 text-muted-foreground" />
        <p className="font-medium">No tienes proyectos todavía</p>
        <p className="mt-1 text-sm text-muted-foreground">
          Crea tu primer proyecto para empezar a generar notas clínicas.
        </p>
      </div>
    )
  }

  return (
    <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
      {projects.map((project) => (
        <ProjectCard key={project.id} project={project} />
      ))}
    </div>
  )
}
