import { useEffect, useRef, useState } from 'react'
import useSWR from 'swr'
import { Layers, FileStack } from 'lucide-react'
import { toast } from 'sonner'

import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { ProgressBar } from '@/components/pipeline/ProgressBar'
import { SectionList } from '@/components/sections/SectionList'
import { SectionEditor } from '@/components/sections/SectionEditor'
import { mergeProject, generateProject, getSections } from '@/api/compendiums'
import { getModels, type AiModel } from '@/api/ai'
import { DEFAULT_MODEL } from '@/config/models'
import { notifyError, notifySuccess } from '@/lib/notify'
import { isProjectBusy, POLL_INTERVAL_MS } from '@/lib/pipeline'
import type { Project, ProjectStatus } from '@/types/project'
import type { CompendiumSection } from '@/types/compendium'
import { TOTAL_SECTIONS } from '@/types/compendium'

const CAN_MERGE: ProjectStatus[] = ['draft', 'extracting', 'review']
const CAN_GENERATE: ProjectStatus[] = ['draft', 'review']

export function CompendiumCard({
  project,
  hasExtractedDocs,
  onMutate,
}: {
  project: Project
  hasExtractedDocs: boolean
  onMutate: () => void
}) {
  const [busy, setBusy] = useState(false)
  const [selected, setSelected] = useState<CompendiumSection | null>(null)
  const [models, setModels] = useState<AiModel[]>([])
  const [selectedGemini, setSelectedGemini] = useState<string>(DEFAULT_MODEL)
  const [selectedClaude, setSelectedClaude] = useState<string>(DEFAULT_MODEL)

  const { data: sections, mutate: mutateSections } = useSWR<CompendiumSection[]>(
    `/projects/${project.id}/sections`,
    () => getSections(project.id),
    {
      refreshInterval: () =>
        isProjectBusy(project.status) ? POLL_INTERVAL_MS : 0,
      revalidateOnFocus: false,
      fallbackData: undefined,
    }
  )

  useEffect(() => {
    getModels().then((list) => {
      setModels(list)
    })
  }, [])

  const prevSectionStatuses = useRef<Map<string, string>>(new Map())
  useEffect(() => {
    if (!sections) return
    for (const s of sections) {
      const prev = prevSectionStatuses.current.get(s.id)
      if (prev && prev !== 'failed' && s.status === 'failed') {
        toast.error(`Sección ${s.section_number} falló: ${s.error_message || 'Error desconocido'}`)
      }
      prevSectionStatuses.current.set(s.id, s.status)
    }
  }, [sections])

  const mergedReady =
    !!project.merged_content && project.merged_content.length > 0
  const canMerge = hasExtractedDocs && CAN_MERGE.includes(project.status)
  const canGenerate = mergedReady && CAN_GENERATE.includes(project.status)

  const list = sections ?? []
  const doneCount = list.filter(
    (s) => s.status === 'completed' || s.status === 'approved'
  ).length

  async function runMerge() {
    setBusy(true)
    try {
      const res = await mergeProject(project.id)
      notifySuccess(
        `Fusionadas ${res.extraction_count} extracciones (${res.merged_char_count} caracteres).`
      )
      onMutate()
    } catch (err) {
      notifyError(err, 'No se pudo fusionar las extracciones.')
    } finally {
      setBusy(false)
    }
  }

  async function runGenerate() {
    setBusy(true)
    try {
      const body = {
        gemini_model: selectedGemini,
        claude_model: selectedClaude,
      }
      const res = await generateProject(project.id, body)
      notifySuccess(`Generación iniciada: ${res.sections_created} secciones.`)
      onMutate()
      mutateSections()
    } catch (err) {
      notifyError(err, 'No se pudo generar el compendio.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Compendio</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="flex flex-wrap items-center gap-2">
          <Button onClick={runMerge} disabled={!canMerge || busy}>
            <Layers className="mr-2 h-4 w-4" />
            Fusionar extracciones
          </Button>
          <Button
            onClick={runGenerate}
            disabled={!canGenerate || busy}
            variant="default"
          >
            <FileStack className="mr-2 h-4 w-4" />
            Generar compendio
          </Button>
        </div>

        <div className="flex flex-wrap gap-4">
          <div className="flex items-center gap-2">
            <label className="text-sm text-muted-foreground" htmlFor="gemini-model">
              Motor Gemini:
            </label>
            <select
              id="gemini-model"
              value={selectedGemini}
              onChange={(e) => setSelectedGemini(e.target.value)}
              className="rounded-md border bg-background px-2 py-1 text-sm"
            >
              {models.map((m) => (
                <option key={m.id} value={m.id}>
                  {m.label}
                </option>
              ))}
            </select>
          </div>
          <div className="flex items-center gap-2">
            <label className="text-sm text-muted-foreground" htmlFor="claude-model">
              Motor Claude:
            </label>
            <select
              id="claude-model"
              value={selectedClaude}
              onChange={(e) => setSelectedClaude(e.target.value)}
              className="rounded-md border bg-background px-2 py-1 text-sm"
            >
              {models.map((m) => (
                <option key={m.id} value={m.id}>
                  {m.label}
                </option>
              ))}
            </select>
          </div>
        </div>

        {!mergedReady && (
          <p className="text-xs text-muted-foreground">
            Fusiona las extracciones antes de generar el compendio.
          </p>
        )}

        {list.length > 0 && (
          <ProgressBar
            value={doneCount}
            total={TOTAL_SECTIONS}
            label="Secciones completadas"
          />
        )}

        {list.length > 0 && (
          <SectionList sections={list} onSelect={setSelected} />
        )}

        {selected && (
          <SectionEditor
            section={selected}
            open={selected !== null}
            onOpenChange={(o) => !o && setSelected(null)}
            onSaved={(updated) => {
              mutateSections(
                (prev) =>
                  (prev ?? []).map((s) =>
                    s.id === updated.id ? updated : s
                  ),
                { revalidate: false }
              )
              onMutate()
            }}
          />
        )}
      </CardContent>
    </Card>
  )
}
