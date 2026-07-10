import base64
import hashlib
from datetime import datetime
from typing import TYPE_CHECKING

from cryptography.fernet import Fernet
from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text
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
    access_token_encrypted: Mapped[str] = mapped_column(
        "api_key_encrypted",
        Text,
        nullable=False,
    )
    refresh_token_encrypted: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
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
    bot_id: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
    )
    workspace_id: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
    )
    owner_user_id: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
    )
    owner_email: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )
    token_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    connected_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    last_refreshed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    user: Mapped["User"] = relationship(back_populates="notion_config")

    @property
    def access_token(self) -> str:
        return _get_fernet().decrypt(self.access_token_encrypted.encode()).decode()

    @access_token.setter
    def access_token(self, value: str) -> None:
        self.access_token_encrypted = _get_fernet().encrypt(value.encode()).decode()

    # Backward-compat alias used by existing service/client code.
    @property
    def api_key(self) -> str:
        return self.access_token

    @api_key.setter
    def api_key(self, value: str) -> None:
        self.access_token = value

    @property
    def refresh_token(self) -> str | None:
        if self.refresh_token_encrypted is None:
            return None
        return _get_fernet().decrypt(self.refresh_token_encrypted.encode()).decode()

    @refresh_token.setter
    def refresh_token(self, value: str | None) -> None:
        if value is None:
            self.refresh_token_encrypted = None
        else:
            self.refresh_token_encrypted = _get_fernet().encrypt(value.encode()).decode()

    def clear_tokens(self) -> None:
        """Disconnect: wipe stored tokens and mark as not connected."""
        self.access_token_encrypted = ""
        self.refresh_token_encrypted = None
        self.is_connected = False
        self.bot_id = None
        self.workspace_id = None
        self.owner_user_id = None
        self.owner_email = None
        self.token_expires_at = None
