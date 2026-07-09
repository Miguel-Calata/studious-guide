import { api } from './client'
import { MODELS, type AiModel } from '@/config/models'

export type { AiModel }

export async function getModels(): Promise<AiModel[]> {
  try {
    const remote = await api.get<AiModel[]>('/ai/models')
    if (Array.isArray(remote) && remote.length > 0) return remote
  } catch {
    /* backend no disponible, usar fallback local */
  }
  return MODELS
}
