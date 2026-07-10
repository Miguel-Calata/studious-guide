import { Navigate, Route, Routes } from 'react-router-dom'

import { AppShell } from '@/components/layout/AppShell'
import { PublicShell } from '@/components/layout/PublicShell'
import { ProtectedRoute } from './ProtectedRoute'
import { LandingPage } from '@/pages/LandingPage'
import { LoginPage } from '@/pages/LoginPage'
import { RegisterPage } from '@/pages/RegisterPage'
import { DashboardPage } from '@/pages/DashboardPage'
import { ProjectDetailPage } from '@/pages/ProjectDetailPage'
import { PublicCompendiumListPage } from '@/pages/PublicCompendiumListPage'
import { PublicCompendiumDetailPage } from '@/pages/PublicCompendiumDetailPage'

export function AppRouter() {
  return (
    <Routes>
      <Route path="/" element={<LandingPage />} />
      <Route path="/login" element={<LoginPage />} />
      <Route path="/register" element={<RegisterPage />} />

      <Route element={<PublicShell />}>
        <Route path="/compendiums" element={<PublicCompendiumListPage />} />
        <Route
          path="/compendiums/:slug"
          element={<PublicCompendiumDetailPage />}
        />
      </Route>

      <Route
        element={
          <ProtectedRoute>
            <AppShell />
          </ProtectedRoute>
        }
      >
        <Route path="/app" element={<DashboardPage />} />
        <Route path="/projects/:id" element={<ProjectDetailPage />} />
      </Route>

      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}
