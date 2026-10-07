"""Add workspace-owned radar project configuration.

Revision ID: 003
Revises: 002
Create Date: 2026-10-08
"""

import sqlalchemy as sa
from alembic import op

revision = "003"
down_revision = "002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "saas_radar_projects",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("workspace_id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("category", sa.String(length=160), nullable=False),
        sa.Column("markets", sa.JSON(), nullable=False),
        sa.Column("competitor_brands", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["workspace_id"], ["saas_workspaces.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("workspace_id", "name", name="uq_saas_radar_projects_workspace_name"),
    )
    op.create_index("ix_saas_radar_projects_workspace_id", "saas_radar_projects", ["workspace_id"])


def downgrade() -> None:
    op.drop_index("ix_saas_radar_projects_workspace_id", table_name="saas_radar_projects")
    op.drop_table("saas_radar_projects")
