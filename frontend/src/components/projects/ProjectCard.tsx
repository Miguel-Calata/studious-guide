import { useNavigate } from 'react-router-dom'
import { ArrowUpRight } from 'lucide-react'

import { Badge } from '@/components/ui/badge'
import { statusLabel, statusVariant } from '@/lib/projects'
import { coverForSlug } from '@/lib/brand'
import type { Project } from '@/types/project'

export function ProjectCard({ project }: { project: Project }) {
  const navigate = useNavigate()
  const cover = coverForSlug(project.slug || project.id)
  const monogram = (project.name.trim().charAt(0) || 'S').toUpperCase()

  return (
    <article
      className="group cursor-pointer overflow-hidden rounded-2xl border border-black/10 bg-card shadow-card transition-shadow hover:shadow-md"
      onClick={() => navigate(`/projects/${project.id}`)}
      role="button"
      tabIndex={0}
      onKeyDown={(e) => {
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault()
          navigate(`/projects/${project.id}`)
        }
      }}
    >
      <div className="relative h-24 w-full overflow-hidden bg-muted">
        <img
          src={cover}
          alt=""
          className="absolute inset-0 size-full object-cover opacity-90 transition-transform duration-300 group-hover:scale-[1.03]"
        />
        <div className="absolute inset-0 bg-gradient-to-t from-black/40 to-transparent" />
        <span className="absolute bottom-3 left-4 flex size-9 items-center justify-center rounded-lg bg-white/95 text-sm font-semibold tracking-tight text-foreground shadow-sm">
          {monogram}
        </span>
      </div>
      <div className="space-y-3 p-5">
        <div className="flex items-start justify-between gap-3">
          <h2 className="text-lg font-semibold tracking-tight text-foreground">
            {project.name}
          </h2>
          <Badge variant={statusVariant(project.status)} className="shrink-0">
            {statusLabel(project.status)}
          </Badge>
        </div>
        <p className="line-clamp-2 text-sm font-medium leading-snug text-foreground/55">
          {project.description || 'Sin descripción'}
        </p>
        <div className="flex items-center justify-between pt-1 text-xs text-muted-foreground">
          <span>
            Creado el {new Date(project.created_at).toLocaleDateString('es')}
          </span>
          <span className="inline-flex items-center gap-0.5 font-medium text-foreground transition-opacity group-hover:opacity-80">
            Abrir
            <ArrowUpRight className="h-3.5 w-3.5" />
          </span>
        </div>
      </div>
    </article>
  )
}
