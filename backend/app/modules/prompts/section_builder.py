from dataclasses import dataclass


@dataclass
class SectionConfig:
    section_number: int
    section_name: str
    next_section: str
    dosification_level: str
    dosification_desc: str
    motor: str
    ecos: list[str]
    is_cogeneration_pair: bool
    cogeneration_note: str | None


SECTION_CONFIGS: dict[int, SectionConfig] = {
    1: SectionConfig(
        section_number=1,
        section_name="DESCRIPCIÓN Y EPIDEMIOLOGÍA",
        next_section="2. CLASIFICACIÓN",
        dosification_level="🟢 ESTÁNDAR",
        dosification_desc="Epidemiología descriptiva. No requiere Extended Thinking.",
        motor="gemini",
        ecos=[],
        is_cogeneration_pair=False,
        cogeneration_note=None,
    ),
    2: SectionConfig(
        section_number=2,
        section_name="CLASIFICACIÓN",
        next_section="3. FISIOPATOLOGÍA",
        dosification_level="🟢 ESTÁNDAR",
        dosification_desc="Clasificación estructurada. No requiere Extended Thinking.",
        motor="gemini",
        ecos=[
            "Definición clínica de LRA, ERA y ERC (→ ver Descripción).",
            "Cifras de incidencia/mortalidad global (→ ver Epidemiología).",
            "Distinción LRA comunitaria vs. hospitalaria (→ ver Epidemiología).",
        ],
        is_cogeneration_pair=False,
        cogeneration_note=None,
    ),
    3: SectionConfig(
        section_number=3,
        section_name="FISIOPATOLOGÍA",
        next_section="4. CUADRO CLÍNICO",
        dosification_level="🔴 MÁXIMO",
        dosification_desc="Fisiopatología biomolecular. Activa Extended Thinking / Max Thinking.",
        motor="claude",
        ecos=[
            "Criterios diagnósticos KDIGO/NICE y tablas de estadificación (→ ver Clasificación).",
            "Criterios ERA funcionales y estructurales (→ ver Clasificación).",
            "Criterios neonatales C/U (→ ver Clasificación).",
            "Clasificación etiológica pre/intra/post-renal (→ ver Clasificación).",
            "Incidencia y mortalidad (→ ver Epidemiología).",
        ],
        is_cogeneration_pair=False,
        cogeneration_note=None,
    ),
    4: SectionConfig(
        section_number=4,
        section_name="CUADRO CLÍNICO",
        next_section="5. DIAGNÓSTICO",
        dosification_level="🟢 ESTÁNDAR",
        dosification_desc="Cuadro clínico con nexos. Pensamiento estándar-moderado.",
        motor="gemini",
        ecos=[
            "Criterios diagnósticos y estadificación (→ ver Clasificación).",
            "Mecanismo molecular de cada fenotipo (→ ver Fisiopatología).",
            "Datos epidemiológicos numéricos (→ ver Descripción y Epidemiología).",
            "Clasificación etiológica (→ ver Clasificación — mencionar categoría, no redefinir).",
        ],
        is_cogeneration_pair=True,
        cogeneration_note=(
            "\n⚡ AVISO LEY R-9 (CO-GENERACIÓN CLÍNICA):\n"
            "Esta es la sección CUADRO CLÍNICO. El prompt de DIAGNÓSTICO (05) se\n"
            "pegará en la MISMA conversación, a continuación. Al redactar esta sección,\n"
            "desarrolla con toda la exhaustividad la HC, examen físico, evaluación de\n"
            "volumen y casos clínicos — el Diagnóstico NO los repetirá.\n"
        ),
    ),
    5: SectionConfig(
        section_number=5,
        section_name="DIAGNÓSTICO",
        next_section="6. ESCALAS Y ESTRATIFICACIÓN",
        dosification_level="🔴 MÁXIMO",
        dosification_desc="Algoritmos diagnósticos + cruce de guías. Activa Extended Thinking.",
        motor="claude",
        ecos=[
            "Historia clínica dirigida y mnemotecnia FILTRO (→ ver Cuadro Clínico).",
            "Examen físico por sistemas y tabla Hipovolemia/Sobrecarga (→ ver Cuadro Clínico).",
            "Casos clínicos ilustrativos (→ ver Cuadro Clínico).",
            "Criterios diagnósticos KDIGO/NICE de LRA (→ ver Clasificación).",
            "Criterios ERA funcionales/estructurales (→ ver Clasificación).",
            "Criterios neonatales de LRA (→ ver Clasificación).",
            "Factores de riesgo generales (→ ver Cuadro Clínico o Escalas).",
        ],
        is_cogeneration_pair=True,
        cogeneration_note=(
            "\n⚡ AVISO LEY R-9 (CO-GENERACIÓN CLÍNICA):\n"
            "Esta es la sección DIAGNÓSTICO. Acabas de generar CUADRO CLÍNICO en este\n"
            "mismo chat. TODO el contenido de historia clínica, mnemotecnia FILTRO,\n"
            "examen físico, evaluación de estado de volumen y casos clínicos ya fue\n"
            "cubierto — aplica R-1 estrictamente. El Diagnóstico comienza DIRECTAMENTE en:\n"
            "  '¿Cómo confirmar y estadificar la LRA de forma analítica?'\n"
            "No reintroduces signos, síntomas, factores de riesgo ni criterios\n"
            "de estadificación (R-1 → ver Clasificación).\n"
        ),
    ),
    6: SectionConfig(
        section_number=6,
        section_name="ESCALAS Y ESTRATIFICACIÓN DE RIESGO",
        next_section="7. MANEJO NO FARMACOLÓGICO",
        dosification_level="🟡 ALTO",
        dosification_desc="Escalas con datos operativos. Pensamiento moderado-alto.",
        motor="gemini",
        ecos=[
            "Criterios diagnósticos formales de LRA (→ ver Clasificación).",
            "Evaluación del estado de volumen (→ ver Cuadro Clínico).",
            "Hallazgos del uroanálisis y sedimento urinario (→ ver Diagnóstico).",
            "Algoritmo diagnóstico diferencial (→ ver Diagnóstico).",
        ],
        is_cogeneration_pair=False,
        cogeneration_note=None,
    ),
    7: SectionConfig(
        section_number=7,
        section_name="MANEJO NO FARMACOLÓGICO",
        next_section="8. MANEJO FARMACOLÓGICO",
        dosification_level="🟢 ESTÁNDAR",
        dosification_desc="Manejo no farmacológico. Pensamiento estándar.",
        motor="gemini",
        ecos=[
            "Evaluación del estado de volumen y tabla Hipovolemia/Sobrecarga (→ ver Cuadro Clínico).",
            "Criterios de estadificación (→ ver Clasificación).",
            "Tabla de biomarcadores con AUC (→ ver Escalas).",
            "Furosemide Stress Test completo (→ ver Escalas — aquí solo citar el umbral).",
            "Algoritmo diagnóstico (→ ver Diagnóstico).",
        ],
        is_cogeneration_pair=False,
        cogeneration_note=None,
    ),
    8: SectionConfig(
        section_number=8,
        section_name="MANEJO FARMACOLÓGICO",
        next_section="9. PROTOCOLO INTEGRADO",
        dosification_level="🔴 MÁXIMO",
        dosification_desc="Farmacología multi-guía con dosis. Activa Extended Thinking / Max Thinking.",
        motor="claude",
        ecos=[
            "Fluidoterapia de resucitación con comparativa de cristaloides (→ ver Manejo No Farmacológico).",
            "Evaluación de estado de volumen (→ ver Cuadro Clínico).",
            "Indicaciones urgentes de TRR (→ ver Protocolo Integrado — anticipar referencia cruzada).",
            "Nexo fisiopatológico de los fármacos ya descrito (→ ver Fisiopatología — referenciar, no repetir).",
        ],
        is_cogeneration_pair=False,
        cogeneration_note=None,
    ),
    9: SectionConfig(
        section_number=9,
        section_name="PROTOCOLO INTEGRADO Y URGENCIAS",
        next_section="10. POBLACIONES ESPECIALES",
        dosification_level="🔴 MÁXIMO",
        dosification_desc="Cruce de todas las guías + urgencias. Activa Extended Thinking / Max Thinking.",
        motor="claude",
        ecos=[
            "Fluidoterapia detallada con comparativa de cristaloides (→ ver Manejo No Farmacológico).",
            "Tabla Hipovolemia/Sobrecarga (→ ver Cuadro Clínico).",
            "Furosemide Stress Test completo (→ ver Escalas).",
            "Farmacología detallada de cada fármaco con dosis (→ ver Manejo Farmacológico).",
            "Criterios neonatales/pediátricos (→ ver Clasificación o Poblaciones Especiales).",
        ],
        is_cogeneration_pair=False,
        cogeneration_note=None,
    ),
    10: SectionConfig(
        section_number=10,
        section_name="POBLACIONES ESPECIALES",
        next_section="11. PROTOCOLO PERIOPERATORIO",
        dosification_level="🟡 ALTO",
        dosification_desc="Subpoblaciones con ajustes específicos. Pensamiento moderado-alto.",
        motor="gemini",
        ecos=[
            "Criterios diagnósticos KDIGO generales (→ ver Clasificación — aplicar igual, señalar diferencias pediátricas).",
            "Escalas y biomarcadores en adultos (→ ver Escalas — señalar grado de evidencia distinto en niños).",
            "Furosemide Stress Test (→ ver Escalas; aquí solo indicar 2B pediátrico vs 2C adulto).",
            "Fluidoterapia general (→ ver Manejo No Farmacológico — aquí ajustar por peso/edad).",
            "Fragmentos de embarazo dispersos en secciones previas (CONSOLIDAR TODOS aquí).",
            "TRR: indicaciones generales (→ ver Protocolo Integrado — aquí modalidades pediátricas específicas).",
        ],
        is_cogeneration_pair=False,
        cogeneration_note=None,
    ),
    11: SectionConfig(
        section_number=11,
        section_name="PROTOCOLO PERIOPERATORIO",
        next_section="FIN DEL COMPENDIO",
        dosification_level="🟡 ALTO",
        dosification_desc="Protocolo perioperatorio con divergencias. Pensamiento moderado-alto.",
        motor="gemini",
        ecos=[
            "Fluidoterapia detallada con comparativa de cristaloides (→ ver Manejo No Farmacológico).",
            "Objetivo de PAM >65 mmHg (mencionar brevemente — detalle → ver Manejo No Farmacológico).",
            "Furosemide Stress Test completo (→ ver Escalas).",
            "Indicaciones urgentes de TRR (→ ver Protocolo Integrado).",
            "Farmacología detallada de IECA/ARA (→ ver Manejo Farmacológico — aquí solo mención perioperatoria).",
        ],
        is_cogeneration_pair=False,
        cogeneration_note=None,
    ),
}

