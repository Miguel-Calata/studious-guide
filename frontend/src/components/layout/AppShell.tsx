import { Outlet } from 'react-router-dom'
import { Header } from './Header'

export function AppShell() {
  return (
    <div className="min-h-screen flex flex-col">
      <Header />
      <main className="container flex-1 py-6">
        <Outlet />
      </main>
    </div>
  )
}
