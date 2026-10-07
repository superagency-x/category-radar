"""Authenticated API entry point for the hosted Category Radar service."""

from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import datetime
from uuid import uuid4

from fastapi import Depends, FastAPI, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from .auth import AuthenticatedUser, get_current_user
from .db import get_engine, get_session
from .models import RadarProject, Workspace, WorkspaceMembership


class WorkspaceCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)

    @field_validator("name")
    @classmethod
    def strip_name(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("Workspace name cannot be blank")
        return normalized


class WorkspaceResponse(BaseModel):
    id: str
    name: str
    role: str
    created_at: datetime


class RadarProjectCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    category: str = Field(min_length=1, max_length=160)
    markets: list[str] = Field(min_length=1, max_length=10)
    competitor_brands: list[str] = Field(default_factory=list, max_length=20)

    @field_validator("name", "category")
    @classmethod
    def strip_required_text(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("Value cannot be blank")
        return normalized

    @field_validator("markets")
    @classmethod
    def normalize_markets(cls, values: list[str]) -> list[str]:
        normalized = [value.strip().upper() for value in values]
        if any(len(value) != 2 or not value.isalpha() for value in normalized):
            raise ValueError("Markets must use two-letter country codes")
        if len(set(normalized)) != len(normalized):
            raise ValueError("Markets must be unique")
        return normalized

    @field_validator("competitor_brands")
    @classmethod
    def normalize_brands(cls, values: list[str]) -> list[str]:
        normalized = [value.strip() for value in values]
        if any(not value for value in normalized):
            raise ValueError("Competitor brands cannot be blank")
        if len({value.casefold() for value in normalized}) != len(normalized):
            raise ValueError("Competitor brands must be unique")
        return normalized


class RadarProjectResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    workspace_id: str
    name: str
    category: str
    markets: list[str]
    competitor_brands: list[str]
    created_at: datetime


def create_app() -> FastAPI:
    @asynccontextmanager
    async def lifespan(_: FastAPI):
        yield

    application = FastAPI(
        title="Category Radar",
        description="Authenticated market intelligence workspace API",
        version="2.0.0",
        lifespan=lifespan,
    )

    @application.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "alive"}

    @application.get("/health/ready")
    async def readiness() -> dict[str, str]:
        try:
            with get_engine().connect() as connection:
                connection.execute(text("SELECT 1"))
        except (RuntimeError, SQLAlchemyError) as exc:
            raise HTTPException(status_code=503, detail="Database is unavailable") from exc
        return {"status": "ready"}

    @application.get("/api/v1/me")
    def me(user: AuthenticatedUser = Depends(get_current_user)) -> dict[str, str]:
        return {"id": user.id}

    @application.get("/api/v1/workspaces", response_model=list[WorkspaceResponse])
    def list_workspaces(
        user: AuthenticatedUser = Depends(get_current_user),
        session: Session = Depends(get_session),
    ) -> list[WorkspaceResponse]:
        rows = session.execute(
            select(Workspace, WorkspaceMembership.role)
            .join(WorkspaceMembership, WorkspaceMembership.workspace_id == Workspace.id)
            .where(WorkspaceMembership.user_id == user.id)
            .order_by(Workspace.created_at)
        ).all()
        return [
            WorkspaceResponse(id=workspace.id, name=workspace.name, role=role, created_at=workspace.created_at)
            for workspace, role in rows
        ]

    @application.post(
        "/api/v1/workspaces",
        response_model=WorkspaceResponse,
        status_code=status.HTTP_201_CREATED,
    )
    def create_workspace(
        payload: WorkspaceCreate,
        user: AuthenticatedUser = Depends(get_current_user),
        session: Session = Depends(get_session),
    ) -> WorkspaceResponse:
        workspace = Workspace(id=str(uuid4()), name=payload.name)
        membership = WorkspaceMembership(id=str(uuid4()), workspace_id=workspace.id, user_id=user.id, role="owner")
        with session.begin():
            session.add(workspace)
            session.add(membership)
            session.flush()
        return WorkspaceResponse(
            id=workspace.id,
            name=workspace.name,
            role=membership.role,
            created_at=workspace.created_at,
        )

    @application.get("/api/v1/workspaces/{workspace_id}", response_model=WorkspaceResponse)
    def get_workspace(
        workspace_id: str,
        user: AuthenticatedUser = Depends(get_current_user),
        session: Session = Depends(get_session),
    ) -> WorkspaceResponse:
        row = session.execute(
            select(Workspace, WorkspaceMembership.role)
            .join(WorkspaceMembership, WorkspaceMembership.workspace_id == Workspace.id)
            .where(Workspace.id == workspace_id, WorkspaceMembership.user_id == user.id)
        ).one_or_none()
        if row is None:
            # Return the same response for missing and unauthorized workspaces.
            raise HTTPException(status_code=404, detail="Workspace not found")
        workspace, role = row
        return WorkspaceResponse(id=workspace.id, name=workspace.name, role=role, created_at=workspace.created_at)

    @application.get("/api/v1/workspaces/{workspace_id}/projects", response_model=list[RadarProjectResponse])
    def list_projects(
        workspace_id: str,
        user: AuthenticatedUser = Depends(get_current_user),
        session: Session = Depends(get_session),
    ) -> list[RadarProjectResponse]:
        rows = (
            session.execute(
                select(RadarProject)
                .join(WorkspaceMembership, WorkspaceMembership.workspace_id == RadarProject.workspace_id)
                .where(RadarProject.workspace_id == workspace_id, WorkspaceMembership.user_id == user.id)
                .order_by(RadarProject.created_at)
            )
            .scalars()
            .all()
        )
        return [RadarProjectResponse.model_validate(row, from_attributes=True) for row in rows]

    @application.post(
        "/api/v1/workspaces/{workspace_id}/projects",
        response_model=RadarProjectResponse,
        status_code=status.HTTP_201_CREATED,
    )
    def create_project(
        workspace_id: str,
        payload: RadarProjectCreate,
        user: AuthenticatedUser = Depends(get_current_user),
        session: Session = Depends(get_session),
    ) -> RadarProjectResponse:
        is_member = session.execute(
            select(WorkspaceMembership.id).where(
                WorkspaceMembership.workspace_id == workspace_id,
                WorkspaceMembership.user_id == user.id,
            )
        ).scalar_one_or_none()
        if is_member is None:
            raise HTTPException(status_code=404, detail="Workspace not found")

        project = RadarProject(
            id=str(uuid4()),
            workspace_id=workspace_id,
            name=payload.name,
            category=payload.category,
            markets=payload.markets,
            competitor_brands=payload.competitor_brands,
        )
        try:
            session.add(project)
            session.flush()
            session.commit()
        except IntegrityError as exc:
            session.rollback()
            raise HTTPException(status_code=409, detail="A project with this name already exists") from exc
        return RadarProjectResponse.model_validate(project, from_attributes=True)

    return application


app = create_app()
