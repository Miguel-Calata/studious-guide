"""
ECOS_SECTION_TEMPLATE — slots de temas que cada sección del
compendio es dueña de desarrollar, agnóstico de patología.

El mini-prompt de auto-poblado (Tarea 3) toma este template + el
nombre de una patología y propone un primer borrador de ecos map
para esa patología. La restricción dura de "mención ≠ desarrollo"
se valida contra este template: cada slot debe estar cubierto en
EXACTAMENTE una sección dueña; las secciones anteriores la citan
como referencia cruzada pero no la desarrollan.
"""



# Cada slot es un identificador semántico del tema + una descripción
# que el mini-prompt usará como guía. Los slots son agnósticos de
# patología: aplican a cualquier compendio clínico del tipo de
# estructura de 11 secciones de SAM v9.
ECOS_SECTION_TEMPLATE: dict[int, list[dict]] = {
    1: [
        {
            "slot_id": "definicion",
            "label": "Definición clínica de la patología",
            "guidance": (
                "Definición operativa, sinonimia, criterios de "
                "inclusión/exclusión."
            ),
        },
        {
            "slot_id": "epidemiologia_cifras",
            "label": "Cifras de incidencia/prevalencia/mortalidad",
            "guidance": (
                "Cifras globales y por subpoblación con sus fuentes."
            ),
        },
        {
            "slot_id": "ambito_comunitario_vs_hospitalario",
            "label": "Distinción ámbito comunitario vs hospitalario",
            "guidance": (
                "Diferencias epidemiológicas y de manejo entre "
                "presentación extra e intrahospitalaria."
            ),
        },
    ],
    2: [
        {
            "slot_id": "criterios_diagnosticos",
            "label": "Criterios diagnósticos formales",
            "guidance": (
                "Criterios oficiales (KDIGO, NICE, guías "
                "especializadas) con tablas de estadificación."
            ),
        },
        {
            "slot_id": "clasificacion_etiologica",
            "label": "Clasificación etiológica",
            "guidance": (
                "Ejes principales de clasificación causal "
                "(p.ej. pre/intra/post)."
            ),
        },
        {
            "slot_id": "subclasificaciones",
            "label": "Subclasificaciones funcionales/estructurales",
            "guidance": (
                "Variantes reconocidas (p.ej. funcional vs "
                "estructural, neonatal, etc.)."
            ),
        },
    ],
    3: [
        {
            "slot_id": "mecanismo_molecular",
            "label": "Mecanismo molecular de cada fenotipo",
            "guidance": (
                "Fisiopatología biomolecular por fenotipo, con "
                "nexo a manifestaciones clínicas posteriores."
            ),
        },
    ],
    4: [
        {
            "slot_id": "historia_clinica_dirigida",
            "label": "Historia clínica dirigida y mnemotecnia",
            "guidance": (
                "Anamnesis estructurada con mnemotecnia propia "
                "de la patología."
            ),
        },
        {
            "slot_id": "examen_fisico_sistemas",
            "label": "Examen físico por sistemas",
            "guidance": (
                "Hallazgos físicos organizados por aparatos con "
                "tabla resumen."
            ),
        },
        {
            "slot_id": "evaluacion_volumen",
            "label": "Evaluación clínica del estado de volumen",
            "guidance": (
                "Tabla dicotómica hipovolemia vs sobrecarga."
            ),
        },
        {
            "slot_id": "casos_clinicos",
            "label": "Casos clínicos ilustrativos",
            "guidance": (
                "2-3 casos que anclen los hallazgos físicos y de "
                "historia a escenarios reales."
            ),
        },
    ],
    5: [
        {
            "slot_id": "algoritmo_diagnostico",
            "label": "Algoritmo diagnóstico + cruce de guías",
            "guidance": (
                "Pasos de confirmación diagnóstica con criterios, "
                "pruebas, y notas de divergencia entre guías."
            ),
        },
        {
            "slot_id": "uroanalisis_sedimento",
            "label": "Hallazgos de uroanálisis y sedimento",
            "guidance": (
                "Patrones de sedimento relevantes y su "
                "interpretación clínica."
            ),
        },
    ],
    6: [
        {
            "slot_id": "escalas_biomarcadores",
            "label": "Escalas y biomarcadores con datos operativos",
            "guidance": (
                "Escalas validadas con sensibilidad, especificidad, "
                "AUC, puntos de corte."
            ),
        },
        {
            "slot_id": "estres_farmacologico",
            "label": "Test de estrés farmacológico",
            "guidance": (
                "Pruebas dinámicas predictoras (p.ej. FST, "
                "test de captopril, etc.)."
            ),
        },
    ],
    7: [
        {
            "slot_id": "fluidoterapia",
            "label": "Fluidoterapia de resucitación",
            "guidance": (
                "Cristaloides vs coloides, balanceados vs salino, "
                "dosis y metas."
            ),
        },
        {
            "slot_id": "manejo_no_farmacologico",
            "label": "Manejo no farmacológico general",
            "guidance": (
                "Posición, oxigenoterapia, soporte ventilatorio "
                "no invasivo, monitorización."
            ),
        },
    ],
    8: [
        {
            "slot_id": "farmacologia_primera_linea",
            "label": "Farmacología de primera línea",
            "guidance": (
                "Fármacos principales con dosis, ajustes por "
                "función renal, contraindicaciones."
            ),
        },
        {
            "slot_id": "farmacologia_segunda_linea",
            "label": "Farmacología de segunda línea y adyuvante",
            "guidance": (
                "Alternativas, combinaciones y ajustes."
            ),
        },
        {
            "slot_id": "interacciones_ajustes",
            "label": "Interacciones y ajustes especiales",
            "guidance": (
                "Interacciones relevantes, ajustes en IR/IH, "
                "geriátricos, pediátricos."
            ),
        },
    ],
    9: [
        {
            "slot_id": "criterios_derivacion_trr",
            "label": "Criterios de derivación y TRR",
            "guidance": (
                "Cuándo derivar a especialista, indicaciones "
                "de terapia de reemplazo renal (urgentes y "
                "electivas), modalidades."
            ),
        },
        {
            "slot_id": "algoritmo_integrado",
            "label": "Algoritmo integrado de manejo",
            "guidance": (
                "Flujo completo de manejo integrando secciones "
                "previas."
            ),
        },
        {
            "slot_id": "manejo_urgencias",
            "label": "Manejo de urgencias específicas",
            "guidance": (
                "Escenarios agudos críticos y su abordaje."
            ),
        },
    ],
    10: [
        {
            "slot_id": "poblacion_pediatrica",
            "label": "Población pediátrica",
            "guidance": (
                "Ajustes por peso/edad, criterios pediátricos, "
                "evidencia específica."
            ),
        },
        {
            "slot_id": "poblacion_gestante",
            "label": "Población gestante",
            "guidance": (
                "Cambios fisiológicos, seguridad de fármacos, "
                "cuidados específicos."
            ),
        },
        {
            "slot_id": "poblacion_geriatrica",
            "label": "Población geriátrica",
            "guidance": (
                "Fragilidad, polifarmacia, comorbilidades, "
                "metas de tratamiento."
            ),
        },
        {
            "slot_id": "poblacion_con_comorbilidades",
            "label": "Pacientes con comorbilidades relevantes",
            "guidance": (
                "IRC, IH, ICC, inmunosupresión, etc."
            ),
        },
    ],
    11: [
        {
            "slot_id": "manejo_perioperatorio",
            "label": "Manejo perioperatorio",
            "guidance": (
                "Optimización preoperatoria, manejo "
                "intraoperatorio, cuidados postoperatorios."
            ),
        },
        {
            "slot_id": "interaccion_iec_ara",
            "label": "Manejo de IECA/ARA perioperatorio",
            "guidance": (
                "Suspensión vs mantenimiento según riesgo, "
                "guía por guía."
            ),
        },
        {
            "slot_id": "contraste_yodado",
            "label": "Prevención de nefropatía por contraste",
            "guidance": (
                "Estrategias de hidratación, profilaxis, "
                "monitorización."
            ),
        },
    ],
}


def all_template_slot_ids() -> set[str]:
    """Conjunto de todos los slot_id del template (para validación)."""
    out: set[str] = set()
    for slots in ECOS_SECTION_TEMPLATE.values():
        for slot in slots:
            out.add(slot["slot_id"])
    return out


def expected_owners() -> dict[str, int]:
    """
    Mapeo slot_id → sección dueña. Cada slot del template tiene
    exactamente una sección dueña; las secciones anteriores la
    referencian en sus ecos (R-1).
    """
    out: dict[str, int] = {}
    for section_number, slots in ECOS_SECTION_TEMPLATE.items():
        for slot in slots:
            out[slot["slot_id"]] = section_number
    return out
