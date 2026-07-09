import { Link, Outlet } from 'react-router-dom'
import { useAuth } from '@/contexts/AuthContext'

export function PublicShell() {
  const { user } = useAuth()

  return (
    <div className="min-h-screen flex flex-col">
      <header className="border-b bg-background">
        <div className="container flex h-14 items-center justify-between">
          <div className="flex items-center gap-6">
            <Link to="/compendiums" className="font-semibold">
              SAM Platform
            </Link>
            <Link
              to="/compendiums"
              className="text-sm text-muted-foreground hover:text-foreground transition-colors"
            >
              Compendios
            </Link>
          </div>
          <div>
            {user ? (
              <Link
                to="/"
                className="text-sm text-muted-foreground hover:text-foreground transition-colors"
              >
                Panel
              </Link>
            ) : (
              <Link
                to="/login"
                className="text-sm text-muted-foreground hover:text-foreground transition-colors"
              >
                Entrar
              </Link>
            )}
          </div>
        </div>
      </header>
      <main className="container flex-1 py-6">
        <Outlet />
      </main>
    </div>
  )
}
