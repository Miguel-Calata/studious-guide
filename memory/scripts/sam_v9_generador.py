"""
SAM v9 — GENERADOR DE PROMPTS
Basado en SAM v8 + Auditoría Magistral del Compendio AKI
======================================================================
Cambios vs v8:
  1. SYSTEM_PROMPT reescrito con 5 Pilares y 10 Leyes Absolutas.
  2. LEY R-1 (Avance Cronológico): MAPA_ECOS por sección — cada prompt
     sabe exactamente qué contenido ya se cubrió y NO puede repetir.
  3. LEY R-2 (Anti Name-Dropping): la fuente es SIEMPRE sujeto cero.
  4. LEY R-3 (Mnemotecnia): listas ≥4 ítems → acrónimo obligatorio.
  5. LEY R-4 (Orden Visual): examen físico / HC siempre en categorías
     en negrita + tabla resumen, nunca párrafo corrido.
  6. LEY R-5 (Dominio del Especialista): callout ⚠️ para controversias
     académicas que no cambian la conducta de 1er nivel.
  7. LEY R-6 (Tabla Accionable): máx. 4 columnas, al menos una de conducta.
  8. LEY R-7 (Callout Nativo): 6 tipos de callout en formato >, nunca prosa.
  9. LEY R-8 (Citación por Bloque): tabla de una sola fuente → cita única.
 10. LEY R-9 (Co-generación): Cuadro Clínico (04) y Diagnóstico (05)
     se generan en la MISMA sesión consecutiva.
 11. LEY R-10 (Límite de Párrafo): ningún párrafo supera 4 líneas.
 12. DOSIFICACION_RAZONAMIENTO: indicador por sección (🔴 MAX / 🟡 ALTO / 🟢).
 13. Workflow bifurcado Gemini / Claude con PARCHE recordado en el output.

NO cambia: extracción sigue preservando estructura nativa de cada fuente.
"""

import re
from pathlib import Path

CARPETA_MD = Path("markdowns")
CARPETA_MD.mkdir(exist_ok=True)
CARPETA_PROMPTS = Path("prompts_generados")
CARPETA_PROMPTS.mkdir(exist_ok=True)

SECCIONES = {
    "1":  ("DESCRIPCIÓN Y EPIDEMIOLOGÍA",        "2. CLASIFICACIÓN"),
    "2":  ("CLASIFICACIÓN",                       "3. FISIOPATOLOGÍA"),
    "3":  ("FISIOPATOLOGÍA",                      "4. CUADRO CLÍNICO"),
    "4":  ("CUADRO CLÍNICO",                      "5. DIAGNÓSTICO"),
    "5":  ("DIAGNÓSTICO",                         "6. ESCALAS Y ESTRATIFICACIÓN"),
    "6":  ("ESCALAS Y ESTRATIFICACIÓN DE RIESGO", "7. MANEJO NO FARMACOLÓGICO"),
    "7":  ("MANEJO NO FARMACOLÓGICO",             "8. MANEJO FARMACOLÓGICO"),
    "8":  ("MANEJO FARMACOLÓGICO",                "9. PROTOCOLO INTEGRADO"),
    "9":  ("PROTOCOLO INTEGRADO Y URGENCIAS",     "10. POBLACIONES ESPECIALES"),
    "10": ("POBLACIONES ESPECIALES",              "11. PROTOCOLO PERIOPERATORIO"),
    "11": ("PROTOCOLO PERIOPERATORIO",            "FIN DEL COMPENDIO"),
}

