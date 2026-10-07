"""Initial schema

Revision ID: 001
Revises:
Create Date: 2026-10-07
"""
import sqlalchemy as sa
from alembic import op

revision = "001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    if "runs" not in tables:
        op.create_table(
            "runs",
            sa.Column("run_id", sa.String(), primary_key=True),
            sa.Column("snapshot_date", sa.String(), nullable=False),
            sa.Column("started_at", sa.String(), nullable=False),
            sa.Column("finished_at", sa.String()),
            sa.Column("category", sa.String(), nullable=False),
            sa.Column("fx_source", sa.String()),
            sa.Column("channel_status", sa.String()),
        )
        op.create_index("ix_runs_started_at", "runs", ["started_at"])
    else:
        idx_names = {idx["name"] for idx in inspector.get_indexes("runs")}
        if "ix_runs_started_at" not in idx_names:
            op.create_index("ix_runs_started_at", "runs", ["started_at"])

    if "listings" not in tables:
        op.create_table(
            "listings",
            sa.Column("run_id", sa.String(), nullable=False),
            sa.Column("snapshot_date", sa.String(), nullable=False),
            sa.Column("channel", sa.String(), nullable=False),
            sa.Column("channel_type", sa.String(), nullable=False),
            sa.Column("market", sa.String(), nullable=False),
            sa.Column("rank", sa.Integer(), nullable=False),
            sa.Column("title", sa.String(), nullable=False),
            sa.Column("url", sa.String()),
            sa.Column("external_id", sa.String()),
            sa.Column("brand", sa.String(), nullable=False),
            sa.Column("model_key", sa.String(), nullable=False),
            sa.Column("price_local", sa.Float()),
            sa.Column("currency", sa.String(), nullable=False),
            sa.Column("price_eur", sa.Float()),
            sa.Column("offers", sa.Integer()),
            sa.Column("rating", sa.Float()),
            sa.Column("rating_count", sa.Integer()),
            sa.Column("sponsored", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("capacity_l", sa.Float()),
            sa.Column("power_w", sa.Integer()),
            sa.Column("dual_zone", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("claims", sa.String(), nullable=False, server_default="[]"),
            sa.Column("extra", sa.String(), nullable=False, server_default="{}"),
            sa.PrimaryKeyConstraint("run_id", "channel", "rank", name="pk_listings"),
        )
        op.create_index("ix_listings_model", "listings", ["model_key", "market", "snapshot_date"])
        op.create_index("ix_listings_date", "listings", ["snapshot_date", "market"])

    if "reviews" not in tables:
        op.create_table(
            "reviews",
            sa.Column("run_id", sa.String(), nullable=False),
            sa.Column("channel", sa.String(), nullable=False),
            sa.Column("market", sa.String(), nullable=False),
            sa.Column("model_key", sa.String(), nullable=False),
            sa.Column("brand", sa.String(), nullable=False),
            sa.Column("rating", sa.Float()),
            sa.Column("language", sa.String()),
            sa.Column("text", sa.String(), nullable=False),
        )

    if "fx_rates" not in tables:
        op.create_table(
            "fx_rates",
            sa.Column("run_id", sa.String(), nullable=False),
            sa.Column("rate_date", sa.String()),
            sa.Column("currency", sa.String(), nullable=False),
            sa.Column("per_eur", sa.Float(), nullable=False),
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    if "fx_rates" in tables:
        op.drop_table("fx_rates")
    if "reviews" in tables:
        op.drop_table("reviews")
    if "listings" in tables:
        idx_names = {idx["name"] for idx in inspector.get_indexes("listings")}
        if "ix_listings_date" in idx_names:
            op.drop_index("ix_listings_date", table_name="listings")
        if "ix_listings_model" in idx_names:
            op.drop_index("ix_listings_model", table_name="listings")
        op.drop_table("listings")
    if "runs" in tables:
        idx_names = {idx["name"] for idx in inspector.get_indexes("runs")}
        if "ix_runs_started_at" in idx_names:
            op.drop_index("ix_runs_started_at", table_name="runs")
        op.drop_table("runs")
