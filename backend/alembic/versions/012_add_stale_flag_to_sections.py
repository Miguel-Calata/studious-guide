"""Add `is_stale` flag to `compendium_sections`.

When a section is regenerated, all downstream sections (higher
section_number) that were generated from the old content are
marked stale so the clinician knows they may be internally
inconsistent.
"""

from alembic import op
import sqlalchemy as sa


revision = "012_add_stale_flag"
down_revision = "011_ecos_maps"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "compendium_sections",
        sa.Column(
            "is_stale",
            sa.Boolean(),
            server_default="false",
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_column("compendium_sections", "is_stale")