# ── DOSIFICACIÓN DEL RAZONAMIENTO POR SECCIÓN ────────────────────────────────
# 🔴 MAX = Extended Thinking activado (Fisiopatología, Farmacología, Protocolos)
# 🟡 ALTO = Pensamiento moderado-alto (Diagnóstico, Escalas, Perioperatorio)
# 🟢 ESTÁNDAR = Sin Extended Thinking (secciones descriptivas/estructurales)
DOSIFICACION = {
    "1":  ("🟢 ESTÁNDAR",
           "Epidemiología descriptiva. No requiere Extended Thinking."),
    "2":  ("🟢 ESTÁNDAR",
           "Clasificación estructurada. No requiere Extended Thinking."),
    "3":  ("🔴 MÁXIMO",
           "Fisiopatología biomolecular. Activa Extended Thinking / Max Thinking."),
    "4":  ("🟢 ESTÁNDAR",
           "Cuadro clínico con nexos. Pensamiento estándar-moderado."),
    "5":  ("🔴 MÁXIMO",
           "Algoritmos diagnósticos + cruce de guías. Activa Extended Thinking."),
    "6":  ("🟡 ALTO",
           "Escalas con datos operativos. Pensamiento moderado-alto."),
    "7":  ("🟢 ESTÁNDAR",
           "Manejo no farmacológico. Pensamiento estándar."),
    "8":  ("🔴 MÁXIMO",
           "Farmacología multi-guía con dosis. Activa Extended Thinking / Max Thinking."),
    "9":  ("🔴 MÁXIMO",
           "Cruce de todas las guías + urgencias. Activa Extended Thinking / Max Thinking."),
    "10": ("🟡 ALTO",
           "Subpoblaciones con ajustes específicos. Pensamiento moderado-alto."),
    "11": ("🟡 ALTO",
           "Protocolo perioperatorio con divergencias. Pensamiento moderado-alto."),
}

# ── MOTOR RECOMENDADO POR SECCIÓN ─────────────────────────────────────────────
# Gemini: secciones descriptivas sin riesgo de límite de cuota
# Claude: secciones de alta densidad clínica con Extended Thinking
MOTOR = {
    "1": "Gemini", "2": "Gemini", "3": "Claude", "4": "Gemini",
    "5": "Claude", "6": "Gemini", "7": "Gemini", "8": "Claude",
    "9": "Claude", "10": "Gemini", "11": "Gemini",
}

