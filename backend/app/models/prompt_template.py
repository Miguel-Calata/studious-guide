from sqlalchemy import Boolean, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDMixin


class PromptTemplate(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "prompt_templates"

    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )
    content: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    version: Mapped[int] = mapped_column(
        Integer,
        default=1,
        server_default="1",
        nullable=False,
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        server_default="true",
        nullable=False,
    )
    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
