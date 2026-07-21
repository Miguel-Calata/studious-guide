import type {
  PublicCompendiumListItem,
  PublicCompendiumDetail,
  PublicSectionResponse,
  SourceDocumentPublic,
} from '@/types/public'

async function publicFetch<T>(path: string): Promise<T> {
  const res = await fetch(path, { credentials: 'include' })
  if (!res.ok) {
    throw new Error(`Error ${res.status}`)
  }
  return (await res.json()) as T
}

export function listPublicCompendiums(): Promise<PublicCompendiumListItem[]> {
  return publicFetch('/public/compendiums')
}

export function getPublicCompendium(
  slug: string
): Promise<PublicCompendiumDetail> {
  return publicFetch(`/public/compendiums/${encodeURIComponent(slug)}`)
}

export function getPublicSection(
  slug: string,
  sectionNumber: number
): Promise<PublicSectionResponse> {
  return publicFetch(
    `/public/compendiums/${encodeURIComponent(slug)}/sections/${sectionNumber}`
  )
}

export function getPublicDownloadUrl(slug: string): string {
  return `/public/compendiums/${encodeURIComponent(slug)}/download`
}

export function listCompendiumSources(
  slug: string
): Promise<SourceDocumentPublic[]> {
  return publicFetch(
    `/public/compendiums/${encodeURIComponent(slug)}/sources`
  )
}

export function getSourceDownloadUrl(slug: string, documentId: string): string {
  return `/public/compendiums/${encodeURIComponent(slug)}/sources/${documentId}`
}
