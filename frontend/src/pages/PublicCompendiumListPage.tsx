import { Link } from 'react-router-dom'
import useSWR from 'swr'
import { BookOpen, Calendar, Layers } from 'lucide-react'

import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { listPublicCompendiums } from '@/api/public'
import type { PublicCompendiumListItem } from '@/types/public'

export function PublicCompendiumListPage() {
  const { data, error, isLoading } = useSWR(
    '/public/compendiums',
    listPublicCompendiums,
    { revalidateOnFocus: false }
  )

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">
          Compendios médicos
        </h1>
        <p className="text-muted-foreground mt-1">
          Compendios generados con IA a partir de guías clínicas y artículos científicos.
        </p>
      </div>

      {isLoading && (
        <p className="text-muted-foreground">Cargando compendios…</p>
      )}

      {error && (
        <p className="text-destructive">
          No se pudieron cargar los compendios.
        </p>
      )}

      {data && data.length === 0 && (
        <div className="text-center py-12">
          <BookOpen className="mx-auto h-12 w-12 text-muted-foreground/50" />
          <p className="mt-4 text-muted-foreground">
            Aún no hay compendios publicados.
          </p>
        </div>
      )}

      {data && data.length > 0 && (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {data.map((item) => (
            <CompendiumCard key={item.slug} item={item} />
          ))}
        </div>
      )}
    </div>
  )
}

function CompendiumCard({ item }: { item: PublicCompendiumListItem }) {
  return (
    <Link to={`/compendiums/${item.slug}`} className="block group">
      <Card className="transition-colors hover:border-primary/50">
        <CardHeader>
          <CardTitle className="text-base group-hover:text-primary transition-colors">
            {item.name}
          </CardTitle>
        </CardHeader>
        <CardContent>
          {item.description && (
            <p className="text-sm text-muted-foreground line-clamp-2 mb-3">
              {item.description}
            </p>
          )}
          <div className="flex items-center gap-4 text-xs text-muted-foreground">
            <span className="flex items-center gap-1">
              <Layers className="h-3 w-3" />
              {item.section_count} secciones
            </span>
            {item.published_at && (
              <span className="flex items-center gap-1">
                <Calendar className="h-3 w-3" />
                {new Date(item.published_at).toLocaleDateString('es-ES', {
                  year: 'numeric',
                  month: 'short',
                  day: 'numeric',
                })}
              </span>
            )}
          </div>
        </CardContent>
      </Card>
    </Link>
  )
}
