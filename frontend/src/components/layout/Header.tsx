import { Link } from 'react-router-dom'
import { useAuth } from '@/contexts/AuthContext'
import { Button } from '@/components/ui/button'
import { LogOut } from 'lucide-react'

export function Header() {
  const { user, logout } = useAuth()

  return (
    <header className="border-b bg-background">
      <div className="container flex h-14 items-center justify-between">
        <div className="flex items-center gap-6">
          <Link to="/" className="font-semibold">
            SAM Platform
          </Link>
          <Link
            to="/compendiums"
            className="text-sm text-muted-foreground hover:text-foreground transition-colors"
          >
            Compendios públicos
          </Link>
        </div>
        {user && (
          <div className="flex items-center gap-4">
            <span className="text-sm text-muted-foreground">
              {user.full_name ?? user.email}
            </span>
            <Button variant="ghost" size="sm" onClick={() => logout()}>
              <LogOut className="mr-2 h-4 w-4" />
              Salir
            </Button>
          </div>
        )}
      </div>
    </header>
  )
}
