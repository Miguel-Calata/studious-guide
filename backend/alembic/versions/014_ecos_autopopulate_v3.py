"""Fix ecos map — v3 del prompt `ecos_map_autopopulate`.

Corrige la contradicción interna de la v2 sobre la dirección de los
ecos. La semántica real del compendio (seed AKI + bloque
`_build_ecos_block` de section_builder) es BACKWARD: un eco es una
referencia cruzada a un tema YA desarrollado en una sección
ANTERIOR ("CONTENIDO YA CUBIERTO — mención ≠ desarrollo", R-1).
La v2 mezclaba esa semántica con una DEFINICIÓN forward ("un tema
que se desarrollará en una sección POSTERIOR") y una R6 que
exigía el eco en la propia sección dueña — lo que producía
salidas inconsistentes del LLM y warnings de validación eternos.

Cambios v3 sobre v2:
- DEFINICIÓN alineada a la semántica backward real.
- R6 corregida: cada slot de las secciones 1-10 debe aparecer como
  eco en AL MENOS UNA sección POSTERIOR a su dueña; los slots de
  la sección 11 nunca son ecos (no hay secciones posteriores).
- R2 aclara que la sección referenciada es siempre la DUEÑA
  (anterior a donde va el eco).
- Se mantiene R1 (sección 1 siempre vacía) y el resto de reglas.

Acompaña a la corrección de `validate_ecos_map` en
`app/modules/prompts/ecos_service.py`, que ahora valida con esta
misma semántica (antes exigía el eco en la sección dueña, lo cual
contradecía R-1 y hacía fallar incluso al seed AKI).
"""

# ruff: noqa: E501

import uuid as _uuid

import sqlalchemy as sa

from alembic import op

revision = "014_ecos_autopopulate_v3"
down_revision = "013_ecos_autopopulate_v2"
branch_labels = None
depends_on = None


ECOS_AUTOPOPULATE_V3 = """Eres un especialista en diseño curricular médico y tu tarea es proponer un MAPA DE ECOS (referencias cruzadas) para un compendio clínico de 11 secciones.

DEFINICIÓN: Un "eco" es una referencia cruzada de UNA LÍNEA que una sección incluye para apuntar a un tema que YA FUE DESARROLLADO en una sección ANTERIOR. Los ecos protegen la regla R-1 anti-repetición del compendio: "mención ≠ desarrollo". El tema lo desarrolla siempre su sección DUEÑA; las secciones POSTERIORES solo lo referencian con un eco.

ENTRADA — RECIBIRÁS:
1. PATOLOGÍA: nombre de la condición clínica.
2. TEMPLATE GENÉRICO: slots (temas) que cada sección (1-11) es dueña de desarrollar.
3. CONTENIDO FUENTE (opcional): extractos de guías clínicas del proyecto. Si está presente, PRIORIZA ecos para temas cubiertos por las fuentes.

REGLAS ESTRICTAS:
R1. Sección 1: SIEMPRE devuelve lista vacía []. No hay secciones anteriores que referenciar.
R2. Cada eco es UNA SOLA LÍNEA en español, formato: "[Tema] (→ ver Sección N: [Label del slot])", donde N es la sección DUEÑA del tema, siempre ANTERIOR a la sección donde va el eco.
R3. Cada eco DEBE mencionar explícitamente el slot_id o su label del template.
R4. NO inventes slots que no estén en el template.
R5. NO desarrolles contenido clínico: cero prosa, cero tablas, cero dosis. Solo referencias cruzadas.
R6. Cobertura: cada slot de las secciones 1 a 10 debe aparecer como eco en AL MENOS UNA sección POSTERIOR a su sección dueña. Los slots de la sección 11 NUNCA aparecen como ecos (no hay secciones posteriores).
R7. NO dupliques el mismo eco dentro de una misma sección.
R8. Si hay CONTENIDO FUENTE, prioriza ecos hacia slots que las fuentes cubren. Si un slot NO está en las fuentes, inclúyelo igual pero anota "candidato a revisión" al final del eco.
R9. Devuelve EXCLUSIVAMENTE un JSON válido con la forma {"1": [], "2": ["..."], ..., "11": ["..."]}. Sin texto adicional fuera del JSON.

EJEMPLO DE ECO CORRECTO (en la sección 5, apuntando a la dueña anterior):
  "Criterios diagnósticos formales (→ ver Sección 2: Clasificación)"

EJEMPLO DE ECO INCORRECTO (demasiado largo, es prosa):
  "La definición de LRA según KDIGO 2012 incluye un aumento de SCr ≥0.3 mg/dL en 48 horas o ≥1.5 veces el basal en 7 días, o bien una diuresis <0.5 mL/kg/h durante 6 horas. Esto es importante porque..."

Genera ahora el mapa de ecos para la patología indicada."""


def upgrade() -> None:
    bind = op.get_bind()

    # Desactivar v2 (y cualquier activa residual)
    bind.execute(
        sa.text(
            "UPDATE prompt_templates SET is_active = false, updated_at = NOW() "
            "WHERE name = 'ecos_map_autopopulate' AND is_active = true"
        )
    )

    # Insertar v3
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
            content=ECOS_AUTOPOPULATE_V3,
            ver=3,
            active=True,
            desc=(
                "v3: semántica backward consistente (eco = referencia a "
                "tema YA desarrollado en sección anterior); R6 exige el "
                "eco en secciones posteriores a la dueña; alineada con "
                "validate_ecos_map corregido."
            ),
        )
    )


def downgrade() -> None:
    bind = op.get_bind()

    # Eliminar v3
    bind.execute(
        sa.text(
            "DELETE FROM prompt_templates "
            "WHERE name = 'ecos_map_autopopulate' AND version = 3"
        )
    )

    # Reactivar v2
    bind.execute(
        sa.text(
            "UPDATE prompt_templates SET is_active = true, updated_at = NOW() "
            "WHERE name = 'ecos_map_autopopulate' AND version = 2"
        )
    )
