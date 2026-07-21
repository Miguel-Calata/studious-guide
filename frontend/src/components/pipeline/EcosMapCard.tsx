import { useCallback, useEffect, useMemo, useState } from 'react'
import useSWR from 'swr'
import { Loader2, RefreshCw, Save, CheckCircle, Wand2 } from 'lucide-react'

import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { EcosSectionAccordion } from '@/components/pipeline/EcosSectionAccordion'
import {
  getActiveEcoMap,
  getPendingDraft,
  proposeEcoMap,
  updateEcoMap,
  approveEcoMap,
} from '@/api/ecos'
import {
  pathologyKeyFor,
  ecosUiStateLabel,
  ecosUiStateVariant,
  ecosToTextareas,
  textareasToEcos,
} from '@/lib/ecos'
import { notifyError, notifySuccess } from '@/lib/notify'
import { POLL_INTERVAL_MS } from '@/lib/pipeline'
import type { Project } from '@/types/project'
import type { EcosMap, EcosMapUiState } from '@/types/ecos'

export function EcosMapCard({
  project,
  onMutate,
}: {
  project: Project
  onMutate: () => void
}) {
  const [busy, setBusy] = useState(false)
  const [textareas, setTextareas] = useState<Record<string, string>>({})
  const [warnings, setWarnings] = useState<string[]>([])

  const pathologyKey = pathologyKeyFor(project.name)
  const hasMerge = !!project.merged_content?.trim()

  // ── SWR: mapa aprobado activo ──────────────────────────────
  const {
    data: active,
    mutate: mutateActive,
  } = useSWR(
    pathologyKey ? `ecos-active-${pathologyKey}` : null,
    () => getActiveEcoMap(pathologyKey),
    { revalidateOnFocus: false }
  )

  // ── SWR: borrador pendiente ────────────────────────────────
  const {
    data: pending,
    mutate: mutatePending,
  } = useSWR(
    pathologyKey ? `ecos-pending-${pathologyKey}` : null,
    () => getPendingDraft(pathologyKey),
    {
      refreshInterval: (): number =>
        // Polling solo si: no hay aprobado ni pending Y ya hay merged_content
        !active && !pending && hasMerge ? POLL_INTERVAL_MS : 0,
      revalidateOnFocus: false,
    }
  )

  // ── Estado UI compuesto ────────────────────────────────────
  const uiState: EcosMapUiState = useMemo(() => {
    if (pending) return 'draft_pending'
    if (active) return 'approved'
    if (hasMerge) return 'proposing'
    return 'no_map'
  }, [pending, active, hasMerge])

  // ── Inicializar textareas cuando cambia el mapa ────────────
  const currentMap: EcosMap | null = pending ?? active ?? null

  useEffect(() => {
    if (currentMap) {
      setTextareas(ecosToTextareas(currentMap.sections))
      setWarnings([])
    }
  }, [currentMap?.id]) // eslint-disable-line react-hooks/exhaustive-deps

  // ── Secciones con warnings (parse del description) ─────────
  const warningSections = useMemo(() => {
    const result = new Set<number>()
    for (const w of warnings) {
      // Los warnings vienen como "slot 'X' no aparece como eco ..."
      // Buscamos qué sección es dueña del slot
      const match = w.match(/\((\d+)\)/)
      if (match) result.add(Number(match[1]))
    }
    return result
  }, [warnings])

  // ── Handlers ───────────────────────────────────────────────
  const handleTextareaChange = useCallback(
    (key: string, value: string) => {
      setTextareas((prev) => ({ ...prev, [key]: value }))
    },
    []
  )

  const handleSave = useCallback(async () => {
    if (!currentMap) return
    setBusy(true)
    try {
      const sections = textareasToEcos(textareas)
      const res = await updateEcoMap(currentMap.id, { sections })
      setWarnings(res.warnings)
      notifySuccess('Cambios guardados.')
      mutatePending()
      onMutate()
    } catch (err) {
      notifyError(err, 'No se pudieron guardar los cambios.')
    } finally {
      setBusy(false)
    }
  }, [currentMap, textareas, mutatePending, onMutate])

  const handleApprove = useCallback(async () => {
    if (!currentMap) return
    setBusy(true)
    try {
      await approveEcoMap(currentMap.id)
      notifySuccess('Ecos map aprobado.')
      mutatePending()
      mutateActive()
      onMutate()
    } catch (err) {
      notifyError(err, 'No se pudo aprobar el ecos map.')
    } finally {
      setBusy(false)
    }
  }, [currentMap, mutatePending, mutateActive, onMutate])

  const handlePropose = useCallback(async () => {
    setBusy(true)
    try {
      await proposeEcoMap(pathologyKey)
      notifySuccess('Borrador generado. Revisando…')
      mutatePending()
    } catch (err) {
      notifyError(err, 'No se pudo generar el borrador.')
    } finally {
      setBusy(false)
    }
  }, [pathologyKey, mutatePending])

  // ── Render ─────────────────────────────────────────────────
  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between gap-3">
          <CardTitle className="text-lg tracking-tight">
            Mapa de Ecos
          </CardTitle>
          <Badge variant={ecosUiStateVariant(uiState)}>
            {uiState === 'draft_pending' && currentMap
              ? `${ecosUiStateLabel(uiState)} v${currentMap.version}`
              : uiState === 'approved' && currentMap
                ? `${ecosUiStateLabel(uiState)} v${currentMap.version}`
                : ecosUiStateLabel(uiState)}
          </Badge>
        </div>
      </CardHeader>

      <CardContent className="space-y-4">
        {/* ── Estado: no_map ────────────────────────────── */}
        {uiState === 'no_map' && (
          <div className="space-y-3">
            <p className="text-sm text-muted-foreground">
              Sube documentos, extrae y haz merge para generar
              automáticamente un borrador del mapa de ecos.
            </p>
            {hasMerge && (
              <Button
                size="sm"
                variant="outline"
                onClick={handlePropose}
                disabled={busy}
              >
                {busy ? (
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                ) : (
                  <Wand2 className="mr-2 h-4 w-4" />
                )}
                Forzar generación de borrador
              </Button>
            )}
          </div>
        )}

        {/* ── Estado: proposing ─────────────────────────── */}
        {uiState === 'proposing' && (
          <div className="space-y-3">
            <div className="flex items-center gap-2 text-sm text-muted-foreground">
              <Loader2 className="h-4 w-4 animate-spin" />
              <span>
                Generando borrador del mapa de ecos en segundo
                plano…
              </span>
            </div>
            <Button
              size="sm"
              variant="outline"
              onClick={handlePropose}
              disabled={busy}
            >
              {busy ? (
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              ) : (
                <RefreshCw className="mr-2 h-4 w-4" />
              )}
              Forzar generación
            </Button>
          </div>
        )}

        {/* ── Estado: draft_pending ─────────────────────── */}
        {uiState === 'draft_pending' && currentMap && (
          <div className="space-y-4">
            {active && (
              <p className="text-xs text-muted-foreground">
                v{active.version} aprobada sigue activa hasta
                aprobar esta nueva versión.
              </p>
            )}

            {currentMap.description && (
              <p className="text-xs text-muted-foreground">
                {currentMap.description}
              </p>
            )}

            <EcosSectionAccordion
              textareas={textareas}
              onChange={handleTextareaChange}
              warningSections={warningSections}
              readOnly={false}
              defaultOpen={warningSections.size > 0 ? Array.from(warningSections).map(String) : undefined}
            />

            {warnings.length > 0 && (
              <div className="rounded-md border border-warning/30 bg-warning/5 p-3 space-y-1">
                <p className="text-xs font-medium text-warning-foreground">
                  Warnings de cobertura:
                </p>
                {warnings.map((w, i) => (
                  <p key={i} className="text-xs text-muted-foreground">
                    • {w}
                  </p>
                ))}
              </div>
            )}

            <div className="flex flex-wrap gap-2">
              <Button
                size="sm"
                variant="outline"
                onClick={handleSave}
                disabled={busy}
              >
                {busy ? (
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                ) : (
                  <Save className="mr-2 h-4 w-4" />
                )}
                Guardar cambios
              </Button>
              <Button
                size="sm"
                onClick={handleApprove}
                disabled={busy}
              >
                {busy ? (
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                ) : (
                  <CheckCircle className="mr-2 h-4 w-4" />
                )}
                Aprobar
              </Button>
            </div>
          </div>
        )}

        {/* ── Estado: approved ──────────────────────────── */}
        {uiState === 'approved' && currentMap && (
          <div className="space-y-4">
            {currentMap.description && (
              <p className="text-xs text-muted-foreground">
                {currentMap.description}
              </p>
            )}

            <EcosSectionAccordion
              textareas={textareas}
              onChange={handleTextareaChange}
              readOnly={true}
            />

            <Button
              size="sm"
              variant="outline"
              onClick={handlePropose}
              disabled={busy}
            >
              {busy ? (
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              ) : (
                <RefreshCw className="mr-2 h-4 w-4" />
              )}
              Regenerar borrador
            </Button>
          </div>
        )}
      </CardContent>
    </Card>
  )
}
