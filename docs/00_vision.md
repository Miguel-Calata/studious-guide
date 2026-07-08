# 00 — Visión del Proyecto

## 🎯 Objetivo

**SAM Platform** es una aplicación web que automatiza la creación de compendios médicos de alta densidad clínica a partir de guías y artículos científicos en PDF, utilizando IA (Gemini + Claude vía OpenRouter) como motor de extracción y redacción, con publicación directa en Notion.

## 👥 Stakeholders

| Rol | Persona | Interés |
|-----|---------|---------|
| **Cliente / Experto de dominio** | Dr. Jorge (médico) | Compendios precisos, fiables, con citas granulares; ahorrar ~5h manuales por patología |
| **Desarrollador** | Calata | Arquitectura limpia, modular, mantenible, deployable en VPS |
| **Usuario final** | Residentes de medicina | Acceso a compendios actualizados, bien estructurados, listos para estudio/consulta |

## 🧠 Contexto: ¿Qué problema resuelve?

Actualmente el Dr. ejecuta un pipeline **manual** para cada patología:

1. Consigue PDFs de guías clínicas (KDIGO, BMJ, NICE, etc.) y artículos (Lancet, NEJM, etc.)
2. Usa Gemini (web) para extraer el contenido de cada PDF con prompts especializados
3. Verifica duplicados manualmente
4. Une todas las extracciones con un script Python
5. Genera 11 prompts especializados con otro script Python (`sam_v9_generador.py`)
6. Bifurca el trabajo: 7 secciones en Gemini web, 4 en Claude web
7. Copia/pega manualmente cada resultado
8. Ensambla todo en Notion

**Problemas críticos del flujo actual:**
- 🔴 ~5 horas de trabajo manual por patología
- 🔴 Límites de cuota en interfaces web (archivos de 150k tokens colapsan las suscripciones)
- 🔴 "Eco ciego": las secciones no se comunican entre sí (si la sección 2 omite algo, la 3 no lo sabe)
- 🔴 Inconsistencia terminológica entre secciones generadas en chats aislados
- 🔴 Riesgo de error humano en copy-paste entre plataformas

## 🚀 Visión del Producto

SAM Platform convierte ese pipeline manual en una aplicación web donde el Dr. (y eventualmente otros médicos) pueda:

1. **Subir PDFs** → drag & drop
2. **Clasificar fuentes** → BMJ, guía completa, artículo
3. **Lanzar extracción** → un clic, el sistema llama a Gemini API (vía OpenRouter)
4. **Revisar extracciones** → editor Markdown integrado
5. **Generar compendio** → un clic, el sistema orquesta las 11 secciones
6. **Revisar/editar secciones** → editor con preview
7. **Publicar en Notion** → un clic, vía Notion API

Todo con:
- Trazabilidad completa (qué PDF generó qué contenido)
- Control de costos (tokens consumidos por patología)
- Historial de versiones
- Posibilidad de re-ejecutar secciones individuales

## 📐 Principios de Diseño

1. **Modularidad**: Cada subsistema (extracción, generación, prompts, Notion) es independiente y reemplazable
2. **API-first**: Toda la lógica de negocio vive en el backend; el frontend es solo una interfaz
3. **Configuración sobre código**: Los prompts, reglas y flujos son configurables sin tocar código
4. **Observabilidad**: Logs, métricas y trazabilidad en cada paso del pipeline
5. **Seguridad**: Datos médicos sensibles; HTTPS, autenticación, RBAC
6. **Simple deployment**: Un `docker compose up` debe levantar todo

## 🗺️ Roadmap (Fases)

| Fase | Alcance | Prioridad |
|------|---------|-----------|
| **Fase 1 — MVP** | Pipeline completo funcional: upload PDF → extracción → unión → generación de 11 secciones → export Markdown. Sin frontend aún, todo vía API/CLI. | 🔴 AHORA |
| **Fase 2 — Web UI** | Frontend React con dashboard, gestión de proyectos, editor Markdown, preview de secciones. | 🟡 Después |
| **Fase 3 — Notion** | Integración completa con Notion API: autenticación, selección de base de datos, publicación automática. | 🟡 Después |
| **Fase 4 — Multi-user** | Registro, login, roles, proyectos compartidos. Google OAuth. | 🟢 Futuro |
| **Fase 5 — Colaboración** | Comentarios en secciones, revisión por pares, historial de cambios. | 🟢 Futuro |

---

> **Referencia original del Dr.:** [memory/NUEVO - IA -.md](../memory/NUEVO%20-%20IA%20-%203965d19d1db18052a5d3c17952ed589f.md)
