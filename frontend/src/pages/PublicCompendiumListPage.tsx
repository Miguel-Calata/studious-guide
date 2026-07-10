import { Link } from 'react-router-dom'
import useSWR from 'swr'
import { BookOpen } from 'lucide-react'

import { Skeleton } from '@/components/ui/skeleton'
import { listPublicCompendiums } from '@/api/public'
import { coverForSlug } from '@/lib/brand'
import type { PublicCompendiumListItem } from '@/types/public'

export function PublicCompendiumListPage() {
  const { data, error, isLoading } = useSWR(
    '/public/compendiums',
    listPublicCompendiums,
    { revalidateOnFocus: false }
  )

  return (
    <div className="space-y-8">
      <div className="space-y-2">
        <h1 className="text-3xl font-semibold tracking-tight sm:text-4xl">
          Notas
        </h1>
        <p className="max-w-2xl text-base font-medium text-muted-foreground sm:text-lg">
          Compendios clínicos generados a partir de guías y artículos, listos
          para consultar.
        </p>
      </div>

      {isLoading && (
        <div className="grid gap-8 sm:grid-cols-2 lg:grid-cols-3">
          {Array.from({ length: 3 }).map((_, i) => (
            <div
              key={i}
              className="overflow-hidden rounded-2xl border border-black/10 shadow-card"
            >
              <Skeleton className="h-60 w-full rounded-none" />
              <div className="space-y-3 p-6">
                <Skeleton className="h-7 w-3/4" />
                <Skeleton className="h-12 w-full" />
                <Skeleton className="h-5 w-24" />
              </div>
            </div>
          ))}
        </div>
      )}

      {error && (
        <p className="text-destructive" role="alert">
          No se pudieron cargar las notas.
        </p>
      )}

      {data && data.length === 0 && (
        <div className="flex flex-col items-center justify-center rounded-2xl border border-dashed border-black/15 py-16 text-center">
          <BookOpen className="mb-3 h-10 w-10 text-muted-foreground" />
          <p className="font-medium">Aún no hay notas publicadas</p>
          <p className="mt-1 text-sm text-muted-foreground">
            Cuando se publique un compendio, aparecerá aquí.
          </p>
        </div>
      )}

      {data && data.length > 0 && (
        <ul className="grid gap-8 sm:grid-cols-2 lg:grid-cols-3">
          {data.map((item) => (
            <li key={item.slug}>
              <NoteCard item={item} />
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}

function NoteCard({ item }: { item: PublicCompendiumListItem }) {
  const cover = coverForSlug(item.slug)

  return (
    <Link
      to={`/compendiums/${item.slug}`}
      className="group block h-full overflow-hidden rounded-2xl border border-black/10 bg-card shadow-card transition-shadow hover:shadow-md"
    >
      <div className="relative h-60 w-full overflow-hidden bg-muted">
        <img
          src={cover}
          alt=""
          className="absolute inset-0 size-full object-cover transition-transform duration-300 group-hover:scale-[1.02]"
        />
      </div>
      <div className="flex flex-col gap-8 p-6">
        <div className="space-y-2">
          <h2 className="text-xl font-semibold tracking-tight text-foreground sm:text-2xl">
            {item.name}
          </h2>
          {item.description ? (
            <p className="line-clamp-3 text-base font-medium leading-snug text-foreground/55 sm:text-lg">
              {item.description}
            </p>
          ) : (
            <p className="text-base font-medium text-foreground/40 sm:text-lg">
              {item.section_count} secciones
            </p>
          )}
        </div>
        <span className="text-base font-medium text-foreground transition-opacity group-hover:opacity-70 sm:text-lg">
          Abrir nota →
        </span>
      </div>
    </Link>
  )
}
