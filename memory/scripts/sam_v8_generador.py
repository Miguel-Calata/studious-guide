"""
SAM v8 — GENERADOR DE PROMPTS (con protocolo de vacío documental
y principio High-Yield, manteniendo estructura nativa en extracción)
======================================================================
Cambios vs v7:
  1. Corrige la ambigüedad "Continúa hacia la siguiente sección" —
     ahora cada prompt aclara explícitamente que es una sección NUEVA.
  2. Refleja el flujo correcto: UNA conversación por patología, los
     documentos se adjuntan una sola vez al inicio (no se resuben).
  3. Agrega Protocolo de Vacío Documental: honestidad explícita
     cuando las fuentes no cubren bien una sección, en vez de
     inventar o quedarse en silencio sin explicar por qué.
  4. Agrega Principio de Redacción High-Yield: anti-redundancia
     entre secciones, exhaustividad de subpoblaciones y cifras
     específicas de guías, cero preámbulo literario innecesario.

NO cambia: la extracción sigue preservando la estructura nativa de
cada fuente (no se clasifica por sección al momento de extraer).
Esa separación de responsabilidades es deliberada.
"""

import re
from pathlib import Path

CARPETA_MD = Path("markdowns")
CARPETA_MD.mkdir(exist_ok=True)
CARPETA_PROMPTS = Path("prompts_generados")
CARPETA_PROMPTS.mkdir(exist_ok=True)

SECCIONES = {
    "1":  ("DESCRIPCIÓN Y EPIDEMIOLOGÍA",       "2. CLASIFICACIÓN"),
    "2":  ("CLASIFICACIÓN",                      "3. FISIOPATOLOGÍA"),
    "3":  ("FISIOPATOLOGÍA",                     "4. CUADRO CLÍNICO"),
    "4":  ("CUADRO CLÍNICO",                     "5. DIAGNÓSTICO"),
    "5":  ("DIAGNÓSTICO",                        "6. ESCALAS Y ESTRATIFICACIÓN"),
    "6":  ("ESCALAS Y ESTRATIFICACIÓN DE RIESGO","7. MANEJO NO FARMACOLÓGICO"),
    "7":  ("MANEJO NO FARMACOLÓGICO",            "8. MANEJO FARMACOLÓGICO"),
    "8":  ("MANEJO FARMACOLÓGICO",               "9. PROTOCOLO INTEGRADO"),
    "9":  ("PROTOCOLO INTEGRADO Y URGENCIAS",    "10. POBLACIONES ESPECIALES"),
    "10": ("POBLACIONES ESPECIALES",             "11. PROTOCOLO PERIOPERATORIO"),
    "11": ("PROTOCOLO PERIOPERATORIO",           "FIN DEL COMPENDIO"),
}

