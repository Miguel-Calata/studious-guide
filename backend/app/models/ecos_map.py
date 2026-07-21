from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDMixin


class EcosMapStatus:
    DRAFT = "draft"
    APPROVED = "approved"

    VALID_STATUSES = {DRAFT, APPROVED}


class EcosMapOrigin:
    SEED = "seed"
    AUTOPOPULATED = "autopopulated"
    MANUAL = "manual"

    VALID_ORIGINS = {SEED, AUTOPOPULATED, MANUAL}


class EcosMap(UUIDMixin, TimestampMixin, Base):
    """
    Mapa de ecos por patología y versión.

    El campo `sections` es un JSONB con la forma
        { "<section_number>": ["eco1", "eco2", ...], ... }
    cubriendo las 11 secciones. Versionado espejo del patrón
    `prompt_templates`: una nueva versión desactiva la anterior; la
    activa es la única que el pipeline de producción consume.

    Trazabilidad: cada CompendiumSection registra
    `ecos_map_version` para que se pueda reconstruir qué mapa usó
    cada generación histórica.
    """

    __tablename__ = "ecos_maps"
    __table_args__ = (
        UniqueConstraint(
            "pathology_key",
            "version",
            name="uq_ecos_maps_pathology_version",
        ),
    )

    pathology_key: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        index=True,
    )
    pathology_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    version: Mapped[int] = mapped_column(
        Integer,
        default=1,
        server_default="1",
        nullable=False,
    )
    sections: Mapped[dict] = mapped_column(
        JSON,
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        String(50),
        default=EcosMapStatus.DRAFT,
        server_default=EcosMapStatus.DRAFT,
        nullable=False,
    )
    origin: Mapped[str] = mapped_column(
        String(50),
        default=EcosMapOrigin.MANUAL,
        server_default=EcosMapOrigin.MANUAL,
        nullable=False,
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        server_default="false",
        nullable=False,
    )
    approved_by: Mapped[str | None] = mapped_column(
        String(),
        ForeignKey("users.id"),
        nullable=True,
    )
    approved_at: Mapped[DateTime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    description: Mapped[str | None] = mapped_column(
        String(1000),
        nullable=True,
    )
