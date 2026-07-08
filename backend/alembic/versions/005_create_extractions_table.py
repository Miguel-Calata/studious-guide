"""create extractions table

Revision ID: 005
Revises: 7bb70c4aeb77
Create Date: 2026-07-07 23:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '005'
down_revision: Union[str, None] = '7bb70c4aeb77'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'extractions',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('source_document_id', sa.String(), nullable=False),
        sa.Column('content', sa.Text(), server_default='', nullable=False),
        sa.Column('model_used', sa.String(length=100), nullable=True),
        sa.Column('input_tokens', sa.Integer(), nullable=True),
        sa.Column('output_tokens', sa.Integer(), nullable=True),
        sa.Column('cost_usd', sa.Numeric(10, 6), nullable=True),
        sa.Column('status', sa.String(length=50), server_default='pending', nullable=False),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('audit_completed', sa.Boolean(), server_default='false', nullable=False),
        sa.Column('audit_content', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['source_document_id'], ['source_documents.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('source_document_id'),
    )
    op.create_index('ix_extractions_source_document_id', 'extractions', ['source_document_id'])


def downgrade() -> None:
    op.drop_index('ix_extractions_source_document_id', table_name='extractions')
    op.drop_table('extractions')