DOSIFICATION_MAP = {
    "🟢 ESTÁNDAR": "STANDARD",
    "🟡 ALTO": "HIGH",
    "🔴 MÁXIMO": "MAX",
}


def _build_ecos_block(ecos: list[str]) -> str:
    if not ecos:
        return ""
    items = "\n".join(f"  - {eco}" for eco in ecos)
    return (
        f"\n──────────────────────────────────────────────────────────────\n"
        f"MAPA DE ECOS — CONTENIDO YA CUBIERTO (R-1: solo referencia cruzada):\n"
        f"{items}\n"
        f"──────────────────────────────────────────────────────────────\n"
    )


def _build_attachment_note(is_first: bool) -> str:
    if is_first:
        return (
            "\n📎 Adjunta los documentos fuente a esta conversación AHORA, "
            "antes de enviar este prompt (una sola vez para toda la sesión).\n"
        )
    return (
        "\n📎 Los documentos fuente YA están adjuntos desde el inicio de "
        "esta conversación — no los vuelvas a adjuntar.\n"
        "Esta es una SECCIÓN NUEVA del compendio, no una continuación "
        "de la sección anterior. Comienza directamente.\n"
    )


def _build_last_section_note(is_last: bool) -> str:
    if not is_last:
        return ""
    return (
        "\n⚠️ ESTA ES LA ÚLTIMA SECCIÓN DEL COMPENDIO.\n"
        "Al terminar el cuerpo de esta sección, genera el bloque\n"
        "## Referencias Bibliográficas con todas las fuentes del compendio.\n"
    )