# ── MAPA DE ECOS: contenido ya cubierto en secciones anteriores ──────────────
# Cada entrada = lista de lo que el modelo NO puede repetir, solo referenciar
MAPA_ECOS = {
    "1": [],  # Primera sección — sin ecos previos
    "2": [
        "Definición clínica de LRA, ERA y ERC (→ ver Descripción).",
        "Cifras de incidencia/mortalidad global (→ ver Epidemiología).",
        "Distinción LRA comunitaria vs. hospitalaria (→ ver Epidemiología).",
    ],
    "3": [
        "Criterios diagnósticos KDIGO/NICE y tablas de estadificación (→ ver Clasificación).",
        "Criterios ERA funcionales y estructurales (→ ver Clasificación).",
        "Criterios neonatales C/U (→ ver Clasificación).",
        "Clasificación etiológica pre/intra/post-renal (→ ver Clasificación).",
        "Incidencia y mortalidad (→ ver Epidemiología).",
    ],
    "4": [
        "Criterios diagnósticos y estadificación (→ ver Clasificación).",
        "Mecanismo molecular de cada fenotipo (→ ver Fisiopatología).",
        "Datos epidemiológicos numéricos (→ ver Descripción y Epidemiología).",
        "Clasificación etiológica (→ ver Clasificación — mencionar categoría, no redefinir).",
    ],
    "5": [
        "Historia clínica dirigida y mnemotecnia FILTRO (→ ver Cuadro Clínico).",
        "Examen físico por sistemas y tabla Hipovolemia/Sobrecarga (→ ver Cuadro Clínico).",
        "Casos clínicos ilustrativos (→ ver Cuadro Clínico).",
        "Criterios diagnósticos KDIGO/NICE de LRA (→ ver Clasificación).",
        "Criterios ERA funcionales/estructurales (→ ver Clasificación).",
        "Criterios neonatales de LRA (→ ver Clasificación).",
        "Factores de riesgo generales (→ ver Cuadro Clínico o Escalas).",
    ],
    "6": [
        "Criterios diagnósticos formales de LRA (→ ver Clasificación).",
        "Evaluación del estado de volumen (→ ver Cuadro Clínico).",
        "Hallazgos del uroanálisis y sedimento urinario (→ ver Diagnóstico).",
        "Algoritmo diagnóstico diferencial (→ ver Diagnóstico).",
    ],
    "7": [
        "Evaluación del estado de volumen y tabla Hipovolemia/Sobrecarga (→ ver Cuadro Clínico).",
        "Criterios de estadificación (→ ver Clasificación).",
        "Tabla de biomarcadores con AUC (→ ver Escalas).",
        "Furosemide Stress Test completo (→ ver Escalas — aquí solo citar el umbral).",
        "Algoritmo diagnóstico (→ ver Diagnóstico).",
    ],
    "8": [
        "Fluidoterapia de resucitación con comparativa de cristaloides (→ ver Manejo No Farmacológico).",
        "Evaluación de estado de volumen (→ ver Cuadro Clínico).",
        "Indicaciones urgentes de TRR (→ ver Protocolo Integrado — anticipar referencia cruzada).",
        "Nexo fisiopatológico de los fármacos ya descrito (→ ver Fisiopatología — referenciar, no repetir).",
    ],
    "9": [
        "Fluidoterapia detallada con comparativa de cristaloides (→ ver Manejo No Farmacológico).",
        "Tabla Hipovolemia/Sobrecarga (→ ver Cuadro Clínico).",
        "Furosemide Stress Test completo (→ ver Escalas).",
        "Farmacología detallada de cada fármaco con dosis (→ ver Manejo Farmacológico).",
        "Criterios neonatales/pediátricos (→ ver Clasificación o Poblaciones Especiales).",
    ],
    "10": [
        "Criterios diagnósticos KDIGO generales (→ ver Clasificación — aplicar igual, señalar diferencias pediátricas).",
        "Escalas y biomarcadores en adultos (→ ver Escalas — señalar grado de evidencia distinto en niños).",
        "Furosemide Stress Test (→ ver Escalas; aquí solo indicar 2B pediátrico vs 2C adulto).",
        "Fluidoterapia general (→ ver Manejo No Farmacológico — aquí ajustar por peso/edad).",
        "Fragmentos de embarazo dispersos en secciones previas (CONSOLIDAR TODOS aquí).",
        "TRR: indicaciones generales (→ ver Protocolo Integrado — aquí modalidades pediátricas específicas).",
    ],
    "11": [
        "Fluidoterapia detallada con comparativa de cristaloides (→ ver Manejo No Farmacológico).",
        "Objetivo de PAM >65 mmHg (mencionar brevemente — detalle → ver Manejo No Farmacológico).",
        "Furosemide Stress Test completo (→ ver Escalas).",
        "Indicaciones urgentes de TRR (→ ver Protocolo Integrado).",
        "Farmacología detallada de IECA/ARA (→ ver Manejo Farmacológico — aquí solo mención perioperatoria).",
    ],
}

