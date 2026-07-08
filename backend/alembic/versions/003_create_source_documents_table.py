"""create_source_documents_table

Revision ID: 003
Revises: 002
Create Date: 2026-07-07

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "003"
down_revision: Union[str, None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "source_documents",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("project_id", sa.String(), nullable=False),
        sa.Column("filename", sa.String(length=500), nullable=False),
        sa.Column("file_path", sa.String(length=1000), nullable=False),
        sa.Column("file_size", sa.BigInteger(), nullable=False),
        sa.Column("document_type", sa.String(length=50), nullable=True),
        sa.Column(
            "status",
            sa.String(length=50),
            server_default="uploaded",
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
    )
    op.create_index(
        op.f("ix_source_documents_project_id"),
        "source_documents",
        ["project_id"],
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_source_documents_project_id"),
        table_name="source_documents",
    )
    op.drop_table("source_documents")
