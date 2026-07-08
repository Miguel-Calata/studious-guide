from sqlalchemy import Boolean, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin


class User(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "users"

    email: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        nullable=False,
        index=True,
    )
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    role: Mapped[str] = mapped_column(
        String(20),
        default="creator",
        server_default="creator",
        nullable=False,
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        server_default="true",
        nullable=False,
    )

    projects: Mapped[list["Project"]] = relationship(
        back_populates="owner",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    notion_config: Mapped["NotionConfig | None"] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
