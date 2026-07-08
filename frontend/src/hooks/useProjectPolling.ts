import useSWR, { type KeyedMutator } from 'swr'
import { getProject } from '@/api/projects'
import type { Project } from '@/types/project'
import { isProjectBusy, POLL_INTERVAL_MS } from '@/lib/pipeline'

export function useProjectPolling(
  id: string | undefined,
  intervalMs: number = POLL_INTERVAL_MS
): {
  project: Project | undefined
  error: unknown
  isLoading: boolean
  mutate: KeyedMutator<Project>
} {
  const { data, error, isLoading, mutate } = useSWR<Project>(
    id ? `/projects/${id}` : null,
    () => getProject(id as string),
    {
      refreshInterval: (latest?: Project) =>
        id && latest && isProjectBusy(latest.status) ? intervalMs : 0,
      revalidateOnFocus: false,
    }
  )
  return { project: data, error, isLoading, mutate }
}