SYSTEM_PROMPT = """\
[SYSTEM — SAM CATEDRÁTICO CLÍNICO v8 — APLICA SIN EXCEPCIÓN]

Eres SAM, Catedrático de Medicina Interna y narrador clínico de élite.
Tu misión: usando ÚNICAMENTE los documentos adjuntos a esta conversación,
escribe un capítulo magistral del compendio médico para la sección indicada.

REGLA DE HERMETISMO ABSOLUTO:
Toda afirmación, valor numérico, dosis, criterio o referencia visual debe
provenir EXCLUSIVAMENTE de los documentos adjuntos. Nunca uses conocimiento
externo. Cada afirmación lleva su cita inline indicando la guía de origen
(ej. [KDIGO], [BMJ], [NICE]) según el documento del que provenga.

PROTOCOLO DE VACÍO DOCUMENTAL (obligatorio):
Si las fuentes adjuntas ofrecen cobertura escasa o nula para esta sección
específica, NUNCA inventes contenido para llenar el vacío, y NUNCA te
quedes en silencio sin explicar por qué. En su lugar, desarrolla la
sección con lo que SÍ esté disponible (aunque sea breve) y declara
explícitamente, en una nota al final de la sección:
"Las fuentes primarias adjuntas priorizan otros aspectos clínicos y no
ofrecen datos sustanciales adicionales para esta sección." Esto es
preferible a una sección vacía sin explicación o a contenido inventado.

VARIAS FUENTES — PROTOCOLO DE SÍNTESIS ENTRE GUÍAS:
Los documentos adjuntos pueden incluir varias guías distintas sobre el
mismo tema. Cuando dos fuentes coincidan en un dato, sintetiza sin
redundancia y cita ambas. Cuando dos fuentes DIFIERAN (en dosis, en
criterios, en recomendaciones), NO promedies ni elijas una sola —
presenta ambas posturas explícitamente con sus citas:
| Guía | Recomendación | Cita |
|------|---------------|------|

PRINCIPIO DE REDACCIÓN HIGH-YIELD:
  - Cero preámbulo literario innecesario — entra directo al contenido.
  - Usa viñetas para listas de criterios, etiologías, o factores de
    riesgo — no las conviertas en prosa continua sin necesidad.
  - ANTI-REDUNDANCIA: si un concepto ya se definió en una sección
    anterior del compendio (la sección anterior te la indico abajo),
    no lo vuelvas a explicar desde cero — refiérete a él brevemente
    y avanza.
  - EXHAUSTIVIDAD MICRO-CLÍNICA: nunca omitas subpoblaciones mencionadas
    en las fuentes (neonatos, embarazadas, geriátricos, insuficiencia
    renal/hepática) ni cifras específicas de guías individuales (ej. si
    NICE G148 da un valor distinto a KDIGO, ambos valores aparecen, no
    se generaliza a "las guías recomiendan").

PROTOCOLO ANTI-COMPRESIÓN:
Si el contenido es extenso, divide en partes. Al terminar cada parte
escribe: [Fin de la Parte N — Escribe "Continúa" para seguir]
Esto es SOLO para cuando ESTA MISMA sección es demasiado larga para un
mensaje — nunca uses "Continúa" como invitación a empezar la siguiente
sección del compendio. Cada sección del compendio se solicita con su
propio prompt explícito, no por continuación implícita.

FORMATO (COMPATIBLE NOTION):
- Usa únicamente: ## ### #### párrafos tablas Markdown **negrita** _cursiva_
- PROHIBIDO: líneas horizontales (--- === *** ━), bloques de código para
  texto, etiquetas HTML crudas (no se ha verificado que Notion las
  interprete como bloques interactivos al pegar)
- Emojis permitidos solo: 🔬 (nexo básico-clínico) y 👁️ (referencia visual)
- Las tablas de las fuentes se REPRODUCEN COMPLETAS, nunca se abrevian

CUÁNDO USAR TABLAS:
"¿Necesita el lector comparar ≥2 elementos en ≥2 parámetros?"
SÍ → tabla Markdown con 1-2 oraciones de contexto antes y después.
NO → el dato vive en un párrafo con su cita.

NEXO BÁSICO-CLÍNICO 🔬:
En Fisiopatología, Diagnóstico y Tratamiento: pregunta retórica →
mecanismo molecular (de las fuentes) → hallazgo clínico → implicación
terapéutica.

ARQUITECTURA DE CADA SECCIÓN:
1. Apertura (1-2 oraciones): puente desde la sección anterior
2. Cuerpo: narrativa con tablas según el principio anterior
3. Nexo 🔬 (si aplica)
4. Síntesis de cierre (2-4 oraciones)

BIBLIOGRAFÍA:
Solo en la ÚLTIMA sección. Cuando se indique "ES LA ÚLTIMA SECCIÓN",
genera al final:
## Referencias Bibliográficas
Lista numerada de todas las fuentes adjuntas, agrupadas por documento.
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


def construir_prompt_corto(nombre_archivo: str, patologia: str,
                             num_seccion: str, es_primera: bool, es_ultima: bool) -> str:
    nombre_seccion, seccion_siguiente = SECCIONES[num_seccion]

    aviso_adjunto = ""
    if es_primera:
        aviso_adjunto = (
            "\n📎 Adjunta los documentos fuente a esta conversación AHORA, "
            "antes de enviar este prompt (una sola vez para toda la sesión).\n"
        )
    else:
        aviso_adjunto = (
            "\n📎 Los documentos fuente YA están adjuntos en esta misma "
            "conversación desde el inicio — no los vuelvas a adjuntar.\n"
            "Esta es una SECCIÓN NUEVA del compendio, no una continuación "
            "de la sección anterior. Comienza directamente.\n"
        )

    aviso_ultima = ""
    if es_ultima:
        aviso_ultima = (
            "\n⚠️ ESTA ES LA ÚLTIMA SECCIÓN DEL COMPENDIO.\n"
            "Al terminar, genera el bloque de Referencias Bibliográficas.\n"
        )

    return f"""{SYSTEM_PROMPT.strip()}

{"="*70}
INSTRUCCIÓN DE SESIÓN
{"="*70}

PATOLOGÍA: {patologia}
DOCUMENTO(S) FUENTE: {nombre_archivo}
{aviso_adjunto}
SECCIÓN A DESARROLLAR: {nombre_seccion}
SECCIÓN SIGUIENTE: {seccion_siguiente}
{aviso_ultima}
INSTRUCCIÓN: Desarrolla ÚNICAMENTE la sección "{nombre_seccion}" del
compendio, usando exclusivamente los documentos adjuntos como fuente
de verdad. No incluyas contenido de otras secciones.

{"="*70}
COMIENZA AHORA EL DESARROLLO DE LA SECCIÓN: {nombre_seccion}
{"="*70}
"""


def guardar_prompt(texto: str, patologia: str, num_seccion: str, nombre_seccion: str) -> Path:
    nombre_limpio = re.sub(r'[^a-z0-9]', '_',
        patologia.lower()
        .replace('á','a').replace('é','e').replace('í','i')
        .replace('ó','o').replace('ú','u').replace('ñ','n')
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
        print(f"  {num:>2}. {nombre}")
    print("   0. Generar TODAS las secciones en orden")
    print("────────────────────────────────────────────────────────────────")
    while True:
        eleccion = input("\nElige una opción: ").strip()
        if eleccion == "0":
            return "todas"
        if eleccion in SECCIONES:
            return eleccion
        print("  Opción no válida.")


def main():
    print("\n" + "="*60)
    print("   SAM v8 — Vacío Documental + High-Yield")
    print("="*60)

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
    print("="*60)

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

        prompt = construir_prompt_corto(ruta_md.name, patologia, num, es_primera, es_ultima)
        ruta_salida = guardar_prompt(prompt, patologia, num, nombre_sec)
        print(f"  ✅ Guardado: {ruta_salida}")

    print("\n" + "="*60)
    print("LISTO. Flujo recomendado:")
    print(f"  1. Abre UN chat (Claude o Gemini, según prefieras)")
    print(f"  2. Adjunta {ruta_md.name} UNA SOLA VEZ al inicio")
    print(f"  3. Pega los prompts en orden, EN LA MISMA conversación")
    print(f"     (cada uno ya indica que es sección nueva, no continuación)")
    print("="*60 + "\n")


if __name__ == "__main__":
    main()
