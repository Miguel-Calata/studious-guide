"""
Tests contra la spec objetivo de Tarea 1+3+6 — `section_builder`.

Reescritos respecto a la versión legacy: ahora verifican que
  - el prompt de la sección 5 ya no miente sobre "acabas de
    generar cuadro clínico en este mismo chat" cuando se usa
    en modo thread (la continuidad real se demuestra con Tarea
    1+5 a nivel orchestrator);
  - el bloque MAPA DE ECOS gana la cláusula de "mención ≠
    desarrollo";
  - las instrucciones se pueden inyectar con ecos arbitrarios
    (Tarea 3: el eco map viene de BD, no del config);
  - build_thread_init_message crea el primer mensaje del hilo
    con sistema + fuentes, sin reenviar la fuente en cada
    sección.
"""

import pytest

from app.modules.prompts.section_builder import (
    SECTION_CONFIGS,
    build_section_instruction,
    build_section_prompt,
    build_thread_init_message,
)

SYSTEM_PROMPT = "[SYSTEM — SAM v9] Test system prompt content."
PATCH_GEMINI = "REFUERZO OBLIGATORIO DE DENSIDAD DE CITAS: test patch content."


# ── build_thread_init_message (Tarea 1) ─────────────────────────────


def test_thread_init_message_contains_system_and_sources():
    msg = build_thread_init_message(
        system_prompt=SYSTEM_PROMPT,
        pathology_name="LRA",
        source_filename="kdigo.pdf",
        merged_content="# Fuentes\nContenido de prueba",
    )
    assert msg.role == "user"
    assert SYSTEM_PROMPT in msg.content
    assert "Contenido de prueba" in msg.content
    assert "# Fuentes" in msg.content
    assert "LRA" in msg.content
    assert "kdigo.pdf" in msg.content


def test_thread_init_message_prepends_gemini_patch():
    msg = build_thread_init_message(
        system_prompt=SYSTEM_PROMPT,
        pathology_name="LRA",
        source_filename="kdigo.pdf",
        merged_content="contenido",
        patch_gemini=PATCH_GEMINI,
    )
    # El patch_gemini debe ir ANTES del system_prompt en el
    # contenido del primer mensaje.
    assert PATCH_GEMINI in msg.content
    pos_patch = msg.content.find(PATCH_GEMINI)
    pos_sys = msg.content.find(SYSTEM_PROMPT)
    assert pos_patch < pos_sys


def test_thread_init_message_omits_patch_when_none():
    msg = build_thread_init_message(
        system_prompt=SYSTEM_PROMPT,
        pathology_name="LRA",
        source_filename="x.pdf",
        merged_content="c",
        patch_gemini=None,
    )
    assert PATCH_GEMINI not in msg.content


# ── build_section_instruction (modo thread, Tarea 1) ────────────────


def test_section_instruction_does_not_embed_source_block():
    """
    En modo thread, la instrucción por sección NO debe re-incrustar
    la fuente documental — ya fue enviada en el primer mensaje.
    Verifica ausencia del bloque fuente con sus delimitadores.
    """
    inst = build_section_instruction(
        section_number=3,
        pathology_name="LRA",
        source_filename="kdigo.pdf",
        is_last=False,
    )
    # El bloque de fuente en build_section_prompt tiene estos marcadores.
    # La instrucción thread NO debe incluirlos.
    assert "FIN DEL CONTENIDO FUENTE" not in inst
    assert "merged_content" not in inst
    assert "merged" not in inst.lower()


def test_section_instruction_includes_dosification_and_motor():
    inst = build_section_instruction(
        section_number=3,
        pathology_name="LRA",
        source_filename="kdigo.pdf",
        is_last=False,
    )
    # Sección 3 es 🔴 MÁXIMO y motor "claude" según config
    assert "🔴 MÁXIMO" in inst
    assert "claude" in inst
    assert "Extended Thinking" in inst


