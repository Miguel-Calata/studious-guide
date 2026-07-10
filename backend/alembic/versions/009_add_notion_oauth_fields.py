"""add OAuth fields to notion_configs

Revision ID: 009
Revises: 008
Create Date: 2026-07-09 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '009'
down_revision: Union[str, None] = '008'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('notion_configs', sa.Column('refresh_token_encrypted', sa.Text(), nullable=True))
    op.add_column('notion_configs', sa.Column('bot_id', sa.String(length=64), nullable=True))
    op.add_column('notion_configs', sa.Column('workspace_id', sa.String(length=64), nullable=True))
    op.add_column('notion_configs', sa.Column('owner_user_id', sa.String(length=64), nullable=True))
    op.add_column('notion_configs', sa.Column('owner_email', sa.String(length=255), nullable=True))
    op.add_column('notion_configs', sa.Column('token_expires_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('notion_configs', sa.Column('connected_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('notion_configs', sa.Column('last_refreshed_at', sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column('notion_configs', 'last_refreshed_at')
    op.drop_column('notion_configs', 'connected_at')
    op.drop_column('notion_configs', 'token_expires_at')
    op.drop_column('notion_configs', 'owner_email')
    op.drop_column('notion_configs', 'owner_user_id')
    op.drop_column('notion_configs', 'workspace_id')
    op.drop_column('notion_configs', 'bot_id')
    op.drop_column('notion_configs', 'refresh_token_encrypted')
