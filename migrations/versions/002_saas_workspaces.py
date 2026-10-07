"""Add identity-independent SaaS workspaces and memberships.

Revision ID: 002
Revises: 001
Create Date: 2026-10-08
"""

import sqlalchemy as sa
from alembic import op

revision = "002"
down_revision = "001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "saas_workspaces",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_table(
        "saas_workspace_memberships",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("workspace_id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=128), nullable=False),
        sa.Column("role", sa.String(length=16), nullable=False, server_default="member"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["workspace_id"], ["saas_workspaces.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("workspace_id", "user_id", name="uq_saas_workspace_memberships_workspace_user"),
        sa.CheckConstraint("role IN ('owner', 'admin', 'member')", name="ck_saas_workspace_memberships_role"),
    )
    op.create_index("ix_saas_workspace_memberships_workspace_id", "saas_workspace_memberships", ["workspace_id"])
    op.create_index("ix_saas_workspace_memberships_user_id", "saas_workspace_memberships", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_saas_workspace_memberships_user_id", table_name="saas_workspace_memberships")
    op.drop_index("ix_saas_workspace_memberships_workspace_id", table_name="saas_workspace_memberships")
    op.drop_table("saas_workspace_memberships")
    op.drop_table("saas_workspaces")