def build_section_prompt(
    section_number: int,
    merged_content: str,
    pathology_name: str,
    source_filename: str,
    is_first: bool,
    is_last: bool,
    system_prompt: str,
    patch_gemini: str | None = None,
) -> str:
    config = SECTION_CONFIGS[section_number]

    prefix = ""
    if config.motor == "gemini" and patch_gemini:
        prefix = patch_gemini.strip() + "\n\n"

    ecos_block = _build_ecos_block(config.ecos)
    cogen_note = config.cogeneration_note or ""
    attachment_note = _build_attachment_note(is_first)
    last_note = _build_last_section_note(is_last)
    thinking_note = (
        "  (Extended Thinking / Max Thinking)"
        if "🔴" in config.dosification_level
        else ""
    )

    prompt = (
        f"{prefix}"
        f"{system_prompt.strip()}\n\n"
        f"{'=' * 70}\n"
        f"INSTRUCCIÓN DE SESIÓN — SAM v9\n"
        f"{'=' * 70}\n\n"
        f"PATOLOGÍA : {pathology_name}\n"
        f"FUENTE(S) : {source_filename}\n"
        f"MOTOR     : {config.motor}{thinking_note}\n"
        f"{attachment_note}\n"
        f"SECCIÓN A DESARROLLAR : {config.section_name}\n"
        f"SECCIÓN SIGUIENTE     : {config.next_section}\n\n"
        f"DOSIFICACIÓN DEL RAZONAMIENTO PARA ESTA SECCIÓN:\n"
        f"  {config.dosification_level} — {config.dosification_desc}\n"
        f"{ecos_block}"
        f"{cogen_note}"
        f"{last_note}\n"
        f"INSTRUCCIÓN: Desarrolla ÚNICAMENTE la sección \"{config.section_name}\" del\n"
        f"compendio, usando exclusivamente los documentos adjuntos. No incluyas\n"
        f"contenido de otras secciones del compendio.\n\n"
        f"{'=' * 70}\n"
        f"COMIENZA AHORA: {config.section_name}\n"
        f"{'=' * 70}\n"
    )
    return prompt
