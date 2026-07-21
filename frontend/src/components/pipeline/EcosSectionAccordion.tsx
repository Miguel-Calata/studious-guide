import { Textarea } from '@/components/ui/textarea'
import { Badge } from '@/components/ui/badge'
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from '@/components/ui/accordion'
import { ECOS_SECTION_NAMES, TOTAL_ECOS_SECTIONS } from '@/types/ecos'

interface EcosSectionAccordionProps {
  /** Texto multilínea por sección (1..11 como string keys). */
  textareas: Record<string, string>
  /** Callback al cambiar el texto de una sección. */
  onChange: (sectionKey: string, value: string) => void
  /** Secciones con warnings de cobertura (se resaltan). */
  warningSections?: Set<number>
  /** Si es true, los textareas están deshabilitados (solo lectura). */
  readOnly?: boolean
  /** Secciones que deben estar abiertas por defecto. */
  defaultOpen?: string[]
}

export function EcosSectionAccordion({
  textareas,
  onChange,
  warningSections,
  readOnly = false,
  defaultOpen,
}: EcosSectionAccordionProps) {
  return (
    <Accordion
      type="multiple"
      defaultValue={defaultOpen}
      className="w-full"
    >
      {Array.from({ length: TOTAL_ECOS_SECTIONS }, (_, i) => i + 1).map(
        (n) => {
          const key = String(n)
          const hasWarning = warningSections?.has(n)
          const value = textareas[key] ?? ''
          const lineCount = value
            .split('\n')
            .filter((l) => l.trim()).length

          return (
            <AccordionItem key={key} value={key}>
              <AccordionTrigger className="text-sm py-2">
                <span className="flex items-center gap-2">
                  <span className="font-medium text-muted-foreground">
                    {n}.
                  </span>
                  <span>{ECOS_SECTION_NAMES[n]}</span>
                  {lineCount > 0 && (
                    <span className="text-xs text-muted-foreground">
                      ({lineCount} eco{lineCount !== 1 ? 's' : ''})
                    </span>
                  )}
                  {hasWarning && (
                    <Badge variant="warning" className="ml-2 text-[10px]">
                      cobertura incompleta
                    </Badge>
                  )}
                </span>
              </AccordionTrigger>
              <AccordionContent>
                {n === 1 ? (
                  <p className="text-xs text-muted-foreground italic">
                    La sección 1 no tiene secciones anteriores que
                    referenciar. Los ecos siempre están vacíos.
                  </p>
                ) : (
                  <Textarea
                    value={value}
                    onChange={(e) => onChange(key, e.target.value)}
                    readOnly={readOnly}
                    disabled={readOnly}
                    placeholder="Un eco por línea, ej: Definición clínica de LRA (→ ver Sección 1)"
                    className="min-h-[80px] font-mono text-xs resize-y"
                    rows={Math.max(3, lineCount + 1)}
                  />
                )}
              </AccordionContent>
            </AccordionItem>
          )
        }
      )}
    </Accordion>
  )
}
