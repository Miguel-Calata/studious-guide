export const BRAND_LOGO = '/brand/logo.png'

export const HERO_IMAGES = [
  '/brand/hero-1.jpg',
  '/brand/hero-2.jpg',
  '/brand/hero-3.jpg',
  '/brand/hero-4.jpg',
] as const

export const NOTE_COVERS = [
  '/brand/note-1.jpg',
  '/brand/note-2.jpg',
  '/brand/note-3.jpg',
  '/brand/hero-1.jpg',
  '/brand/hero-2.jpg',
  '/brand/hero-3.jpg',
  '/brand/hero-4.jpg',
] as const

/** Stable cover from a slug when the API has no cover_url yet. */
export function coverForSlug(slug: string): string {
  let hash = 0
  for (let i = 0; i < slug.length; i += 1) {
    hash = (hash * 31 + slug.charCodeAt(i)) >>> 0
  }
  return NOTE_COVERS[hash % NOTE_COVERS.length]
}
