import { Link } from 'react-router-dom'

import { BrandNav } from './BrandNav'

export function PublicHeader({ className }: { className?: string }) {
  return <BrandNav mode="public" className={className} />
}

export function AuthShell({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex min-h-screen flex-col bg-background">
      <BrandNav mode="public" />
      <main className="mx-auto flex w-full max-w-md flex-1 flex-col justify-center px-4 pb-16 pt-2 sm:px-6">
        {children}
        <p className="mt-6 text-center text-sm text-muted-foreground">
          <Link
            to="/"
            className="font-medium text-foreground underline-offset-4 hover:underline"
          >
            ← Volver al inicio
          </Link>
        </p>
      </main>
    </div>
  )
}