# ── SYSTEM PROMPT SAM v9 ──────────────────────────────────────────────────────
SYSTEM_PROMPT = """\
[SYSTEM — SAM v9 — CATEDRÁTICO CLÍNICO — 5 PILARES, 10 LEYES ABSOLUTAS]

Eres SAM, Catedrático de Medicina Interna y narrador clínico de élite.
Tu misión: usando ÚNICAMENTE los documentos adjuntos a esta conversación,
escribe un capítulo magistral de compendio médico estilo Washington Manual
para la sección indicada. Destinatario: residente de medicina interna
preparando examen de alta densidad (ENARM / USMLE / UKMLA).

╔══════════════════════════════════════════════════════════════╗
║  PILAR I — HERMETISMO Y HONESTIDAD DOCUMENTAL               ║
╚══════════════════════════════════════════════════════════════╝

REGLA DE HERMETISMO ABSOLUTO:
Toda afirmación, valor numérico, dosis, criterio o referencia visual debe
provenir EXCLUSIVAMENTE de los documentos adjuntos. Nunca uses conocimiento
externo. Cada afirmación lleva su cita inline: [KDIGO 2026], [NICE NG148],
[BMJ], [Lancet 2025], [Renal Association], [Nature Reviews 2021], [Kidney
Medicine], etc. Cita la fuente exacta de donde proviene el dato.

PROTOCOLO DE VACÍO DOCUMENTAL:
Si las fuentes adjuntas no cubren un punto de esta sección, NUNCA inventes
y NUNCA te quedes en silencio sin explicar por qué. Desarrolla la sección
con lo disponible y declara al final de esa subsección:
  *"Las fuentes primarias no ofrecen datos sustanciales para este punto."*

╔══════════════════════════════════════════════════════════════╗
║  PILAR II — LAS 10 LEYES ABSOLUTAS DE SAM v9               ║
╚══════════════════════════════════════════════════════════════╝

R-1 | LEY DEL AVANCE CRONOLÓGICO ESTRICTO
Si un concepto fue definido en una sección anterior del compendio
(se te indica cuáles en el bloque MAPA DE ECOS del prompt de sesión),
en esta sección SOLO aparece como referencia cruzada de una línea:
  `→ Ver [Nombre de Sección].`
PROHIBIDO redefinir, resumir o "recordar al lector" en prosa.

R-2 | LEY ANTI NAME-DROPPING
La fuente es SIEMPRE sujeto gramatical CERO. El dato clínico va primero.
✅ `Inicio precoz de TRR no reduce mortalidad vs tardío (1A) [KDIGO 2026].`
❌ `La guía KDIGO 2026 recomienda que el inicio precoz de TRR...`
El nombre de la guía en corchetes al final de la afirmación, nunca antes.

R-3 | LEY DE LA MNEMOTECNIA
Toda lista de ≥4 ítems que NO sea una tabla de datos numéricos DEBE tener
un acrónimo o mnemotecnia en español ANTES de presentarse como lista.
Formato obligatorio en callout:
  `> 🔑 **[SIGLA]** = **[S]**ignificado · **[I]**gual · **[G]**uía...`

R-4 | LEY DEL ORDEN VISUAL POR SISTEMAS
El examen físico, historia clínica por aparatos y factores de riesgo se
estructuran SIEMPRE con categorías en **negrita** + tabla resumen final.
Orden estándar: **Hemodinámico** → **Perfusión** → **Mucocutáneo** →
**Cardiopulmonar** → **Sobrecarga** → **Especial** (pediátrico, etc.).
PROHIBIDO el párrafo corrido para listar hallazgos físicos o síntomas.

R-5 | LEY DEL DOMINIO DEL ESPECIALISTA
Toda controversia académica, índice con múltiples variables de confusión
o herramienta subespecializada que NO cambie la conducta del residente
en 1er nivel → reducir a callout ⚠️ de 2–3 líneas máximo.
NUNCA desarrollar como sección completa con datos crudos.
✅ Aplica a: FeNa/FeUrea (confundidores múltiples), subfenotipado
   molecular, modelos predictivos con AUC-ROC crudos, genómica renal.

R-6 | LEY DE LA TABLA ACCIONABLE
Las tablas tienen máximo 4 columnas. Al menos UNA columna debe contener
[Conducta], [Acción] o equivalente orientado a decisión clínica.
EXCEPCIÓN ÚNICA: tablas epidemiológicas multi-fuente (hasta 5 columnas).

R-7 | LEY DEL CALLOUT NATIVO (6 TIPOS OBLIGATORIOS)
Los siguientes elementos van SIEMPRE en formato callout `>`, NUNCA prosa:

  > 🔬 **Nexo Básico-Clínico:** [Mecanismo molecular] → [Hallazgo clínico] → [Implicación terapéutica]
  > 💡 **Perla Clínica:** [Tip de 1–2 líneas para urgencias / 1er nivel]
  > ⚠️ **Dominio del Especialista:** [Contexto en 2–3 líneas; redirige a especialista]
  > 📋 **Nota de divergencia:** [Guía A] recomienda [X] [cita A], mientras que [Guía B] recomienda [Y] [cita B]. No se promedian.
  > 🩺 **Caso clínico:** [Presentación 2–3 líneas + dato clave diagnóstico o terapéutico]
  > 🔑 **Mnemotecnia [SIGLA]:** [S]ignificado · [I]gual · ...

R-8 | LEY DE LA CITACIÓN POR BLOQUE
Cuando una tabla completa proviene de UNA sola fuente → citar UNA VEZ
debajo de la tabla: `*Adaptado de [Fuente].*`
PROHIBIDO poner [Fuente] en cada fila de la tabla.

R-9 | LEY DE CO-GENERACIÓN CLÍNICA
Las secciones CUADRO CLÍNICO (4) y DIAGNÓSTICO (5) se generan en la
MISMA conversación, en prompts consecutivos, para que R-1 funcione en
tiempo real entre ellas. Se te indicará cuándo aplica.

R-10 | LEY DEL LÍMITE DE PÁRRAFO
Ningún párrafo de prosa supera 4 líneas de texto. Si supera → convierte
en bullets, tabla o callout según el tipo de contenido.

╔══════════════════════════════════════════════════════════════╗
║  PILAR III — SÍNTESIS ENTRE GUÍAS                          ║
╚══════════════════════════════════════════════════════════════╝

Cuando dos o más fuentes coinciden → sintetiza sin redundancia, cita ambas:
  `[KDIGO 2026; Lancet 2025]`
Cuando dos fuentes DIFIEREN en dosis, umbral o recomendación → usa
el callout 📋 Nota de divergencia (R-7). NUNCA promediar ni elegir una.

╔══════════════════════════════════════════════════════════════╗
║  PILAR IV — DENSIDAD HIGH-YIELD Y CITACIÓN GRANULAR        ║
╚══════════════════════════════════════════════════════════════╝

DENSIDAD HIGH-YIELD:
- Cero preámbulo literario — entra directo al contenido.
- Si comparas ≥2 elementos en ≥2 parámetros → tabla obligatoria (R-6).
- ANTI-REDUNDANCIA: aplica R-1 sin excepción — el MAPA DE ECOS te indica
  exactamente qué temas ya se cubrieron.
- EXHAUSTIVIDAD MICRO-CLÍNICA: nunca omitas subpoblaciones mencionadas
  en las fuentes (neonatos, embarazadas, geriátricos, IR/IH) ni cifras
  específicas por guía individual.

CITACIÓN GRANULAR INMEDIATA (no negociable):
✅ `Mortalidad hospitalaria: >20% [BMJ], 23% [Nature Reviews 2021], >30% [Renal Association].`
❌ `Mortalidad del 20-30% [BMJ, Nature, Renal Association].`
Cada cifra divergente va pegada a SU cita, no todas agrupadas al final.

PROTOCOLO ANTI-COMPRESIÓN:
Si el contenido es extenso, divide en partes. Al terminar cada parte:
  `[Fin de la Parte N — Escribe "Continúa" para seguir]`
Esto es SOLO para cuando ESTA MISMA sección no cabe en un mensaje.
NUNCA para invitar a la sección siguiente del compendio.

╔══════════════════════════════════════════════════════════════╗
║  PILAR V — FORMATO Y ARQUITECTURA                          ║
╚══════════════════════════════════════════════════════════════╝

FORMATO COMPATIBLE NOTION:
- Usa: ## ### #### párrafos tablas Markdown **negrita** _cursiva_ > callouts
- PROHIBIDO: líneas horizontales (--- === *** ━), HTML crudo,
  bloques de código para texto clínico narrativo.
- Emojis solo en callouts definidos en R-7 y 👁️ para referencias visuales.
- Las tablas de las fuentes se REPRODUCEN COMPLETAS, nunca abreviadas.

ARQUITECTURA DE CADA SECCIÓN:
1. Apertura (1–2 oraciones): puente breve desde la sección anterior
2. Cuerpo: narrativa + tablas + callouts según las 10 Leyes
3. Nexo 🔬 (en Fisiopatología, Diagnóstico y Farmacología)
4. Síntesis de cierre (2–4 oraciones)

BIBLIOGRAFÍA: solo en la ÚLTIMA sección del compendio, cuando se indique
"ES LA ÚLTIMA SECCIÓN". Formato:
  ## Referencias Bibliográficas
  Lista numerada por documento fuente.
"""


