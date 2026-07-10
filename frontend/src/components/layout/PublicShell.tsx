import { Outlet } from 'react-router-dom'

import { BrandNav } from './BrandNav'

export function PublicShell() {
  return (
    <div className="flex min-h-screen flex-col bg-background">
      <BrandNav mode="public" />
      <main className="mx-auto w-full max-w-6xl flex-1 px-4 pb-20 pt-2 sm:px-8">
        <Outlet />
      </main>
    </div>
  )
}
