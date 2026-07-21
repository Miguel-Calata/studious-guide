# AGENTS.md — SAM Platform

> Plataforma que convierte PDFs de guías clínicas y artículos científicos en compendios médicos de 11 secciones, usando IA (Gemini + Claude vía OpenRouter), con publicación en S3 + Notion.
> **Cliente:** Dr. Jorge (médico) · **Usuarios finales:** residentes de medicina.

---

## ⚠️ PROPÓSITO DE ESTE ARCHIVO — LEER ANTES QUE NADA

Este archivo existe para **evitar que los agentes causen daño**. Parte del pipeline actual fue construido por agentes que eligieron la vía eficiente, simple o directamente perezosa, cuando el dominio exigía lo contrario. Este documento es la corrección permanente a ese comportamiento.

**Esto es medicina.** No es un CRUD, ni un blog, ni una app de notas. El contenido que genera este sistema lo usan médicos para estudiar y consultar decisiones clínicas. Un agente que "optimiza" este pipeline como si fuera software genérico está cometiendo un error grave, aunque el código pase los tests.

Antes de proponer o implementar cualquier solución, pregúntate:

> *"¿Estoy eligiendo esta solución porque es correcta para un dominio clínico, o porque es la más fácil/rápida/genérica?"*

Si la respuesta es la segunda, detente y busca la solución ad hoc. Si no estás seguro, **pregunta al usuario antes de implementar**.

---

## 🩺 PILAR #1 — Fidelidad y veracidad de los compendios

### Principio rector

> **En salud, un dato inventado o una cifra alterada es PEOR que un dato ausente.**
> La fidelidad a la fuente prima sobre la completitud, la fluidez del texto, la velocidad de entrega y la elegancia del código. Siempre.

Todo el contenido clínico del compendio debe ser **real y trazable a los PDFs fuente**. Nada de conocimiento del modelo, nada de "rellenar huecos", nada de cifras aproximadas. Cuando la fuente no cubre un punto, el sistema lo **declara explícitamente** — nunca lo inventa.

### 🚫 Anti-patrones PROHIBIDOS (atajos de "agente flojo")

Estos comportamientos ya causaron problemas reales en este proyecto. Están terminantemente prohibidos:

1. **Truncar contenido para ahorrar tokens** o para que "quepa" en el contexto. El sistema ya falla en voz alta ante overflow (`ContextOverflowError`, `ContinuationExhaustedError`); jamás introduzcas truncamiento silencioso para "arreglar" esos errores.
2. **Resumir o condensar tablas/cifras** de la fuente "para simplificar". Las tablas se reproducen completas. Una dosis, un umbral o un porcentaje alterado es un fallo clínico, no de formato.
3. **Promediar o fusionar valores divergentes** entre guías (ej. dos guías con umbrales distintos). Las divergencias se reportan aisladas y explícitas; promediar guías es fabricar un dato que no existe en ninguna fuente.
4. **Descartar o ignorar documentos/extracciones que fallan** con un simple warning para que el pipeline "siga avanzando". Un documento excluido en silencio = omisiones invisibles en el compendio.
5. **Debilitar prompts para que "funcione"**: quitar instrucciones anti-alucinación, relajar la citación granular o el protocolo de vacío documental porque un modelo no las cumple, o acortar prompts "para eficiencia".
6. **Validaciones genéricas donde se necesita criterio de dominio**: un check de keywords plano NO es verificación de fidelidad. No vendas una comprobación superficial como si fuera una garantía.
7. **Marcar como completo algo parcial**: secciones truncadas, extracciones incompletas o contenido con errores de filtrado nunca se marcan como COMPLETED "para no bloquear el flujo".
8. **Automatizar la revisión humana**: los gates de aprobación (ecos map, revisión del Dr.) no se eliminan ni se auto-aprueban "para agilizar".
9. **Elegir la implementación más simple cuando el dominio pide la correcta**: si la solución correcta cuesta más trabajo, se hace el trabajo. La simplicidad es un valor de ingeniería, nunca a costa de la fidelidad clínica.

### ✅ Reglas inviolables al tocar el pipeline

Aplican a extracción, merge, generación de secciones, prompts, ecos map y publicación:

1. **Nunca debilites las garantías anti-alucinación existentes** (Pilar I "hermetismo documental", protocolo de vacío documental, citación granular inline). Todo cambio de prompt debe mantenerlas o reforzarlas; relajarlas es una regresión.
2. **Todo texto clínico proviene de `merged_content`** (las extracciones de los PDFs). Si una modificación introduce contenido que no es trazable a la fuente, es un bug — aunque el texto sea "correcto" según el conocimiento general del modelo.
3. **Fail-loud, nunca fail-silent**: ante contenido truncado, filtrado, vacío, tabla malformada o documento no procesado → error explícito. Nunca continuar con datos degradados.
4. **Tablas, dosis, umbrales y cifras son datos críticos**: cualquier cambio en extracción (`pymupdf4llm`), sanitización o merge debe demostrar que sobreviven íntegros (test con fixture que incluya tabla + dosis + cita).
5. **Las citas deben corresponder a documentos reales del proyecto.** Nunca generar, completar ni "corregir" referencias desde el modelo.
6. **No eliminar ni debilitar la auditoría de extracción** (`app/modules/audit/service.py`, `find_missing_facts`): hoy es el único detector automático de omisiones.
7. **No saltarse gates humanos existentes** (aprobación del ecos map es obligatoria para generar; mantenerlo así o más estricto, nunca menos).
8. **Si tocas extracción/merge/generación**: corre la suite completa en Docker y añade/actualiza un test que cubra fidelidad (omisiones, tablas, cifras o citas).

