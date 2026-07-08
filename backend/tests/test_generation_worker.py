from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.compendium_section import CompendiumSection, SectionStatus
from app.models.project import Project, ProjectStatus
from app.models.user import User
from app.modules.ai_gateway.interfaces import AIResult
from app.modules.auth.service import hash_password
from app.modules.prompts.section_builder import SECTION_CONFIGS
from app.workers.generation_worker import generate_section


def _make_ai_result(
    content: str = "Generated section content",
    model: str = "google/gemini-2.5-pro",
) -> AIResult:
    return AIResult(
        content=content,
        model=model,
        input_tokens=2000,
        output_tokens=1500,
        cost_usd=0.10,
        finish_reason="STOP",
    )


async def _create_generation_test_data(
    db: AsyncSession, email: str, num_sections: int = 0
) -> dict:
    user = User(
        email=email,
        password_hash=hash_password("Test1234"),
        full_name="Gen Worker Test",
    )
    db.add(user)
    await db.flush()

    project = Project(
        user_id=user.id,
        name="LRA Test",
        slug=f"lra-gen-{email.split('@')[0]}",
        status=ProjectStatus.GENERATING,
        merged_content="Merged extraction content for testing generation worker.",
    )
    db.add(project)
    await db.flush()

    section_ids = []
    for num in range(1, num_sections + 1):
        config = SECTION_CONFIGS[num]
        section = CompendiumSection(
            project_id=project.id,
            section_number=num,
            section_name=config.section_name,
            dosification="STANDARD",
            status=SectionStatus.PENDING,
        )
        db.add(section)
        await db.flush()
        section_ids.append(section.id)

    await db.commit()

    return {
        "user_id": user.id,
        "project_id": project.id,
        "section_ids": section_ids,
    }


@pytest.mark.asyncio
async def test_worker_saves_section_content(client, db_session):
    data = await _create_generation_test_data(
        db_session, "gen-content@test.com", num_sections=1
    )
    section_id = data["section_ids"][0]

    with patch(
        "app.workers.generation_worker.OpenRouterClient"
    ) as MockAI:
        mock_ai = MagicMock()
        mock_ai.generate = AsyncMock(return_value=_make_ai_result())
        MockAI.return_value = mock_ai

        result = await generate_section(
            {},
            project_id=data["project_id"],
            section_number=1,
            _db=db_session,
        )

        assert result["status"] == "completed"

        section = (
            await db_session.execute(
                select(CompendiumSection).where(
                    CompendiumSection.id == section_id
                )
            )
        ).scalar_one()
        assert section.status == SectionStatus.COMPLETED
        assert section.content == "Generated section content"


@pytest.mark.asyncio
async def test_worker_saves_model_used(client, db_session):
    data = await _create_generation_test_data(
        db_session, "gen-model@test.com", num_sections=1
    )

    with patch(
        "app.workers.generation_worker.OpenRouterClient"
    ) as MockAI:
        mock_ai = MagicMock()
        mock_ai.generate = AsyncMock(
            return_value=_make_ai_result(model="google/gemini-2.5-pro")
        )
        MockAI.return_value = mock_ai

        await generate_section(
            {},
            project_id=data["project_id"],
            section_number=1,
            _db=db_session,
        )

        section = (
            await db_session.execute(
                select(CompendiumSection).where(
                    CompendiumSection.project_id == data["project_id"],
                    CompendiumSection.section_number == 1,
                )
            )
        ).scalar_one()
        assert section.model_used == "google/gemini-2.5-pro"


@pytest.mark.asyncio
async def test_worker_saves_cost_and_tokens(client, db_session):
    data = await _create_generation_test_data(
        db_session, "gen-cost@test.com", num_sections=1
    )

    with patch(
        "app.workers.generation_worker.OpenRouterClient"
    ) as MockAI:
        mock_ai = MagicMock()
        mock_ai.generate = AsyncMock(return_value=_make_ai_result())
        MockAI.return_value = mock_ai

        await generate_section(
            {},
            project_id=data["project_id"],
            section_number=1,
            _db=db_session,
        )

        section = (
            await db_session.execute(
                select(CompendiumSection).where(
                    CompendiumSection.project_id == data["project_id"],
                    CompendiumSection.section_number == 1,
                )
            )
        ).scalar_one()
        assert section.input_tokens == 2000
        assert section.output_tokens == 1500
        assert float(section.cost_usd) == 0.10


@pytest.mark.asyncio
async def test_worker_saves_prompt_version(client, db_session):
    data = await _create_generation_test_data(
        db_session, "gen-version@test.com", num_sections=1
    )

    with patch(
        "app.workers.generation_worker.OpenRouterClient"
    ) as MockAI:
        mock_ai = MagicMock()
        mock_ai.generate = AsyncMock(return_value=_make_ai_result())
        MockAI.return_value = mock_ai

        await generate_section(
            {},
            project_id=data["project_id"],
            section_number=1,
            _db=db_session,
        )

        section = (
            await db_session.execute(
                select(CompendiumSection).where(
                    CompendiumSection.project_id == data["project_id"],
                    CompendiumSection.section_number == 1,
                )
            )
        ).scalar_one()
        assert section.prompt_version is not None
        assert section.prompt_version == "1"


