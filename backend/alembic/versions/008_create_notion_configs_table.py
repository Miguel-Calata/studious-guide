"""create notion_configs table

Revision ID: 008
Revises: 007
Create Date: 2026-07-08 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '008'
down_revision: Union[str, None] = '007'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'notion_configs',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('user_id', sa.String(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('api_key_encrypted', sa.Text(), nullable=False),
        sa.Column('workspace_name', sa.String(length=255), nullable=True),
        sa.Column('default_parent_page_id', sa.String(length=255), nullable=True),
        sa.Column('is_connected', sa.Boolean(), server_default='false', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', name='uq_notion_configs_user_id'),
    )
    op.create_index('ix_notion_configs_user_id', 'notion_configs', ['user_id'])


def downgrade() -> None:
    op.drop_index('ix_notion_configs_user_id', table_name='notion_configs')
    op.drop_table('notion_configs')