def listar_markdowns() -> list[Path]:
    archivos = sorted(CARPETA_MD.glob("*.md"))
    if not archivos:
        print("\n❌ No hay archivos .md en markdowns/")
    return archivos


def extraer_patologia(ruta: Path) -> str:
    contenido = ruta.read_text(encoding="utf-8", errors="ignore")[:500]
    match = re.search(r"#\s+(.+)", contenido)
    return match.group(1).strip() if match else ruta.stem


def construir_bloque_ecos(num_seccion: str) -> str:
    """Genera el bloque MAPA DE ECOS para el prompt de sesión."""
    ecos = MAPA_ECOS.get(num_seccion, [])
    if not ecos:
        return ""
    lineas = "\n".join(f"  - {eco}" for eco in ecos)
    return (
        f"\n──────────────────────────────────────────────────────────────\n"
        f"MAPA DE ECOS — CONTENIDO YA CUBIERTO (R-1: solo referencia cruzada):\n"
        f"{lineas}\n"
        f"──────────────────────────────────────────────────────────────\n"
    )


def construir_nota_cogeneracion(num_seccion: str) -> str:
    """Instrucción explícita para la co-generación de secciones 4 y 5 (R-9)."""
    if num_seccion == "4":
        return (
            "\n⚡ AVISO LEY R-9 (CO-GENERACIÓN CLÍNICA):\n"
            "Esta es la sección CUADRO CLÍNICO. El prompt de DIAGNÓSTICO (05) se\n"
            "pegará en la MISMA conversación, a continuación. Al redactar esta sección,\n"
            "desarrolla con toda la exhaustividad la HC, examen físico, evaluación de\n"
            "volumen y casos clínicos — el Diagnóstico NO los repetirá.\n"
        )
    elif num_seccion == "5":
        return (
            "\n⚡ AVISO LEY R-9 (CO-GENERACIÓN CLÍNICA):\n"
            "Esta es la sección DIAGNÓSTICO. Acabas de generar CUADRO CLÍNICO en este\n"
            "mismo chat. TODO el contenido de historia clínica, mnemotecnia FILTRO,\n"
            "examen físico, evaluación de estado de volumen y casos clínicos ya fue\n"
            "cubierto — aplica R-1 estrictamente. El Diagnóstico comienza DIRECTAMENTE en:\n"
            "  '¿Cómo confirmar y estadificar la LRA de forma analítica?'\n"
            "No reintroduces signos, síntomas, factores de riesgo ni criterios\n"
            "de estadificación (R-1 → ver Clasificación).\n"
        )
    return ""


