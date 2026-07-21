"""Tarea 3 — Tabla `ecos_maps` + columna `ecos_map_version` en secciones.

- Crea `ecos_maps` (una fila por patología+versión; JSONB con el
  mapa de 11 secciones; versionado espejo de `prompt_templates`).
- Crea el índice de pathology_key para lookups rápidos.
- Añade `compendium_sections.ecos_map_version` para trazabilidad
  histórica de qué mapa usó cada sección generada.
- Siembra el mapa AKI v1 como `approved`/`active`/`origin=seed`
  copiando byte a byte el contenido actualmente en
  `SECTION_CONFIGS[*].ecos` del módulo `section_builder`. Cargar la
  fuente desde Python (no hardcodear el JSON aquí) garantiza que
  cualquier ajuste manual al config de AKI se propague en futuras
  migraciones de seed.
"""

from alembic import op
import sqlalchemy as sa


revision = "011_ecos_maps"
down_revision = "010_seed_audit_checklists"
branch_labels = None
depends_on = None


def _load_aki_sections_dict() -> dict:
    """
    Importa el config actual de AKI desde la app y devuelve el dict
    `{str(section_number): [...ecos]}` para todas las 11 secciones.

    Se ejecuta dentro de la transacción de Alembic, que tiene acceso
    a `app.*` porque el `upgrade` corre dentro del `env.py` que ya
    configuró el path del proyecto.
    """
    from app.modules.prompts.section_builder import SECTION_CONFIGS

    out: dict = {}
    for n in range(1, 12):
        cfg = SECTION_CONFIGS[n]
        out[str(n)] = list(cfg.ecos)
    return out


def upgrade() -> None:
    op.create_table(
        "ecos_maps",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column(
            "pathology_key",
            sa.String(length=255),
            nullable=False,
        ),
        sa.Column(
            "pathology_name",
            sa.String(length=255),
            nullable=False,
        ),
        sa.Column(
            "version",
            sa.Integer(),
            server_default="1",
            nullable=False,
        ),
        sa.Column("sections", sa.JSON(), nullable=False),
        sa.Column(
            "status",
            sa.String(length=50),
            server_default="draft",
            nullable=False,
        ),
        sa.Column(
            "origin",
            sa.String(length=50),
            server_default="manual",
            nullable=False,
        ),
        sa.Column(
            "is_active",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
        sa.Column(
            "approved_by",
            sa.String(),
            sa.ForeignKey("users.id"),
            nullable=True,
        ),
        sa.Column(
            "approved_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column("description", sa.String(length=1000), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "pathology_key",
            "version",
            name="uq_ecos_maps_pathology_version",
        ),
    )
    op.create_index(
        "ix_ecos_maps_pathology_key",
        "ecos_maps",
        ["pathology_key"],
    )
    op.create_index(
        "ix_ecos_maps_active",
        "ecos_maps",
        ["pathology_key", "is_active"],
    )

    op.add_column(
        "compendium_sections",
        sa.Column(
            "ecos_map_version",
            sa.String(length=50),
            nullable=True,
        ),
    )

    # Seed AKI v1 (origen=seed, status=approved, is_active=True).
    # El path_key usa el slug "aki" como clave normalizada principal;
    # pathology_name conserva la nomenclatura humana.
    import uuid as _uuid

    sections_dict = _load_aki_sections_dict()
    bind = op.get_bind()
    bind.execute(
        sa.text(
            "INSERT INTO ecos_maps "
            "(id, pathology_key, pathology_name, version, sections, "
            " status, origin, is_active, description, "
            " created_at, updated_at) "
            "VALUES (:id, :key, :name, :ver, CAST(:sections AS JSON), "
            " :status, :origin, :active, :desc, NOW(), NOW())"
        ).bindparams(
            id=str(_uuid.uuid4()),
            key="aki",
            name="Insuficiencia Renal Aguda (LRA / AKI)",
            ver=1,
            sections=_to_json_string(sections_dict),
            status="approved",
            origin="seed",
            active=True,
            desc=(
                "Mapa AKI v1 — sembrado desde SECTION_CONFIGS "
                "originales; byte-idéntico al config legacy."
            ),
        )
    )

    # Seed del mini-prompt de auto-poblado (type='ecos_map').
    # No se invoca desde el pipeline de producción; sólo desde el
    # endpoint humano POST /pathologies/{key}/ecos-map:propose.
    ecos_autopopulate = """Eres un asistente que propone un primer \
borrador de MAPA DE ECOS para una patología nueva, basándose \
exclusivamente en la plantilla genérica de slots por sección que se \
te proporciona. La plantilla define qué temas (slots) es dueña de \
desarrollar cada sección; tú propones los ECOS (referencias cruzadas \
para secciones POSTERIORES) que cada sección debe mencionar en su \
bloque MAPA DE ECOS.

Reglas:
  1. Para cada slot del template, genera una frase de eco que \
mencione explícitamente el slot_id o su label humano. Las frases \
deben estar en español, en formato imperativo breve \
("(→ ver Sección)") o referencia cruzada de una línea.
  2. NO inventes slots que no estén en el template.
  3. NO desarrolles el contenido del slot: tu salida son SOLO \
referencias cruzadas, no prosa clínica.
  4. Cada sección (1 a 11) tiene su propia lista de ecos, incluso \
si la sección 1 está vacía.
  5. Devuelve exclusivamente un JSON válido con la forma \
{"1": ["..."], "2": ["..."], ..., "11": ["..."]}. Sin texto \
adicional fuera del JSON."""

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
            content=ecos_autopopulate,
            ver=1,
            active=True,
            desc=(
                "Mini-prompt para auto-poblar un ecos map borrador "
                "a partir de ECOS_SECTION_TEMPLATE. Sólo invocable "
                "por endpoint humano; NUNCA desde el pipeline."
            ),
        )
    )


def _to_json_string(d: dict) -> str:
    import json

    return json.dumps(d, ensure_ascii=False)


def downgrade() -> None:
    op.drop_column("compendium_sections", "ecos_map_version")
    op.drop_index("ix_ecos_maps_active", table_name="ecos_maps")
    op.drop_index("ix_ecos_maps_pathology_key", table_name="ecos_maps")
    op.drop_table("ecos_maps")
