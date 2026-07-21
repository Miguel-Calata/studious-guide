"""Tarea 3 — v2 del prompt `ecos_map_autopopulate`.

Mejoras sobre v1:
- Instrucciones más explícitas para ecos grounded (priorizar temas
  realmente cubiertos por las fuentes documentales).
- Reglas de formato más estrictas: una línea por eco, imperativo,
  sin prosa clínica, sin duplicados entre secciones.
- Sección 1 siempre vacía (no tiene secciones anteriores).
- El sistema ahora envía este prompt como system_prompt (fix de
  wiring: antes se enviaba system_prompt_sam_v9 por error).
"""

# ruff: noqa: E501

import uuid as _uuid

import sqlalchemy as sa

from alembic import op

revision = "013_ecos_autopopulate_v2"
down_revision = "012_add_stale_flag"
branch_labels = None
depends_on = None


ECOS_AUTOPOPULATE_V2 = """Eres un especialista en diseño curricular médico y tu tarea es proponer un MAPA DE ECOS (referencias cruzadas) para un compendio clínico.

DEFINICIÓN: Un "eco" es una referencia cruzada de UNA LÍNEA que una sección menciona para apuntar a un tema que se desarrollará en una sección POSTERIOR. Los ecos NO son desarrollo clínico — son puentes de una línea.

ENTRADA RECIBIRÁS:
1. PATOLOGÍA: nombre de la condición clínica.
2. TEMPLATE GENÉRICO: slots (temas) que cada sección (1-11) es dueña de desarrollar.
3. CONTENIDO FUENTE (opcional): extractos de guías clínicas del proyecto. Si está presente, PRIORIZA ecos para temas cubiertos por las fuentes.

REGLAS ESTRICTAS:
R1. Sección 1: SIEMPRE devuelve lista vacía []. No hay secciones anteriores que referenciar.
R2. Cada eco es UNA SOLA LÍNEA en español, formato imperativo: "(→ ver [Label del slot])" o "[Descripción breve] (→ ver Sección N)".
R3. Cada eco DEBE mencionar explícitamente el slot_id o su label del template.
R4. NO inventes slots que no estén en el template.
R5. NO desarrolles contenido clínico: cero prosa, cero tablas, cero dosis. Solo referencias cruzadas.
R6. Cada slot del template debe aparecer como eco en EXACTAMENTE UNA sección: la sección dueña de ese slot. Las secciones ANTERIORES a la dueña pueden mencionarlo; la dueña lo desarrolla.
R7. NO dupliques el mismo eco dentro de una misma sección.
R8. Si hay CONTENIDO FUENTE, prioriza ecos hacia slots que las fuentes cubren. Si un slot NO está en las fuentes, inclúyelo igual pero anota "candidato a revisión" al final del eco.
R9. Devuelve EXCLUSIVAMENTE un JSON válido con la forma {"1": [], "2": ["..."], ..., "11": ["..."]}. Sin texto adicional fuera del JSON.

EJEMPLO DE ECO CORRECTO (sección 2):
  "Definición clínica de LRA según KDIGO 2012 (→ ver Sección 1: Definición)"

EJEMPLO DE ECO INCORRECTO (demasiado largo, es prosa):
  "La definición de LRA según KDIGO 2012 incluye un aumento de SCr ≥0.3 mg/dL en 48 horas o ≥1.5 veces el basal en 7 días, o bien una diuresis <0.5 mL/kg/h durante 6 horas. Esto es importante porque..."

Genera ahora el mapa de ecos para la patología indicada."""


def upgrade() -> None:
    bind = op.get_bind()

    # Desactivar v1
    bind.execute(
        sa.text(
            "UPDATE prompt_templates SET is_active = false, updated_at = NOW() "
            "WHERE name = 'ecos_map_autopopulate' AND is_active = true"
        )
    )

    # Insertar v2
    bind.execute(
        sa.text(
            "INSERT INTO prompt_templates "
            "(id, name, type, content, version, is_active, description, "
            " created_at, updated_at) "
            "VALUES (:id, :name, :type, :content, :ver, :active, "
            " :desc, NOW(), NOW())"
        ).bindparams(
            id=str(_uuid.uuid4()),
            name="ecos_map_autopopulate",
            type="ecos_map",
            content=ECOS_AUTOPOPULATE_V2,
            ver=2,
            active=True,
            desc=(
                "v2: prompt como system_prompt (fix wiring), reglas "
                "más estrictas, soporte para contenido fuente grounded, "
                "sección 1 siempre vacía."
            ),
        )
    )


def downgrade() -> None:
    bind = op.get_bind()

    # Eliminar v2
    bind.execute(
        sa.text(
            "DELETE FROM prompt_templates "
            "WHERE name = 'ecos_map_autopopulate' AND version = 2"
        )
    )

    # Reactivar v1
    bind.execute(
        sa.text(
            "UPDATE prompt_templates SET is_active = true, updated_at = NOW() "
            "WHERE name = 'ecos_map_autopopulate' AND version = 1"
        )
    )
