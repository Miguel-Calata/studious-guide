"""Add model_used column to ecos_maps.

Tracks which LLM model was used to generate the ecos map draft,
matching the pattern already used by Extraction and CompendiumSection.
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "015_add_model_used_to_ecos_maps"
down_revision = "014_ecos_autopopulate_v3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "ecos_maps",
        sa.Column("model_used", sa.String(100), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("ecos_maps", "model_used")
