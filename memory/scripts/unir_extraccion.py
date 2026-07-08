"""
SAM — UNIR PARTES DE EXTRACCIÓN
================================
Junta los pedazos que Gemini te va dando (extracción inicial,
continuaciones, auditoría) en UN SOLO archivo .md por patología,
listo para usarse en sam_v6_generador.py

CÓMO USARLO (método recomendado — descarga directa, sin copiar y pegar):

Gemini puede generar el resultado como un archivo descargable en vez de
solo texto en el chat. Para activarlo, agrega esta línea al final de tu
prompt de extracción (y también al pedir "continúa" o la auditoría):

    "Genera tu respuesta como un archivo Markdown (.md) descargable,
    no la muestres solo como texto en el chat."

Gemini te dará un botón de descarga. Cada archivo que descargues lo
mueves directamente a una carpeta por patología dentro de raw_parts/,
en el orden en que los recibiste:

    raw_parts/lesion_renal_aguda/01.md   -> extracción inicial
    raw_parts/lesion_renal_aguda/02.md   -> si hubo "continúa"
    raw_parts/lesion_renal_aguda/03.md   -> la auditoría (ADENDA)

No importa el nombre exacto, solo el orden numérico al inicio.

ALTERNATIVA (si Gemini no te da la opción de descarga en tu caso):
copia el texto de la respuesta y pégalo en un archivo nuevo de TextEdit
o VS Code, numerado igual (01.txt, 02.txt...), guardado como texto plano.
El script acepta tanto .md como .txt indistintamente.

Después de tener todas las partes de una patología en su carpeta, corre
este script: te va a preguntar qué carpeta unir, y te entrega el .md
final ya limpio, directo en markdowns/, listo para sam_v6_generador.py.

Este script también borra automáticamente las líneas tipo
"[CONTINÚA - Pendiente desde: ...]", porque esas son solo señales de
chat, no contenido clínico.
"""

import re
from pathlib import Path

CARPETA_RAW = Path("raw_parts")
CARPETA_RAW.mkdir(exist_ok=True)
CARPETA_MD = Path("markdowns")
CARPETA_MD.mkdir(exist_ok=True)

MARCADOR_CONTINUACION = re.compile(r"\[CONTINÚA.*?\]", re.IGNORECASE | re.DOTALL)


def listar_carpetas_pendientes() -> list[Path]:
    return sorted([c for c in CARPETA_RAW.iterdir() if c.is_dir()])


def unir_carpeta(carpeta: Path) -> str:
    archivos = sorted(list(carpeta.glob("*.txt")) + list(carpeta.glob("*.md")))
    if not archivos:
        return ""
    partes = []
    for archivo in archivos:
        texto = archivo.read_text(encoding="utf-8", errors="ignore").strip()
        texto = MARCADOR_CONTINUACION.sub("", texto).strip()
        partes.append(texto)
    return "\n\n".join(partes)


def main():
    print("\n=== SAM — UNIR PARTES DE EXTRACCIÓN ===\n")
    carpetas = listar_carpetas_pendientes()

    if not carpetas:
        print("No hay carpetas dentro de raw_parts/.")
        print("Crea una carpeta por patología (ej. raw_parts/lesion_renal_aguda/)")
        print("y pega ahí los .txt numerados (01.txt, 02.txt, ...).")
        return

    print("Carpetas disponibles:")
    for i, c in enumerate(carpetas, 1):
        n_archivos = len(list(c.glob("*.txt"))) + len(list(c.glob("*.md")))
        print(f"  {i}. {c.name}  ({n_archivos} partes encontradas)")

    try:
        idx = int(input("\nElige la carpeta a unir (número): ")) - 1
        carpeta = carpetas[idx]
    except (ValueError, IndexError):
        print("Selección inválida.")
        return

    contenido_final = unir_carpeta(carpeta)
    if not contenido_final:
        print("Esa carpeta está vacía, no hay nada que unir.")
        print("Descarga o pega ahí las partes (.md o .txt) numeradas: 01, 02, 03...")
        return

    ruta_salida = CARPETA_MD / f"{carpeta.name}.md"
    ruta_salida.write_text(contenido_final, encoding="utf-8")

    tokens_aprox = len(contenido_final) // 4
    print(f"\n✅ Archivo final creado: {ruta_salida}")
    print(f"   {len(contenido_final):,} caracteres (~{tokens_aprox:,} tokens aproximados)")
    print("\nEste archivo ya está listo para sam_v6_generador.py")
    print("Puedes borrar la carpeta en raw_parts/ si ya no la necesitas.")


if __name__ == "__main__":
    main()