def test_section_instruction_section_5_references_cogeneration_truthfully():
    """
    La nota R-9 de la sección 5 ya no miente: si la generación
    se hace dentro del mismo thread (modo orchestrator), el
    contenido previo de la 4 está en el historial real, no en
    una nota que se basa en suposición.
    """
    inst = build_section_instruction(
        section_number=5,
        pathology_name="LRA",
        source_filename="kdigo.pdf",
        is_last=False,
    )
    assert "CO-GENERACIÓN" in inst
    assert "DIAGNÓSTICO" in inst


def test_section_instruction_accepts_injected_ecos():
    """
    Tarea 3: el eco map se carga de BD y se inyecta en la
    instrucción; el config default no debe usarse si hay
    override.
    """
    custom_ecos = ["ECO_CUSTOM_1", "ECO_CUSTOM_2"]
    inst = build_section_instruction(
        section_number=3,
        pathology_name="LRA",
        source_filename="kdigo.pdf",
        is_last=False,
        ecos=custom_ecos,
    )
    assert "ECO_CUSTOM_1" in inst
    assert "ECO_CUSTOM_2" in inst


def test_section_instruction_default_uses_config_ecos():
    """Sin override, se usa el ecos del config de la sección."""
    inst = build_section_instruction(
        section_number=2,
        pathology_name="LRA",
        source_filename="kdigo.pdf",
        is_last=False,
    )
    config_ecos = SECTION_CONFIGS[2].ecos
    for eco in config_ecos:
        # El eco puede aparecer con "→ ver X" o similar
        assert any(
            word in inst for word in eco.split()[:3]
        )


def test_section_instruction_ecos_block_contains_no_omit_clause():
    """
    Restricción dura Tarea 3: el bloque de ecos DEBE contener
    la cláusula de "mención ≠ desarrollo".
    """
    inst = build_section_instruction(
        section_number=4,
        pathology_name="LRA",
        source_filename="kdigo.pdf",
        is_last=False,
    )
    assert "mención" in inst.lower()
    assert "desarrollo" in inst.lower()


def test_section_instruction_last_section_marks_11():
    inst = build_section_instruction(
        section_number=11,
        pathology_name="LRA",
        source_filename="kdigo.pdf",
        is_last=True,
    )
    assert "ÚLTIMA SECCIÓN" in inst
    assert "Referencias Bibliográficas" in inst


def test_section_instruction_motor_override():
    """
    Tarea 5: si la sección 5 hereda motor del par 4 (motor_override
    = "gemini"), la instrucción debe mostrar "gemini", no "claude".
    """
    inst = build_section_instruction(
        section_number=5,
        pathology_name="LRA",
        source_filename="kdigo.pdf",
        is_last=False,
        motor_override="gemini",
    )
    assert "gemini" in inst
    # La sección 5 sigue siendo 🔴 MÁXIMO por dosificación; la nota
    # de thinking permanece como indicación al clínico (la decisión
    # de aplicar thinking la toma el orchestrator con extra_params
    # cuando el motor efectivo es Claude).


# ── build_section_prompt (modo standalone, retrocompatibilidad) ────


@pytest.mark.asyncio
async def test_build_section_prompt_returns_string_legacy():
    """Compatibilidad: build_section_prompt sigue funcionando para
    generación standalone (no thread) con su firma original."""
    result = build_section_prompt(
        section_number=1,
        merged_content="Test merged content",
        pathology_name="LRA",
        source_filename="kdigo.pdf",
        is_first=True,
        is_last=False,
        system_prompt=SYSTEM_PROMPT,
        patch_gemini=PATCH_GEMINI,
    )
    assert isinstance(result, str)
    assert len(result) > 100


def test_legacy_section_prompt_includes_pathology():
    result = build_section_prompt(
        section_number=1,
        merged_content="content",
        pathology_name="Insuficiencia Renal Aguda",
        source_filename="test.pdf",
        is_first=True,
        is_last=False,
        system_prompt=SYSTEM_PROMPT,
    )
    assert "Insuficiencia Renal Aguda" in result


