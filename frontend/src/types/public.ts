export interface PublicCompendiumListItem {
  slug: string
  name: string
  description: string | null
  section_count: number
  published_at: string | null
}

export interface PublicSectionSummary {
  section_number: number
  section_name: string
}

export interface PublicCompendiumDetail {
  slug: string
  name: string
  description: string | null
  section_count: number
  sections: PublicSectionSummary[]
  published_at: string | null
  public_url: string | null
}

export interface PublicSectionResponse {
  section_number: number
  section_name: string
  content: string
  dosification: string
}
