import { FolderOpen } from 'lucide-react'

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
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {Array.from({ length: 3 }).map((_, i) => (
          <div
            key={i}
            className="h-32 animate-pulse rounded-xl border bg-primary/5"
          />
        ))}
      </div>
    )
  }

  if (projects.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center rounded-xl border border-dashed py-16 text-center">
        <FolderOpen className="mb-3 h-10 w-10 text-muted-foreground" />
        <p className="font-medium">No tienes proyectos todavía</p>
        <p className="text-sm text-muted-foreground">
          Crea tu primer proyecto para empezar a generar compendios.
        </p>
      </div>
    )
  }

  return (
    <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
      {projects.map((project) => (
        <ProjectCard key={project.id} project={project} />
      ))}
    </div>
  )
}
