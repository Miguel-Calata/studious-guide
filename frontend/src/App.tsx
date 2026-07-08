import { BrowserRouter } from 'react-router-dom'
import { Toaster } from 'sonner'
import { AppRouter } from '@/routes/AppRouter'
import { AuthProvider } from '@/contexts/AuthContext'
import { ApiProvider } from '@/hooks/useApi'

export default function App() {
  return (
    <BrowserRouter>
      <ApiProvider>
        <AuthProvider>
          <AppRouter />
        </AuthProvider>
      </ApiProvider>
      <Toaster richColors position="top-right" />
    </BrowserRouter>
  )
}