def construir_prompt_corto(nombre_archivo: str, patologia: str,
                            num_seccion: str, es_primera: bool,
                            es_ultima: bool) -> str:
    nombre_seccion, seccion_siguiente = SECCIONES[num_seccion]
    indicador_dos, descripcion_dos = DOSIFICACION[num_seccion]
    motor = MOTOR[num_seccion]
    bloque_ecos = construir_bloque_ecos(num_seccion)
    nota_cogen = construir_nota_cogeneracion(num_seccion)

    if es_primera:
        aviso_adjunto = (
            "\n📎 Adjunta los documentos fuente a esta conversación AHORA, "
            "antes de enviar este prompt (una sola vez para toda la sesión).\n"
        )
    else:
        aviso_adjunto = (
            "\n📎 Los documentos fuente YA están adjuntos desde el inicio de "
            "esta conversación — no los vuelvas a adjuntar.\n"
            "Esta es una SECCIÓN NUEVA del compendio, no una continuación "
            "de la sección anterior. Comienza directamente.\n"
        )

    aviso_ultima = ""
    if es_ultima:
        aviso_ultima = (
            "\n⚠️ ESTA ES LA ÚLTIMA SECCIÓN DEL COMPENDIO.\n"
            "Al terminar el cuerpo de esta sección, genera el bloque\n"
            "## Referencias Bibliográficas con todas las fuentes del compendio.\n"
        )

    return (
        f"{SYSTEM_PROMPT.strip()}\n\n"
        f"{'='*70}\n"
        f"INSTRUCCIÓN DE SESIÓN — SAM v9\n"
        f"{'='*70}\n\n"
        f"PATOLOGÍA : {patologia}\n"
        f"FUENTE(S) : {nombre_archivo}\n"
        f"MOTOR     : {motor}  "
        f"{'(Extended Thinking / Max Thinking)' if '🔴' in indicador_dos else ''}\n"
        f"{aviso_adjunto}\n"
        f"SECCIÓN A DESARROLLAR : {nombre_seccion}\n"
        f"SECCIÓN SIGUIENTE     : {seccion_siguiente}\n\n"
        f"DOSIFICACIÓN DEL RAZONAMIENTO PARA ESTA SECCIÓN:\n"
        f"  {indicador_dos} — {descripcion_dos}\n"
        f"{bloque_ecos}"
        f"{nota_cogen}"
        f"{aviso_ultima}\n"
        f"INSTRUCCIÓN: Desarrolla ÚNICAMENTE la sección \"{nombre_seccion}\" del\n"
        f"compendio, usando exclusivamente los documentos adjuntos. No incluyas\n"
        f"contenido de otras secciones del compendio.\n\n"
        f"{'='*70}\n"
        f"COMIENZA AHORA: {nombre_seccion}\n"
        f"{'='*70}\n"
    )


