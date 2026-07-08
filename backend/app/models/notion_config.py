import base64
import hashlib
from typing import TYPE_CHECKING

from cryptography.fernet import Fernet
from sqlalchemy import Boolean, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.config import settings
from app.models.base import Base, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.models.user import User


def _get_fernet() -> Fernet:
    key = hashlib.sha256(settings.secret_key.encode()).digest()
    return Fernet(base64.urlsafe_b64encode(key))


class NotionConfig(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "notion_configs"

    user_id: Mapped[str] = mapped_column(
        String(),
        ForeignKey("users.id"),
        unique=True,
        nullable=False,
        index=True,
    )
    api_key_encrypted: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    workspace_name: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )
    default_parent_page_id: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )
    is_connected: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        server_default="false",
        nullable=False,
    )

    user: Mapped["User"] = relationship(back_populates="notion_config")

    @property
    def api_key(self) -> str:
        return _get_fernet().decrypt(self.api_key_encrypted.encode()).decode()

    @api_key.setter
    def api_key(self, value: str) -> None:
        self.api_key_encrypted = _get_fernet().encrypt(value.encode()).decode()
