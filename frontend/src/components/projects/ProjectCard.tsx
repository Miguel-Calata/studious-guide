import { useNavigate } from 'react-router-dom'
import { FileText } from 'lucide-react'

import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { statusLabel, statusVariant } from '@/lib/projects'
import type { Project } from '@/types/project'

export function ProjectCard({ project }: { project: Project }) {
  const navigate = useNavigate()

  return (
    <Card
      className="cursor-pointer transition-colors hover:bg-accent/40"
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
      <CardHeader className="flex flex-row items-start justify-between space-y-0">
        <CardTitle className="text-base">{project.name}</CardTitle>
        <Badge variant={statusVariant(project.status)}>
          {statusLabel(project.status)}
        </Badge>
      </CardHeader>
      <CardContent className="space-y-2">
        <p className="line-clamp-2 text-sm text-muted-foreground">
          {project.description || 'Sin descripción'}
        </p>
        <p className="flex items-center gap-1 text-xs text-muted-foreground">
          <FileText className="h-3.5 w-3.5" />
          Creado el {new Date(project.created_at).toLocaleDateString('es')}
        </p>
      </CardContent>
    </Card>
  )
}
