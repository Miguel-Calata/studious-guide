import { Outlet } from 'react-router-dom'

import { BrandNav } from './BrandNav'

export function AppShell() {
  return (
    <div className="flex min-h-screen flex-col bg-background">
      <BrandNav mode="app" />
      <main className="mx-auto w-full max-w-6xl flex-1 px-4 pb-16 pt-2 sm:px-8">
        <Outlet />
      </main>
    </div>
  )
}
