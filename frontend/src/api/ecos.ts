import { api, ApiError } from './client'
import type {
  EcosMap,
  EcosMapUpdateRequest,
  EcosMapUpdateResponse,
} from '@/types/ecos'

/** Mapa aprobado activo. Devuelve null si no existe (404). */
export async function getActiveEcoMap(
  pathologyKey: string
): Promise<EcosMap | null> {
  try {
    return await api.get<EcosMap>(
      `/pathologies/${pathologyKey}/ecos-map`
    )
  } catch (err) {
    if (err instanceof ApiError && err.status === 404) return null
    throw err
  }
}

/** Borrador pendiente más reciente. Devuelve null si no existe (404). */
export async function getPendingDraft(
  pathologyKey: string
): Promise<EcosMap | null> {
  try {
    return await api.get<EcosMap>(
      `/pathologies/${pathologyKey}/ecos-map/pending-draft`
    )
  } catch (err) {
    if (err instanceof ApiError && err.status === 404) return null
    throw err
  }
}

/** Historial completo de versiones del ecos map. */
export async function listEcoMaps(
  pathologyKey: string
): Promise<EcosMap[]> {
  return api.get<EcosMap[]>(`/pathologies/${pathologyKey}/ecos-maps`)
}

/** Genera un nuevo borrador vía LLM. */
export async function proposeEcoMap(
  pathologyKey: string
): Promise<EcosMap> {
  return api.post<EcosMap>(
    `/pathologies/${pathologyKey}/ecos-map:propose`
  )
}

/** Edita un borrador (draft-only). 409 si no es editable. */
export async function updateEcoMap(
  id: string,
  body: EcosMapUpdateRequest
): Promise<EcosMapUpdateResponse> {
  return api.put<EcosMapUpdateResponse>(`/ecos-maps/${id}`, body)
}

/** Aprueba un borrador. */
export async function approveEcoMap(id: string): Promise<EcosMap> {
  return api.post<EcosMap>(`/ecos-maps/${id}/approve`)
}
