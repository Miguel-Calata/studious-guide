import { Link } from 'react-router-dom'
import { LogOut } from 'lucide-react'

import { useAuth } from '@/contexts/AuthContext'
import { Button } from '@/components/ui/button'
import { BRAND_LOGO } from '@/lib/brand'
import { cn } from '@/lib/utils'

export function BrandNav({
  mode = 'public',
  className,
}: {
  mode?: 'public' | 'app'
  className?: string
}) {
  const { user, isLoading, logout } = useAuth()

  const logoTo = mode === 'app' ? '/app' : '/'
  const logoLabel = mode === 'app' ? 'SAM — panel' : 'SAM — inicio'

  return (
    <header
      className={cn(
        'flex w-full items-center justify-center px-4 py-6 sm:px-6',
        className
      )}
    >
      <div className="flex w-full max-w-xl items-center justify-between rounded-2xl border border-black bg-black py-2 pl-4 pr-2 backdrop-blur-[35px] sm:max-w-2xl">
        <Link
          to={logoTo}
          className="flex items-center gap-2 text-white"
          aria-label={logoLabel}
        >
          <img
            src={BRAND_LOGO}
            alt=""
            className="size-7 rounded-md object-cover sm:size-8"
          />
          <span className="text-lg font-semibold tracking-tight sm:text-xl">
            SAM
          </span>
        </Link>

        <nav className="flex items-center gap-2 sm:gap-4">
          {mode === 'public' && (
            <>
              {!isLoading &&
                (user ? (
                  <Link
                    to="/app"
                    className="hidden text-sm font-medium text-white/90 transition-opacity hover:opacity-80 sm:inline sm:text-base"
                  >
                    Panel
                  </Link>
                ) : (
                  <Link
                    to="/login"
                    className="hidden text-sm font-medium text-white/90 transition-opacity hover:opacity-80 sm:inline sm:text-base"
                  >
                    Iniciar sesión
                  </Link>
                ))}
              <Button
                asChild
                size="sm"
                className="rounded-lg bg-white px-3 text-black hover:bg-white/90"
              >
                <Link to="/compendiums">Ver notas</Link>
              </Button>
            </>
          )}

          {mode === 'app' && (
            <>
              <Link
                to="/compendiums"
                className="text-sm font-medium text-white/90 transition-opacity hover:opacity-80 sm:text-base"
              >
                Notas
              </Link>
              {user && (
                <span className="hidden max-w-[10rem] truncate text-sm text-white/70 sm:inline">
                  {user.full_name ?? user.email}
                </span>
              )}
              <Button
                size="sm"
                className="rounded-lg bg-white px-3 text-black hover:bg-white/90"
                onClick={() => logout()}
              >
                <LogOut className="h-4 w-4" />
                <span className="hidden sm:inline">Salir</span>
              </Button>
            </>
          )}
        </nav>
      </div>
    </header>
  )
}
