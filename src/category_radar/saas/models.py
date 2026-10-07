"""Relational models for customer identity and workspace ownership."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, CheckConstraint, DateTime, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Workspace(Base):
    __tablename__ = "saas_workspaces"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class WorkspaceMembership(Base):
    __tablename__ = "saas_workspace_memberships"
    __table_args__ = (
        UniqueConstraint("workspace_id", "user_id", name="uq_saas_workspace_memberships_workspace_user"),
        CheckConstraint("role IN ('owner', 'admin', 'member')", name="ck_saas_workspace_memberships_role"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    workspace_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("saas_workspaces.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # Supabase Auth subject. The auth provider remains the source of truth for user identity.
    user_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    role: Mapped[str] = mapped_column(String(16), nullable=False, default="member")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class RadarProject(Base):
    """A workspace's market scope; collection runs are attached in a later release."""

    __tablename__ = "saas_radar_projects"
    __table_args__ = (UniqueConstraint("workspace_id", "name", name="uq_saas_radar_projects_workspace_name"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    workspace_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("saas_workspaces.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    category: Mapped[str] = mapped_column(String(160), nullable=False)
    markets: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    competitor_brands: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