def guardar_prompt(texto: str, patologia: str, num_seccion: str,
                   nombre_seccion: str) -> Path:
    nombre_limpio = re.sub(r'[^a-z0-9]', '_',
        patologia.lower()
        .replace('á', 'a').replace('é', 'e').replace('í', 'i')
        .replace('ó', 'o').replace('ú', 'u').replace('ñ', 'n')
    )[:35].strip('_')

    carpeta_pat = CARPETA_PROMPTS / nombre_limpio
    carpeta_pat.mkdir(exist_ok=True, parents=True)

    nombre_seccion_limpio = re.sub(r'[^a-z0-9]', '_', nombre_seccion.lower())[:30]
    nombre_archivo = f"{num_seccion.zfill(2)}_{nombre_seccion_limpio}_PROMPT.txt"
    ruta_salida = carpeta_pat / nombre_archivo
    ruta_salida.write_text(texto, encoding="utf-8")
    return ruta_salida


def mostrar_menu_secciones() -> str:
    print("\n── SECCIONES DEL COMPENDIO ─────────────────────────────────────")
    for num, (nombre, _) in SECCIONES.items():
        indicador, _ = DOSIFICACION[num]
        motor = MOTOR[num]
        motor_str = f"[{motor}]"
        print(f"  {num:>2}. {nombre:<42} {indicador} {motor_str}")
    print("   0. Generar TODAS las secciones en orden")
    print("────────────────────────────────────────────────────────────────")
    print("  🔴 MAX = Extended Thinking activo  |  🟡 ALTO  |  🟢 Estándar")
    while True:
        eleccion = input("\nElige una opción: ").strip()
        if eleccion == "0":
            return "todas"
        if eleccion in SECCIONES:
            return eleccion
        print("  Opción no válida.")


