import { Link, useLocation, useNavigate } from 'react-router-dom'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { useState } from 'react'

import { useAuth } from '@/contexts/AuthContext'
import { loginSchema, type LoginFormValues } from '@/schemas/auth'
import { AuthShell } from '@/components/layout/PublicHeader'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from '@/components/ui/card'
import { BRAND_LOGO } from '@/lib/brand'

export function LoginPage() {
  const { login } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const [error, setError] = useState<string | null>(null)

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<LoginFormValues>({
    resolver: zodResolver(loginSchema),
  })

  async function onSubmit(values: LoginFormValues) {
    setError(null)
    try {
      await login(values)
      const from = (location.state as { from?: { pathname: string } })?.from
      navigate(from?.pathname ?? '/app')
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Error al iniciar sesión')
    }
  }

  return (
    <AuthShell>
      <Card className="w-full border-black/10 shadow-card">
        <CardHeader className="space-y-3">
          <div className="flex items-center gap-2">
            <img
              src={BRAND_LOGO}
              alt=""
              className="size-8 rounded-md object-cover"
            />
            <span className="text-lg font-semibold tracking-tight">SAM</span>
          </div>
          <CardTitle className="text-2xl tracking-tight">
            Iniciar sesión
          </CardTitle>
          <CardDescription className="text-base">
            Accede a tu cuenta
          </CardDescription>
        </CardHeader>
        <form onSubmit={handleSubmit(onSubmit)}>
          <CardContent className="space-y-4">
            {error && (
              <Alert variant="destructive">
                <AlertDescription role="alert">{error}</AlertDescription>
              </Alert>
            )}
            <div className="space-y-2">
              <Label htmlFor="email">Email</Label>
              <Input
                id="email"
                type="email"
                autoComplete="email"
                {...register('email')}
              />
              {errors.email && (
                <p className="text-sm text-destructive">
                  {errors.email.message}
                </p>
              )}
            </div>
            <div className="space-y-2">
              <Label htmlFor="password">Contraseña</Label>
              <Input
                id="password"
                type="password"
                autoComplete="current-password"
                {...register('password')}
              />
              {errors.password && (
                <p className="text-sm text-destructive">
                  {errors.password.message}
                </p>
              )}
            </div>
          </CardContent>
          <CardFooter className="flex flex-col gap-3">
            <Button type="submit" className="w-full" disabled={isSubmitting}>
              {isSubmitting ? 'Ingresando…' : 'Ingresar'}
            </Button>
            <p className="text-sm text-muted-foreground">
              ¿No tienes cuenta?{' '}
              <Link
                to="/register"
                className="font-medium text-foreground underline-offset-4 hover:underline"
              >
                Regístrate
              </Link>
            </p>
          </CardFooter>
        </form>
      </Card>
    </AuthShell>
  )
}
