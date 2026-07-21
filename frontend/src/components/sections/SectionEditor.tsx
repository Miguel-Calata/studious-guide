import { lazy, Suspense, useEffect, useState } from 'react'
import { RefreshCw, Save } from 'lucide-react'

import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'
import { ModelSelect } from '@/components/ui/model-select'
import { updateSection, regenerateSection } from '@/api/compendiums'
import { notifyError, notifySuccess } from '@/lib/notify'
import { dosificationLabel } from '@/lib/pipeline'
import { readModelPref, writeModelPref } from '@/lib/modelPrefs'
import { DEFAULT_MODEL, DEFAULT_CLAUDE_MODEL } from '@/config/models'
import type { AiModel } from '@/api/ai'
import type { CompendiumSection, SectionStatus } from '@/types/compendium'

const REGENERABLE: SectionStatus[] = ['completed', 'failed', 'approved']

const MDEditor = lazy(() =>
  import('@uiw/react-md-editor').then((m) => ({ default: m.default }))
)

export function SectionEditor({
  section,
  open,
  onOpenChange,
  onSaved,
  models,
}: {
  section: CompendiumSection
  open: boolean
  onOpenChange: (open: boolean) => void
  onSaved: (section: CompendiumSection) => void
  models?: AiModel[]
}) {
  const [content, setContent] = useState(section.content)
  const [saving, setSaving] = useState(false)
  const [regenerating, setRegenerating] = useState(false)
  const [geminiModel, setGeminiModel] = useState<string>(() =>
    readModelPref('gemini', DEFAULT_MODEL)
  )
  const [claudeModel, setClaudeModel] = useState<string>(() =>
    readModelPref('claude', DEFAULT_CLAUDE_MODEL)
  )

  useEffect(() => {
    if (open) setContent(section.content)
  }, [open, section.content])

  useEffect(() => {
    return () => {
      document.body.style.overflow = ''
    }
  }, [])

  const canRegenerate = REGENERABLE.includes(section.status)

  async function handleSave() {
    setSaving(true)
    try {
      const updated = await updateSection(section.id, { content })
      notifySuccess(`Sección ${section.section_number} guardada.`)
      onSaved(updated)
      onOpenChange(false)
    } catch (err) {
      notifyError(err, 'No se pudo guardar la sección.')
    } finally {
      setSaving(false)
    }
  }

  async function handleRegenerate() {
    setRegenerating(true)
    try {
      const updated = await regenerateSection(section.id, {
        gemini_model: geminiModel,
        claude_model: claudeModel,
      })
      notifySuccess(`Sección ${section.section_number} en regeneración.`)
      onSaved(updated)
      onOpenChange(false)
    } catch (err) {
      notifyError(err, 'No se pudo regenerar la sección.')
    } finally {
      setRegenerating(false)
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-3xl">
        <DialogHeader>
          <DialogTitle>
            {section.section_number}. {section.section_name}
          </DialogTitle>
          <DialogDescription>
            {section.model_used
              ? `${section.model_used} · ${dosificationLabel(section.dosification)}`
              : 'Edita el contenido Markdown de la sección.'}
          </DialogDescription>
        </DialogHeader>

        {section.status === 'failed' && section.error_message && (
          <div className="rounded-xl border border-destructive/50 bg-destructive/10 px-3 py-2 text-sm text-destructive">
            {section.error_message}
          </div>
        )}

        {canRegenerate && (models?.length ?? 0) > 0 && (
          <div className="flex flex-wrap gap-4">
            <div className="flex flex-wrap items-center gap-2">
              <label className="text-sm text-muted-foreground" htmlFor="section-gemini-model">
                Motor Gemini
              </label>
              <ModelSelect
                id="section-gemini-model"
                value={geminiModel}
                onChange={(v) => {
                  setGeminiModel(v)
                  writeModelPref('gemini', v)
                }}
                options={models!}
                disabled={regenerating || saving}
              />
            </div>
            <div className="flex flex-wrap items-center gap-2">
              <label className="text-sm text-muted-foreground" htmlFor="section-claude-model">
                Motor Claude
              </label>
              <ModelSelect
                id="section-claude-model"
                value={claudeModel}
                onChange={(v) => {
                  setClaudeModel(v)
                  writeModelPref('claude', v)
                }}
                options={models!}
                disabled={regenerating || saving}
              />
            </div>
          </div>
        )}

        <div data-color-mode="light" className="max-h-[60vh] overflow-auto">
          <Suspense fallback={<p className="text-sm text-muted-foreground">Cargando editor…</p>}>
            <MDEditor
              value={content}
              onChange={(v) => setContent(v ?? '')}
              preview="live"
              height={420}
              overflow={false}
            />
          </Suspense>
        </div>

        <DialogFooter className="gap-2">
          {canRegenerate && (
            <Button
              variant="outline"
              onClick={handleRegenerate}
              disabled={regenerating || saving}
            >
              <RefreshCw className="mr-2 h-4 w-4" />
              {regenerating ? 'Regenerando…' : 'Regenerar'}
            </Button>
          )}
          <Button onClick={handleSave} disabled={saving || regenerating}>
            <Save className="mr-2 h-4 w-4" />
            {saving ? 'Guardando…' : 'Guardar'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