def main():
    print("\n" + "=" * 62)
    print("   SAM v9 — 10 Leyes Absolutas + Mapa de Ecos + Callouts")
    print("=" * 62)

    archivos = listar_markdowns()
    if not archivos:
        return

    print("\n── ARCHIVOS DISPONIBLES ────────────────────────────────────────")
    for i, a in enumerate(archivos, 1):
        tam_kb = a.stat().st_size / 1024
        print(f"  {i}. {a.name}  ({tam_kb:,.0f} KB)")
    print("────────────────────────────────────────────────────────────────")

    while True:
        try:
            idx = int(input("\nElige el archivo (número): ")) - 1
            if 0 <= idx < len(archivos):
                ruta_md = archivos[idx]
                break
            print("  Número fuera de rango.")
        except ValueError:
            print("  Ingresa un número válido.")

    patologia = extraer_patologia(ruta_md)
    print(f"\n  PATOLOGÍA DETECTADA: {patologia}")
    print("=" * 62)

    eleccion = mostrar_menu_secciones()
    nums_a_generar = list(SECCIONES.keys()) if eleccion == "todas" else [eleccion]
    primera_seccion = nums_a_generar[0]
    ultima_seccion = list(SECCIONES.keys())[-1]

    total = len(nums_a_generar)
    for i, num in enumerate(nums_a_generar, 1):
        nombre_sec = SECCIONES[num][0]
        es_primera = (num == primera_seccion)
        es_ultima = (num == ultima_seccion)
        print(f"\n[{i}/{total}] Generando: {nombre_sec}...")

        prompt = construir_prompt_corto(
            ruta_md.name, patologia, num, es_primera, es_ultima
        )
        ruta_salida = guardar_prompt(prompt, patologia, num, nombre_sec)
        print(f"  ✅ {ruta_salida}")

    # ── Resumen del flujo v9 ──────────────────────────────────────────────
    print("\n" + "=" * 62)
    print("LISTO — Flujo SAM v9 (workflow bifurcado):")
    print()
    print("  SESIÓN GEMINI (01, 02, 04, 06, 07, 10, 11):")
    print(f"    1. Chat nuevo en Gemini 2.5 Pro")
    print(f"    2. Adjunta {ruta_md.name} UNA SOLA VEZ")
    print("    3. Pega PARCHE_GEMINI_V9.txt ANTES del primer prompt")
    print("    4. Pega los prompts 01, 02, 04, 06, 07, 10, 11 en orden")
    print()
    print("  SESIÓN CLAUDE (03, 05, 08, 09):")
    print("    1. Chat nuevo en Claude")
    print(f"    2. Adjunta {ruta_md.name} UNA SOLA VEZ")
    print("    3. Secciones 🔴 MAX → activa Extended Thinking")
    print("    4. Pega los prompts 03, 05, 08, 09 en orden")
    print()
    if eleccion == "todas" or ("4" in nums_a_generar and "5" in nums_a_generar):
        print("  ⚡ LEY R-9: Los prompts 04 y 05 van en la MISMA sesión")
        print("     (Gemini para el 04, Claude para el 05).")
        print("     Si bifurcas motores: genera 04 en Gemini, guarda la")
        print("     respuesta; luego en Claude pega el contexto de cuadro")
        print("     clínico antes del prompt 05, o usa Claude para ambos.")
    print("=" * 62 + "\n")


if __name__ == "__main__":
    main()
