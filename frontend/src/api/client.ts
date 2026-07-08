const API_BASE_URL =
  (import.meta.env.VITE_API_BASE_URL as string | undefined) ?? '/api/v1'

export class ApiError extends Error {
  status: number
  detail: unknown

  constructor(status: number, message: string, detail?: unknown) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.detail = detail
  }
}

let isRefreshing = false
let pendingQueue: Array<{
  resolve: (value: unknown) => void
  reject: (reason?: unknown) => void
}> = []

async function refreshAccessToken(): Promise<boolean> {
  const res = await fetch(`${API_BASE_URL}/auth/refresh`, {
    method: 'POST',
    credentials: 'include',
    headers: { 'Content-Type': 'application/json' },
  })
  return res.ok
}

function subscribeTokenRefresh() {
  return new Promise<boolean>((resolve, reject) => {
    pendingQueue.push({
      resolve: (v) => resolve(Boolean(v)),
      reject,
    })
  })
}

function onRefreshed(success: boolean) {
  pendingQueue.forEach((p) => (success ? p.resolve(true) : p.reject(false)))
  pendingQueue = []
}

export async function request<T>(
  method: string,
  path: string,
  body?: unknown,
  retry = true
): Promise<T> {
  const url = path.startsWith('http') ? path : `${API_BASE_URL}${path}`
  const res = await fetch(url, {
    method,
    credentials: 'include',
    headers: { 'Content-Type': 'application/json' },
    body: body !== undefined ? JSON.stringify(body) : undefined,
  })

  if (res.status === 401 && retry && !path.includes('/auth/')) {
    if (!isRefreshing) {
      isRefreshing = true
      try {
        const success = await refreshAccessToken()
        isRefreshing = false
        onRefreshed(success)
        if (!success) {
          throw new ApiError(401, 'Sesión expirada')
        }
      } catch {
        isRefreshing = false
        onRefreshed(false)
        throw new ApiError(401, 'Sesión expirada')
      }
    } else {
      await subscribeTokenRefresh()
    }
    return request<T>(method, path, body, false)
  }

  if (!res.ok) {
    let detail: unknown
    try {
      detail = await res.json()
    } catch {
      detail = null
    }
    const message =
      (detail as { detail?: string })?.detail ?? `Error ${res.status}`
    throw new ApiError(res.status, message, detail)
  }

  if (res.status === 204) {
    return undefined as T
  }

  return (await res.json()) as T
}

export async function uploadFile<T>(
  path: string,
  formData: FormData
): Promise<T> {
  const url = path.startsWith('http') ? path : `${API_BASE_URL}${path}`
  const res = await fetch(url, {
    method: 'POST',
    credentials: 'include',
    body: formData,
  })

  if (res.status === 401) {
    throw new ApiError(401, 'Sesión expirada')
  }

  if (!res.ok) {
    let detail: unknown
    try {
      detail = await res.json()
    } catch {
      detail = null
    }
    const message =
      (detail as { detail?: string })?.detail ?? `Error ${res.status}`
    throw new ApiError(res.status, message, detail)
  }

  if (res.status === 204) {
    return undefined as T
  }

  return (await res.json()) as T
}

export const api = {
  get: <T>(path: string) => request<T>('GET', path),
  post: <T>(path: string, body?: unknown) => request<T>('POST', path, body),
  put: <T>(path: string, body?: unknown) => request<T>('PUT', path, body),
  delete: <T>(path: string) => request<T>('DELETE', path),
}

export { API_BASE_URL }
