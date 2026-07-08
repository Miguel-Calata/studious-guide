import { useAuth } from '@/contexts/AuthContext'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'

export function DashboardPage() {
  const { user } = useAuth()

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Dashboard</h1>
        <p className="text-muted-foreground">
          Bienvenido, {user?.full_name ?? user?.email}
        </p>
      </div>
      <Card>
        <CardHeader>
          <CardTitle>Información de la cuenta</CardTitle>
        </CardHeader>
        <CardContent className="space-y-2 text-sm">
          <p>
            <span className="text-muted-foreground">Email:</span> {user?.email}
          </p>
          <p>
            <span className="text-muted-foreground">Rol:</span> {user?.role}
          </p>
          <p>
            <span className="text-muted-foreground">ID:</span> {user?.id}
          </p>
        </CardContent>
      </Card>
    </div>
  )
}
