# 13 — Comparación empírica de motores (Tarea 4)

## 🎯 Objetivo

Proveer evidencia medible sobre si la bifurcación original
Gemini/Claude (decisión de v8/v9, documentada en
[09_pipeline_ia.md](09_pipeline_ia.md)) sigue justificándose
**dado el catálogo actual de AVAILABLE_MODELS** y la
implementación real (Tarea 1) del orquestador con extended
thinking.

**Este documento y el harness asociado NO deciden automáticamente.**
Entregan datos; un humano completa la rúbrica cualitativa y
toma la decisión de producto.

---

## 🔬 Por qué se necesita ahora

- `MOTOR_MODEL_MAP` quedó con ambos motores apuntando a
  `DEFAULT_GENERATION_MODEL` (Gemini 3.1 Pro), de modo que la
  bifurcación está **muerta en producción** aunque el spec la
  mantiene.
- El razonamiento de la bifurcación original (Gemini barato para
  secciones descriptivas, Claude + extended thinking para
  razonamiento clínico profundo) era razonable con los modelos de
  entonces (Gemini 2.5 Pro, Claude 3.5 Sonnet).
- Hoy el catálogo incluye Opus 4.8, Sonnet 5 (con adaptive
  thinking), Gemini 3.1 Pro, GPT-5 Pro, y modelos free
  utilizables para calibración. **La decisión merece ser
  re-evaluada con datos.**

---

## 🛠️ Harness

`backend/scripts/compare_motors.py` — script CLI que:

1. Carga un proyecto existente con `merged_content` listo.
2. Genera las secciones 🔴 (por defecto `3, 5, 8, 9`) con cada
   modelo del subconjunto que se le pase.
3. Aplica `extra_params.thinking` (`reasoning: {enabled: true}`)
   en secciones 🔴 cuando el motor es Claude.
4. Mide tokens, costo, latencia por sección.
5. Calcula `missing_facts` por sección usando
   `find_missing_facts` (Tarea 2) contra el checklist del tipo
   de documento — **métrica objetiva de fidelidad a fuentes**.
6. Persiste los outputs en `comparisons/<timestamp>_<id>/` con:
   - `<model_id>/seccion_NN.md` — contenido completo
   - `metrics.json` — métricas machine-readable
   - `comparison_report.md` — **plantilla de reporte a completar
     por humano** con rúbrica cualitativa.

### Uso

```bash
cd backend
export OPENROUTER_API_KEY=...
python -m scripts.compare_motors \
    --project-id <UUID> \
    --models google/gemini-3.1-pro-preview,anthropic/claude-sonnet-5,anthropic/claude-opus-4.8 \
    --sections 3,5,8,9
```

Los `--models` se validan contra `AVAILABLE_MODELS` — no se
pueden usar modelos fuera del catálogo.

### Costo estimado (orientativo)

| Modelos | Secciones | Costo est. por run |
| --- | --- | --- |
| Gemini 3.1 Pro + Claude Sonnet 5 | 3, 5, 8, 9 | ~$2-5 USD |
| Gemini 3.1 Pro + Sonnet 5 + Opus 4.8 | 3, 5, 8, 9 | ~$5-15 USD |
| Solo modelos free (calibración) | 3, 5, 8, 9 | ~$0 USD |

---

## 📊 Rúbrica de revisión humana

Para cada par (modelo, sección), responder:

1. **Fidelidad a fuentes** (objetiva, via `missing_facts`):
   ¿hay omisiones flagrantes? ¿alucinaciones numéricas?
2. **Cobertura del MAPA DE ECOS** (semi-objetiva): ¿Se desarrollan
   los temas del template sin omitir?
3. **Cumplimiento de las 10 Leyes** (R-1…R-10) — manual:
   referencias cruzadas, citación granular, formato callout.
4. **Calidad clínica** — razonamiento diagnóstico, manejo, dosis:
   ¿se sostiene la postura de "Claude para razonamiento profundo"?
5. **Latencia / costo** — ¿La diferencia de calidad justifica
   la diferencia de costo/latencia?

---

## 📋 Formato del reporte

`comparison_report.md` (generado por el harness) tiene la
siguiente estructura:

```markdown
# Comparación empírica de motores — {patología}

## Modelos comparados
[claude-sonnet-5, gemini-3.1-pro, claude-opus-4.8, ...]

## Métricas agregadas (secciones 3, 5, 8, 9)
| Modelo | Input tokens | Output tokens | Costo USD | Latencia total |
| --- | ---: | ---: | ---: | ---: |
| `claude-sonnet-5` | ... | ... | ... | ... |
| `gemini-3.1-pro`  | ... | ... | ... | ... |
| `claude-opus-4.8` | ... | ... | ... | ... |

## Rúbrica de revisión humana
[Por modelo, por sección: 5 preguntas]
```

---

## 🎯 Decisión pendiente de producto

Tras revisar los outputs y la rúbrica, el dueño de producto
debe decidir una de las siguientes opciones (no implementada
automáticamente):

- **A) Restaurar bifurcación** — actualizar `MOTOR_MODEL_MAP`
  con los modelos ganadores por motor (ej.
  `gemini → 3.1-pro`, `claude → sonnet-5`).
- **B) Bifurcación más fina** — por sección en lugar de por
  motor (ej. sección 3 y 8 a Opus, sección 5 y 9 a Sonnet).
- **C) Sin bifurcación** — todo a Gemini 3.1 Pro (más barato).
- **D) Modelo único premium** — todo a Opus 4.8 (calidad
  uniforme, costo alto).

La decisión se aplica en `MOTOR_MODEL_MAP` (Tarea 1) y se
documenta en este doc + changelog.

---

> **Próximo documento:** volver a [12_roadmap_sprints.md](12_roadmap_sprints.md) tras ejecutar la comparación y archivar el reporte final.
