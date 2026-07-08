import { SWRConfig } from 'swr'
import { api } from '@/api/client'

export const swrConfig = {
  fetcher: (path: string) => api.get(path),
  revalidateOnFocus: false,
}

export function ApiProvider({ children }: { children: React.ReactNode }) {
  return <SWRConfig value={swrConfig}>{children}</SWRConfig>
}
