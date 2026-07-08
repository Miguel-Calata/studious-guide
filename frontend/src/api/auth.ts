import { api } from './client'
import type { LoginRequest, RegisterRequest, User } from '@/types/auth'

export function login(data: LoginRequest): Promise<unknown> {
  return api.post('/auth/login', data)
}

export function register(data: RegisterRequest): Promise<unknown> {
  return api.post('/auth/register', data)
}

export function logout(): Promise<unknown> {
  return api.post('/auth/logout')
}

export function me(): Promise<User> {
  return api.get<User>('/auth/me')
}