### 🕳️ Brechas conocidas de fidelidad (deuda técnica — no empeorar)

Estas debilidades existen hoy. Conócelas, no las empeores, y tenlas en cuenta antes de afirmar que algo "está verificado":

- **No hay verificador post-generación**: nada compara las 11 secciones finales contra `merged_content`/PDFs. La auditoría por keywords solo cubre la etapa de extracción.
- **Las citas no están validadas**: `[KDIGO 2026]` es texto libre del LLM; nada comprueba que la fuente citada exista en el corpus del proyecto (riesgo de cita alucinada).
- **`SectionStatus.APPROVED` existe pero no está cableado**: se puede publicar con secciones en estado COMPLETED sin revisión humana del texto clínico (`app/modules/publishing/service.py`).
- **La auditoría v1 es keyword-based y no bloqueante**: sus warnings solo se loguean; el pipeline continúa con hechos faltantes.
- **`pymupdf4llm` puede mutilar tablas** antes de que el LLM las vea; el PDF nunca se envía como archivo nativo al modelo.
- **El merge puede excluir documentos solo con warning** (`merge_extractions`), y el auto-propose del ecos map trunca la fuente (`ecos_map_max_source_chars`).

### 💡 Mejoras futuras anotadas (pendientes de planificar)

- Verificador de fidelidad post-generación (compendio ↔ fuente: alucinaciones, omisiones, verificación numérica).
- Validación de citas contra el corpus real del proyecto.
- Gate de aprobación humana por sección antes de publicar (cablear `APPROVED`).
- Auditoría bloqueante y/o verificación con segundo modelo (critic/verifier).

---

## 🧪 Comandos

### Tests (dentro del contenedor Docker)

Los tests corren dentro del contenedor `docker-backend-1` (necesita acceso a `postgres:5432`). El contenedor ya tiene `pytest` y `tests/` en `/app/tests`.

```bash
# Toda la suite del backend
docker exec docker-backend-1 pytest tests/ -q --tb=short

# Un archivo de tests
docker exec docker-backend-1 pytest tests/test_notion.py -q --tb=short

# Un test específico
docker exec docker-backend-1 pytest tests/test_notion.py::test_md_to_notion_blocks_table_width_and_cells -q
```

### Lint (venv local)

```bash
cd backend && venv/bin/ruff check app tests
```

### Type checking

`mypy` no está instalado en el contenedor ni en el venv. Para comprobar:

```bash
cd backend && venv/bin/pip install mypy && venv/bin/mypy app
```

Nota: `mypy` está configurado con `strict = true` en `pyproject.toml` y puede reportar errores preexistentes en el proyecto.

### Sincronizar código al contenedor

Tras editar archivos localmente, cópialos al contenedor en ejecución antes de correr tests:

```bash
docker cp backend/app/modules/<modulo>/<archivo>.py docker-backend-1:/app/app/modules/<modulo>/<archivo>.py
docker cp backend/tests/<test>.py docker-backend-1:/app/tests/<test>.py
```

Alternativa para cambios grandes: `docker compose up --build backend worker`.

---

## 📂 Estructura y stack

```
ProyectoJorge/
├── docs/       ← Documentación de arquitectura y decisiones (ver abajo)
├── memory/     ← Documentación original del Dr. Jorge (referencia de dominio)
├── backend/    ← FastAPI + SQLAlchemy 2.0 + ARQ/Redis (Python 3.12)
├── frontend/   ← React 19 + TypeScript + Vite + Tailwind + shadcn/ui
├── docker/     ← Dockerfiles + nginx
└── docker-compose.yml
```

PostgreSQL 16 · Redis 7 · OpenRouter (gateway único de IA) · S3 (prod) / MinIO (local) · Docker Compose + Coolify.

### Lectura obligatoria antes de tocar el pipeline

- `docs/09_pipeline_ia.md` — pipeline de IA end-to-end
- `docs/08_prompt_engine.md` — motor de prompts y sus garantías
- `docs/02_arquitectura.md`, `docs/06_modulos.md` — arquitectura y módulos
- `docs/11_changelog.md` — historia de decisiones (consulta antes de deshacer algo "raro")

---

## 🏗️ Convenciones

- **Cambios mínimos y ad hoc**: toca solo lo necesario, sigue el estilo del código existente, y adapta la solución al dominio (ver Pilar #1). "Minimal" nunca significa "superficial".
- **Lint con ruff** antes de dar por terminado un cambio en backend.
- **Tests**: si el proyecto tiene tests del área que tocas, añade/actualiza tests y corre la suite en Docker.
- **FSM de estados**: proyectos, extracciones y secciones usan máquinas de estados; respétalas, no hagas transiciones "a mano".
- **Prompts versionados** en `prompt_templates` (BD + seeds en `alembic/versions/`); no hardcodear prompts en lógica nueva sin seguir ese patrón.
- **No commitear** sin que el usuario lo pida explícitamente; no tocar git config ni hacer force-push.
