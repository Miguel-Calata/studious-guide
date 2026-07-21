from sqlalchemy import ForeignKey, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin


class SectionStatus:
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    APPROVED = "approved"

    VALID_STATUSES = {PENDING, PROCESSING, COMPLETED, FAILED, APPROVED}


class CompendiumSection(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "compendium_sections"
    __table_args__ = (
        UniqueConstraint("project_id", "section_number", name="uq_compendium_sections_project_section"),
    )

    project_id: Mapped[str] = mapped_column(
        String(),
        ForeignKey("projects.id"),
        nullable=False,
        index=True,
    )
    section_number: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )
    section_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    content: Mapped[str] = mapped_column(
        Text,
        default="",
        server_default="",
        nullable=False,
    )
    model_used: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )
    dosification: Mapped[str] = mapped_column(
        String(10),
        default="STANDARD",
        server_default="STANDARD",
        nullable=False,
    )
    input_tokens: Mapped[int | None] = mapped_column(
        nullable=True,
    )
    output_tokens: Mapped[int | None] = mapped_column(
        nullable=True,
    )
    cost_usd: Mapped[float | None] = mapped_column(
        Numeric(10, 6),
        nullable=True,
    )
    status: Mapped[str] = mapped_column(
        String(50),
        default=SectionStatus.PENDING,
        server_default=SectionStatus.PENDING,
        nullable=False,
    )
    prompt_version: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
    )
    ecos_map_version: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
    )
    notion_page_id: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )
    error_message: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    is_stale: Mapped[bool] = mapped_column(
        default=False,
        server_default="false",
        nullable=False,
    )

    project: Mapped["Project"] = relationship(back_populates="sections")
