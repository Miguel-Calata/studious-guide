import { Loader2 } from 'lucide-react'

import { Badge } from '@/components/ui/badge'
import {
  sectionStatusLabel,
  sectionStatusVariant,
  dosificationLabel,
} from '@/lib/pipeline'
import type { CompendiumSection } from '@/types/compendium'

export function SectionList({
  sections,
  onSelect,
}: {
  sections: CompendiumSection[]
  onSelect: (section: CompendiumSection) => void
}) {
  if (sections.length === 0) return null

  const sorted = [...sections].sort(
    (a, b) => a.section_number - b.section_number
  )

  return (
    <ul className="divide-y divide-border overflow-hidden rounded-xl border border-border">
      {sorted.map((section) => (
        <li key={section.id}>
          <button
            type="button"
            onClick={() => onSelect(section)}
            className="flex w-full items-center justify-between gap-3 px-3 py-2.5 text-left transition-colors hover:bg-muted/60"
          >
            <span className="flex min-w-0 items-center gap-2">
              {section.status === 'processing' && (
                <Loader2
                  className="size-3.5 shrink-0 animate-spin text-muted-foreground"
                  aria-hidden
                />
              )}
              <span className="text-sm font-medium tabular-nums text-muted-foreground">
                {section.section_number}.
              </span>
              <span className="truncate text-sm">{section.section_name}</span>
            </span>
            <span className="flex shrink-0 items-center gap-2">
              {section.model_used && (
                <span className="hidden text-xs text-muted-foreground sm:inline">
                  {section.model_used} · {dosificationLabel(section.dosification)}
                </span>
              )}
              <Badge variant={sectionStatusVariant(section.status)}>
                {sectionStatusLabel(section.status)}
              </Badge>
            </span>
          </button>
          {section.status === 'failed' && section.error_message && (
            <p className="border-t border-destructive/10 bg-destructive/5 px-3 py-2 text-xs text-destructive line-clamp-2">
              {section.error_message}
            </p>
          )}
        </li>
      ))}
    </ul>
  )
}
