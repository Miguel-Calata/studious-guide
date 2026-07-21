"""Seed de checklists de auditoría por tipo de documento (Tarea 2).

Tarea 2 introduce una versión MÍNIMA viable de la auditoría de
extracción: en lugar del LLM self-audit (legacy `audit` prompt), se
compara el contenido extraído contra una lista curada de "hechos
esperados" (checklist) por tipo de fuente, usando matching por
palabra clave/entidad. Los checklists viven en `prompt_templates` con
`type="audit_checklist"` y siguen el patrón de versionado del
ecosistema: nueva versión desactiva la anterior, el código siempre
lee la activa.

Esta migración siembra v1 curada para AKI como punto de partida;
el Dr. puede iterar creando nuevas versiones vía la API de prompts.
"""

import uuid

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision = "010_seed_audit_checklists"
down_revision = "009"
branch_labels = None
depends_on = None


# Checklists en JSON. Estructura:
#   {
#     "version": 1,
#     "items": [
#       {"id": str, "fact": str, "keywords": [str, ...]},
#       ...
#     ]
#   }
# Matching v1: un hecho se considera PRESENTE si al menos una de sus
# keywords aparece (normalizada) en el contenido. Documentado como
# limitación v1 — no es NLP.

CHECKLIST_BMJ = """{
  "version": 1,
  "scope": "AKI / Insuficiencia Renal Aguda (fuentes tipo BMJ Best Practice / NICE CKS / Oxford Handbook)",
  "items": [
    {"id": "aki_def_oliguria", "fact": "Definición de oliguria (<0.5 mL/kg/h o <400 mL/día)", "keywords": ["oliguria", "0.5 ml/kg", "400 ml"]},
    {"id": "aki_def_anuria", "fact": "Definición de anuria (<100 mL/día)", "keywords": ["anuria", "100 ml"]},
    {"id": "kdigo_aumento_creatinina", "fact": "Criterio KDIGO: aumento creatinina >=0.3 mg/dL en 48h", "keywords": ["0.3 mg", "48 h", "kdigo"]},
    {"id": "kdigo_aumento_1_5_basal", "fact": "Criterio KDIGO: aumento >=1.5 veces la creatinina basal", "keywords": ["1.5 veces", "1.5x", "creatinina basal"]},
    {"id": "estadio_1", "fact": "Estadio 1 KDIGO (aumento 1.5-1.9x o >=0.3 mg/dL)", "keywords": ["estadio 1", "stage 1"]},
    {"id": "estadio_3", "fact": "Estadio 3 KDIGO (creatinina >=4.0 o inicio TRR)", "keywords": ["estadio 3", "stage 3", "4.0 mg"]},
    {"id": "etiologia_prerrenal", "fact": "Causas prerrenales (hipovolemia, ICC, sepsis)", "keywords": ["prerrenal", "pre-renal", "hipovolemia", "sepsis"]},
    {"id": "etiologia_postrenal", "fact": "Causas postrenales (obstrucción)", "keywords": ["postrenal", "post-renal", "obstrucción", "obstruction"]},
    {"id": "fena", "fact": "Fracción excretada de sodio (FENa) como diferencial", "keywords": ["fena", "fracción excretada de sodio"]},
    {"id": "furosemide_stress_test", "fact": "Furosemide Stress Test (FST) para predicción de progresión", "keywords": ["furosemide stress test", "fst"]}
  ]
}"""

