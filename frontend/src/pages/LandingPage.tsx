import { Link } from 'react-router-dom'

import { PublicHeader } from '@/components/layout/PublicHeader'
import { Button } from '@/components/ui/button'
import { HERO_IMAGES } from '@/lib/brand'

export function LandingPage() {
  return (
    <div className="flex min-h-screen flex-col bg-background">
      <PublicHeader />

      <main className="flex flex-1 flex-col">
        <section className="flex flex-col items-center px-6 pb-12 pt-10 sm:px-16 sm:pb-20 sm:pt-16">
          <div className="mx-auto flex w-full max-w-5xl flex-col items-center gap-6 text-center sm:gap-8">
            <h1 className="text-4xl font-bold leading-[1.1] tracking-tightest text-foreground sm:text-5xl md:text-6xl md:tracking-[-0.02em]">
              20 guías clínicas una nota. Sin perder un dato.
            </h1>
            <p className="max-w-3xl text-lg font-medium leading-snug text-foreground/55 sm:text-xl md:text-2xl">
              SAM convierte guías de práctica clínica, artículos y más en
              compendios sin perder un solo dato, un solo umbral ni una sola
              cita.
            </p>
            <div className="flex w-full flex-col items-stretch justify-center gap-3 sm:w-auto sm:flex-row sm:items-center sm:gap-4">
              <Button
                asChild
                size="lg"
                className="h-12 rounded-xl px-6 text-base sm:text-lg"
              >
                <Link to="/register">Crear cuenta</Link>
              </Button>
              <Button
                asChild
                variant="outline"
                size="lg"
                className="h-12 rounded-xl border-2 border-black/15 px-6 text-base sm:text-lg"
              >
                <Link to="/compendiums">Ver notas</Link>
              </Button>
            </div>
          </div>
        </section>

        <section
          className="w-full overflow-hidden px-2 pb-16 pt-2 sm:px-2 sm:pb-20"
          aria-hidden
        >
          <div className="mx-auto flex max-w-[1280px] gap-3 overflow-x-auto px-2 pb-2 sm:justify-center sm:gap-4 sm:overflow-visible sm:px-2">
            {HERO_IMAGES.map((src) => (
              <div
                key={src}
                className="relative h-[280px] w-[200px] shrink-0 overflow-hidden rounded-2xl sm:h-[360px] sm:w-[260px] md:h-[410px] md:w-[305px]"
              >
                <img
                  src={src}
                  alt=""
                  className="absolute inset-0 size-full object-cover"
                />
              </div>
            ))}
          </div>
        </section>
      </main>
    </div>
  )
}