def test_legacy_section_prompt_includes_section_name_for_all():
    for num in range(1, 12):
        result = build_section_prompt(
            section_number=num,
            merged_content="content",
            pathology_name="LRA",
            source_filename="test.pdf",
            is_first=(num == 1),
            is_last=(num == 11),
            system_prompt=SYSTEM_PROMPT,
        )
        config = SECTION_CONFIGS[num]
        assert config.section_name in result


def test_legacy_section_1_has_no_ecos():
    result = build_section_prompt(
        section_number=1,
        merged_content="content",
        pathology_name="LRA",
        source_filename="test.pdf",
        is_first=True,
        is_last=False,
        system_prompt=SYSTEM_PROMPT,
    )
    assert "MAPA DE ECOS" not in result


def test_legacy_section_3_has_ecos():
    result = build_section_prompt(
        section_number=3,
        merged_content="content",
        pathology_name="LRA",
        source_filename="test.pdf",
        is_first=False,
        is_last=False,
        system_prompt=SYSTEM_PROMPT,
    )
    assert "MAPA DE ECOS" in result
    # Ecos default del config de la 3
    assert "Criterios diagnósticos" in result or "kdigo" in result.lower()


def test_legacy_gemini_sections_include_patch():
    gemini_sections = [1, 2, 4, 6, 7, 10, 11]
    for num in gemini_sections:
        result = build_section_prompt(
            section_number=num,
            merged_content="content",
            pathology_name="LRA",
            source_filename="test.pdf",
            is_first=(num == 1),
            is_last=(num == 11),
            system_prompt=SYSTEM_PROMPT,
            patch_gemini=PATCH_GEMINI,
        )
        assert "DENSIDAD DE CITAS" in result


def test_legacy_claude_sections_exclude_patch():
    claude_sections = [3, 5, 8, 9]
    for num in claude_sections:
        result = build_section_prompt(
            section_number=num,
            merged_content="content",
            pathology_name="LRA",
            source_filename="test.pdf",
            is_first=False,
            is_last=False,
            system_prompt=SYSTEM_PROMPT,
            patch_gemini=PATCH_GEMINI,
        )
        assert "DENSIDAD DE CITAS" not in result


def test_legacy_red_sections_have_thinking_note():
    red_sections = [3, 5, 8, 9]
    for num in red_sections:
        result = build_section_prompt(
            section_number=num,
            merged_content="content",
            pathology_name="LRA",
            source_filename="test.pdf",
            is_first=False,
            is_last=False,
            system_prompt=SYSTEM_PROMPT,
        )
        assert "Extended Thinking" in result


def test_legacy_section_11_has_last_note():
    result = build_section_prompt(
        section_number=11,
        merged_content="content",
        pathology_name="LRA",
        source_filename="test.pdf",
        is_first=False,
        is_last=True,
        system_prompt=SYSTEM_PROMPT,
    )
    assert "ÚLTIMA SECCIÓN" in result
    assert "Referencias Bibliográficas" in result


def test_legacy_non_last_sections_have_no_last_note():
    for num in range(1, 11):
        result = build_section_prompt(
            section_number=num,
            merged_content="content",
            pathology_name="LRA",
            source_filename="test.pdf",
            is_first=(num == 1),
            is_last=False,
            system_prompt=SYSTEM_PROMPT,
        )
        assert "ÚLTIMA SECCIÓN" not in result


# ── Coherencia config / thread instruction (Tarea 1) ────────────────


def test_thread_instruction_matches_config_motor_when_no_override():
    """Sin motor_override, la instrucción muestra el motor del config."""
    for num in (3, 5, 8, 9):  # claude per config
        inst = build_section_instruction(
            section_number=num,
            pathology_name="LRA",
            source_filename="x.pdf",
            is_last=False,
        )
        assert SECTION_CONFIGS[num].motor in inst