@pytest.mark.asyncio
async def test_red_sections_use_claude(client, db_session):
    red_sections = [3, 5, 8, 9]
    data = await _create_generation_test_data(
        db_session, "gen-claude@test.com", num_sections=9
    )

    with patch(
        "app.workers.generation_worker.OpenRouterClient"
    ) as MockAI:
        mock_ai = MagicMock()

        async def capture_generate(prompt, model, **kwargs):
            return _make_ai_result(
                content=f"Content for {model}",
                model=model,
            )

        mock_ai.generate = AsyncMock(side_effect=capture_generate)
        MockAI.return_value = mock_ai

        for num in red_sections:
            await generate_section(
                {},
                project_id=data["project_id"],
                section_number=num,
                _db=db_session,
            )

        for num in red_sections:
            section = (
                await db_session.execute(
                    select(CompendiumSection).where(
                        CompendiumSection.project_id == data["project_id"],
                        CompendiumSection.section_number == num,
                    )
                )
            ).scalar_one()
            assert "claude" in (section.model_used or "").lower(), (
                f"Section {num} should use Claude, got {section.model_used}"
            )


@pytest.mark.asyncio
async def test_green_yellow_sections_use_gemini(client, db_session):
    gemini_sections = [1, 2, 4, 6, 7]
    data = await _create_generation_test_data(
        db_session, "gen-gemini@test.com", num_sections=7
    )

    with patch(
        "app.workers.generation_worker.OpenRouterClient"
    ) as MockAI:
        mock_ai = MagicMock()

        async def capture_generate(prompt, model, **kwargs):
            return _make_ai_result(
                content=f"Content for {model}",
                model=model,
            )

        mock_ai.generate = AsyncMock(side_effect=capture_generate)
        MockAI.return_value = mock_ai

        for num in gemini_sections:
            await generate_section(
                {},
                project_id=data["project_id"],
                section_number=num,
                _db=db_session,
            )

        for num in gemini_sections:
            section = (
                await db_session.execute(
                    select(CompendiumSection).where(
                        CompendiumSection.project_id == data["project_id"],
                        CompendiumSection.section_number == num,
                    )
                )
            ).scalar_one()
            assert "gemini" in (section.model_used or "").lower(), (
                f"Section {num} should use Gemini, got {section.model_used}"
            )


@pytest.mark.asyncio
async def test_project_review_when_all_done(client, db_session):
    data = await _create_generation_test_data(
        db_session, "gen-review@test.com", num_sections=11
    )

    with patch(
        "app.workers.generation_worker.OpenRouterClient"
    ) as MockAI:
        mock_ai = MagicMock()
        mock_ai.generate = AsyncMock(return_value=_make_ai_result())
        MockAI.return_value = mock_ai

        for num in range(1, 12):
            await generate_section(
                {},
                project_id=data["project_id"],
                section_number=num,
                _db=db_session,
            )

        project = (
            await db_session.execute(
                select(Project).where(Project.id == data["project_id"])
            )
        ).scalar_one()
        assert project.status == ProjectStatus.REVIEW


@pytest.mark.asyncio
async def test_project_stays_generating_with_pending(client, db_session):
    data = await _create_generation_test_data(
        db_session, "gen-pending@test.com", num_sections=11
    )

    with patch(
        "app.workers.generation_worker.OpenRouterClient"
    ) as MockAI:
        mock_ai = MagicMock()
        mock_ai.generate = AsyncMock(return_value=_make_ai_result())
        MockAI.return_value = mock_ai

        await generate_section(
            {},
            project_id=data["project_id"],
            section_number=1,
            _db=db_session,
        )

        project = (
            await db_session.execute(
                select(Project).where(Project.id == data["project_id"])
            )
        ).scalar_one()
        assert project.status == ProjectStatus.GENERATING


@pytest.mark.asyncio
async def test_worker_handles_ai_failure(client, db_session):
    data = await _create_generation_test_data(
        db_session, "gen-fail@test.com", num_sections=1
    )

    with patch(
        "app.workers.generation_worker.OpenRouterClient"
    ) as MockAI:
        mock_ai = MagicMock()
        mock_ai.generate = AsyncMock(
            side_effect=Exception("OpenRouter API error")
        )
        MockAI.return_value = mock_ai

        result = await generate_section(
            {},
            project_id=data["project_id"],
            section_number=1,
            _db=db_session,
        )

        assert result["status"] == "failed"
        assert "OpenRouter API error" in result["error"]

        section = (
            await db_session.execute(
                select(CompendiumSection).where(
                    CompendiumSection.project_id == data["project_id"],
                    CompendiumSection.section_number == 1,
                )
            )
        ).scalar_one()
        assert section.status == SectionStatus.FAILED
        assert "OpenRouter API error" in section.error_message
