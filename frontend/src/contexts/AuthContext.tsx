import {
  createContext,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from 'react'
import * as authApi from '@/api/auth'
import type { LoginRequest, RegisterRequest, User } from '@/types/auth'

interface AuthContextValue {
  user: User | null
  isLoading: boolean
  isAuthenticated: boolean
  login: (data: LoginRequest) => Promise<void>
  register: (data: RegisterRequest) => Promise<void>
  logout: () => Promise<void>
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const [isLoading, setIsLoading] = useState(true)

  useEffect(() => {
    let active = true
    authApi
      .me()
      .then((u) => {
        if (active) setUser(u)
      })
      .catch(() => {
        if (active) setUser(null)
      })
      .finally(() => {
        if (active) setIsLoading(false)
      })
    return () => {
      active = false
    }
  }, [])

  async function login(data: LoginRequest) {
    await authApi.login(data)
    const u = await authApi.me()
    setUser(u)
  }

  async function register(data: RegisterRequest) {
    await authApi.register(data)
    await login({ email: data.email, password: data.password })
  }

  async function logout() {
    await authApi.logout().catch(() => undefined)
    setUser(null)
  }

  const value = useMemo<AuthContextValue>(
    () => ({
      user,
      isLoading,
      isAuthenticated: user !== null,
      login,
      register,
      logout,
    }),
    [user, isLoading]
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext)
  if (ctx === undefined) {
    throw new Error('useAuth must be used within an AuthProvider')
  }
  return ctx
}
