import pytest

from app.modules.prompts.section_builder import (
    SECTION_CONFIGS,
    build_section_prompt,
)


SYSTEM_PROMPT = "[SYSTEM — SAM v9] Test system prompt content."
PATCH_GEMINI = "REFUERZO OBLIGATORIO DE DENSIDAD DE CITAS: test patch content."


@pytest.mark.asyncio
async def test_build_section_prompt_returns_string():
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


@pytest.mark.asyncio
async def test_section_prompt_includes_pathology():
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


@pytest.mark.asyncio
async def test_section_prompt_includes_section_name():
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


@pytest.mark.asyncio
async def test_section_1_has_no_ecos():
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


@pytest.mark.asyncio
async def test_section_3_has_ecos():
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
    assert "Criterios diagnósticos KDIGO" in result


@pytest.mark.asyncio
async def test_section_4_has_cogeneration_note():
    result = build_section_prompt(
        section_number=4,
        merged_content="content",
        pathology_name="LRA",
        source_filename="test.pdf",
        is_first=False,
        is_last=False,
        system_prompt=SYSTEM_PROMPT,
    )
    assert "CO-GENERACIÓN CLÍNICA" in result
    assert "CUADRO CLÍNICO" in result


@pytest.mark.asyncio
async def test_section_5_has_cogeneration_note():
    result = build_section_prompt(
        section_number=5,
        merged_content="content",
        pathology_name="LRA",
        source_filename="test.pdf",
        is_first=False,
        is_last=False,
        system_prompt=SYSTEM_PROMPT,
    )
    assert "CO-GENERACIÓN CLÍNICA" in result
    assert "DIAGNÓSTICO" in result


@pytest.mark.asyncio
async def test_section_11_has_last_section_note():
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


@pytest.mark.asyncio
async def test_non_last_sections_have_no_last_note():
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


@pytest.mark.asyncio
async def test_gemini_sections_include_patch():
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


@pytest.mark.asyncio
async def test_claude_sections_exclude_patch():
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


@pytest.mark.asyncio
async def test_first_section_has_attachment_note():
    result = build_section_prompt(
        section_number=1,
        merged_content="content",
        pathology_name="LRA",
        source_filename="test.pdf",
        is_first=True,
        is_last=False,
        system_prompt=SYSTEM_PROMPT,
    )
    assert "Adjunta los documentos fuente" in result


@pytest.mark.asyncio
async def test_subsequent_sections_have_no_reattach_note():
    result = build_section_prompt(
        section_number=2,
        merged_content="content",
        pathology_name="LRA",
        source_filename="test.pdf",
        is_first=False,
        is_last=False,
        system_prompt=SYSTEM_PROMPT,
    )
    assert "YA están adjuntos" in result
    assert "SECCIÓN NUEVA" in result


@pytest.mark.asyncio
async def test_red_sections_have_thinking_note():
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
