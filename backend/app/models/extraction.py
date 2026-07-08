from sqlalchemy import Boolean, ForeignKey, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin


class ExtractionStatus:
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"

    VALID_STATUSES = {PENDING, PROCESSING, COMPLETED, FAILED}


class Extraction(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "extractions"

    source_document_id: Mapped[str] = mapped_column(
        String(),
        ForeignKey("source_documents.id"),
        unique=True,
        nullable=False,
        index=True,
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
        default=ExtractionStatus.PENDING,
        server_default=ExtractionStatus.PENDING,
        nullable=False,
    )
    error_message: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    audit_completed: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        server_default="false",
        nullable=False,
    )
    audit_content: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    source_document: Mapped["SourceDocument"] = relationship(back_populates="extraction")
