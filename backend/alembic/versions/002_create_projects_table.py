"""create_projects_table

Revision ID: 002
Revises: 001
Create Date: 2026-07-06

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "projects",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("slug", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column(
            "status",
            sa.String(length=50),
            server_default="draft",
            nullable=False,
        ),
        sa.Column("merged_content", sa.Text(), nullable=True),
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
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
    )
    op.create_index(op.f("ix_projects_user_id"), "projects", ["user_id"])
    op.create_index(op.f("ix_projects_slug"), "projects", ["slug"], unique=True)


def downgrade() -> None:
    op.drop_index(op.f("ix_projects_slug"), table_name="projects")
    op.drop_index(op.f("ix_projects_user_id"), table_name="projects")
    op.drop_table("projects")