CHECKLIST_GUIDELINE = """{
  "version": 1,
  "scope": "Guías completas (KDIGO 2026, NICE NG148, Renal Association)",
  "items": [
    {"id": "kdigo_def_aki", "fact": "Definición KDIGO 2026 de AKI", "keywords": ["kdigo 2026", "definición", "aki", "lra"]},
    {"id": "kdigo_estadificacion_completa", "fact": "Tabla de estadificación KDIGO completa (3 estadios)", "keywords": ["estadio 1", "estadio 2", "estadio 3", "stage 1", "stage 2", "stage 3"]},
    {"id": "causas_comunes_irc_aki", "fact": "Manejo de AKI sobre ERC (overlap)", "keywords": ["sobre erc", "sobre irc", "overlap", "aki on ckd"]},
    {"id": "criterios_dialisis_urgente_AEIOU", "fact": "Indicaciones urgentes de TRR / criterios AEIOU", "keywords": ["aeiou", "indicaciones urgentes", "diálisis urgente", "trr urgente"]},
    {"id": "fluidoterapia_cristaloides", "fact": "Comparativa de cristaloides (suero salino vs balanceados)", "keywords": ["cristaloides", "balanceados", "ringer", "plasma-lyte", "suero salino"]},
    {"id": "vasopresor_noradrenalina", "fact": "Noradrenalina como vasopresor de primera línea", "keywords": ["noradrenalina", "norepinephrine", "vasopresor"]},
    {"id": "dosis_dialisis_peritoneal", "fact": "Modalidades de TRR (hemodiálisis intermitente, continua, peritoneal)", "keywords": ["hemodiálisis", "diálisis peritoneal", "trr continua", "crrt"]},
    {"id": "manejo_pediatrico", "fact": "Manejo pediátrico de AKI con ajustes por peso/edad", "keywords": ["pediátrico", "pediatric", "peso", "edad"]},
    {"id": "manejo_gestante", "fact": "Manejo de AKI en embarazo", "keywords": ["embarazo", "gestante", "pregnancy"]},
    {"id": "contraste_yodado_prevencion", "fact": "Prevención de nefropatía por contraste", "keywords": ["contraste", "yodado", "nefropatía por contraste", "prevención"]},
    {"id": "iec_ara_ajuste", "fact": "Manejo de IECA/ARA en AKI (suspensión vs mantenimiento)", "keywords": ["ieca", "ara", "iECA", "ARA-II", "suspensión"]},
    {"id": "rampirad_hepat", "fact": "N-acetilcisteína y otras estrategias nefroprotectoras", "keywords": ["n-acetilcisteína", "nac", "nefroprotector"]}
  ]
}"""

CHECKLIST_ARTICLE = """{
  "version": 1,
  "scope": "Artículos de revista (Lancet, NEJM, JAMA, Nature)",
  "items": [
    {"id": "abstract_presente", "fact": "Abstract / resumen del artículo", "keywords": ["abstract", "resumen", "background", "objetivo"]},
    {"id": "metodos_resumen", "fact": "Sección de métodos (diseño, población, criterios de inclusión)", "keywords": ["métodos", "methods", "diseño", "design"]},
    {"id": "resultados_principales", "fact": "Resultados principales con cifras", "keywords": ["resultados", "results", "primary outcome"]},
    {"id": "conclusiones", "fact": "Conclusiones de los autores", "keywords": ["conclusiones", "conclusions", "interpretación"]},
    {"id": "cifras_mortalidad", "fact": "Cifras de mortalidad reportadas", "keywords": ["mortalidad", "mortality", "%"]},
    {"id": "limitaciones", "fact": "Limitaciones reconocidas por los autores", "keywords": ["limitaciones", "limitations"]}
  ]
}"""


def upgrade() -> None:
    bind = op.get_bind()
    for name, content, description in (
        (
            "audit_checklist_bmj",
            CHECKLIST_BMJ,
            "Checklist de hechos esperados (v1) para fuentes tipo BMJ/NICE CKS/Oxford Handbook",
        ),
        (
            "audit_checklist_guideline",
            CHECKLIST_GUIDELINE,
            "Checklist de hechos esperados (v1) para guías completas (KDIGO/NICE/Renal Association)",
        ),
        (
            "audit_checklist_article",
            CHECKLIST_ARTICLE,
            "Checklist de hechos esperados (v1) para artículos de revista",
        ),
    ):
        bind.execute(
            sa.text(
                "INSERT INTO prompt_templates (id, name, type, content, version, is_active, description, created_at, updated_at) "
                "VALUES (:id, :name, :type, :content, :version, :is_active, :description, NOW(), NOW())"
            ).bindparams(
                id=str(uuid.uuid4()),
                name=name,
                type="audit_checklist",
                content=content,
                version=1,
                is_active=True,
                description=description,
            )
        )


def downgrade() -> None:
    op.execute(
        "DELETE FROM prompt_templates WHERE name IN "
        "('audit_checklist_bmj', 'audit_checklist_guideline', 'audit_checklist_article')"
    )
