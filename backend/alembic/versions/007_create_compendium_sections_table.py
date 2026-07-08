"""create compendium_sections table

Revision ID: 007
Revises: 006
Create Date: 2026-07-08 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '007'
down_revision: Union[str, None] = '006'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'compendium_sections',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('project_id', sa.String(), sa.ForeignKey('projects.id'), nullable=False),
        sa.Column('section_number', sa.Integer(), nullable=False),
        sa.Column('section_name', sa.String(length=255), nullable=False),
        sa.Column('content', sa.Text(), server_default='', nullable=False),
        sa.Column('model_used', sa.String(length=100), nullable=True),
        sa.Column('dosification', sa.String(length=10), server_default='STANDARD', nullable=False),
        sa.Column('input_tokens', sa.Integer(), nullable=True),
        sa.Column('output_tokens', sa.Integer(), nullable=True),
        sa.Column('cost_usd', sa.Numeric(10, 6), nullable=True),
        sa.Column('status', sa.String(length=50), server_default='pending', nullable=False),
        sa.Column('prompt_version', sa.String(length=50), nullable=True),
        sa.Column('notion_page_id', sa.String(length=255), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('project_id', 'section_number', name='uq_compendium_sections_project_section'),
    )
    op.create_index('ix_compendium_sections_project_id', 'compendium_sections', ['project_id'])


def downgrade() -> None:
    op.drop_index('ix_compendium_sections_project_id', table_name='compendium_sections')
    op.drop_table('compendium_sections')
