from sqlalchemy import BigInteger, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin


class SourceDocumentStatus:
    UPLOADED = "uploaded"
    EXTRACTING = "extracting"
    EXTRACTED = "extracted"
    ERROR = "error"

    VALID_STATUSES = {UPLOADED, EXTRACTING, EXTRACTED, ERROR}


class SourceDocument(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "source_documents"

    project_id: Mapped[str] = mapped_column(
        String(),
        ForeignKey("projects.id"),
        nullable=False,
        index=True,
    )
    filename: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
    )
    file_path: Mapped[str] = mapped_column(
        String(1000),
        nullable=False,
    )
    file_size: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
    )
    document_type: Mapped[str] = mapped_column(
        String(50),
        default="article",
        server_default="article",
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        String(50),
        default=SourceDocumentStatus.UPLOADED,
        server_default=SourceDocumentStatus.UPLOADED,
        nullable=False,
    )

    project: Mapped["Project"] = relationship(back_populates="documents")
    extraction: Mapped["Extraction | None"] = relationship(
        back_populates="source_document",
        uselist=False,
    )

    def set_status(self, new_status: str) -> None:
        if new_status not in SourceDocumentStatus.VALID_STATUSES:
            raise ValueError(f"Estado inválido: {new_status}")
        self.status = new_status
