import { toast } from 'sonner'
import { ApiError } from '@/api/client'

function extractMessage(err: unknown): string {
  if (err instanceof ApiError) {
    const d = err.detail
    if (typeof d === 'string') return d
    if (d && typeof d === 'object' && 'detail' in d) {
      const nested = (d as { detail?: unknown }).detail
      if (typeof nested === 'string') return nested
      if (Array.isArray(nested)) {
        return nested
          .map((n) => (n && typeof n === 'object' ? String((n as { msg?: string }).msg ?? '') : String(n)))
          .filter(Boolean)
          .join('; ')
      }
    }
    return err.message
  }
  if (err instanceof Error) return err.message
  return 'Ocurrió un error inesperado'
}

export function notifyError(err: unknown, fallback?: string): void {
  toast.error(extractMessage(err) || fallback || 'Ocurrió un error')
}

export function notifySuccess(message: string): void {
  toast.success(message)
}
