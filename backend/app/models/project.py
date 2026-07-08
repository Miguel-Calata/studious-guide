from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin


class ProjectStatus:
    DRAFT = "draft"
    EXTRACTING = "extracting"
    GENERATING = "generating"
    REVIEW = "review"
    COMPLETED = "completed"
    ARCHIVED = "archived"

    VALID_STATUSES = {
        DRAFT,
        EXTRACTING,
        GENERATING,
        REVIEW,
        COMPLETED,
        ARCHIVED,
    }

    TRANSITIONS: dict[str, set[str]] = {
        DRAFT: {EXTRACTING, GENERATING, ARCHIVED},
        EXTRACTING: {DRAFT, GENERATING, ARCHIVED},
        GENERATING: {REVIEW, ARCHIVED},
        REVIEW: {GENERATING, COMPLETED, ARCHIVED},
        COMPLETED: {GENERATING, ARCHIVED},
        ARCHIVED: {DRAFT},
    }

    @classmethod
    def is_valid_transition(cls, current: str, new: str) -> bool:
        if new not in cls.VALID_STATUSES:
            return False
        if current == new:
            return True
        return new in cls.TRANSITIONS.get(current, set())


class Project(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "projects"

    user_id: Mapped[str] = mapped_column(
        String(),
        ForeignKey("users.id"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    slug: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        nullable=False,
        index=True,
    )
    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    status: Mapped[str] = mapped_column(
        String(50),
        default=ProjectStatus.DRAFT,
        server_default=ProjectStatus.DRAFT,
        nullable=False,
    )
    merged_content: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    owner: Mapped["User"] = relationship(back_populates="projects")
    documents: Mapped[list["SourceDocument"]] = relationship(
        back_populates="project",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    sections: Mapped[list["CompendiumSection"]] = relationship(
        back_populates="project",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    is_published: Mapped[bool] = mapped_column(
        default=False,
        server_default="false",
        nullable=False,
    )
    s3_bucket: Mapped[str | None] = mapped_column(String(255), nullable=True)
    s3_key: Mapped[str | None] = mapped_column(String(500), nullable=True)
    public_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)

    def set_status(self, new_status: str) -> None:
        if not ProjectStatus.is_valid_transition(self.status, new_status):
            raise ValueError(
                f"Transición de estado inválida: {self.status} -> {new_status}"
            )
        self.status = new_status
