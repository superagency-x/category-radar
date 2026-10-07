"""Tests for Category Radar SaaS API (Workspaces, Projects, Multi-Tenancy)."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from category_radar.saas.app import create_app
from category_radar.saas.auth import AuthenticatedUser, get_current_user
from category_radar.saas.db import get_session
from category_radar.saas.models import Base


@pytest.fixture
def saas_db():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    TestingSessionLocal = sessionmaker(bind=engine, expire_on_commit=False)

    yield TestingSessionLocal

    Base.metadata.drop_all(engine)


@pytest.fixture
def test_user():
    return AuthenticatedUser(id="user_test_123")


@pytest.fixture
def other_user():
    return AuthenticatedUser(id="user_other_456")


@pytest.fixture
def client(saas_db, test_user):
    app = create_app()

    def override_get_session():
        with saas_db() as session:
            yield session

    def override_get_current_user():
        return test_user

    app.dependency_overrides[get_session] = override_get_session
    app.dependency_overrides[get_current_user] = override_get_current_user

    with TestClient(app) as test_client:
        yield test_client


def test_saas_health(client):
    res = client.get("/health")
    assert res.status_code == 200
    assert res.json() == {"status": "alive"}


def test_saas_me(client, test_user):
    res = client.get("/api/v1/me")
    assert res.status_code == 200
    assert res.json() == {"id": test_user.id}


def test_workspace_crud_and_isolation(client, saas_db, other_user):
    # 1. Create workspace
    res = client.post("/api/v1/workspaces", json={"name": "European Growth Brand"})
    assert res.status_code == 201
    data = res.json()
    ws_id = data["id"]
    assert data["name"] == "European Growth Brand"
    assert data["role"] == "owner"

    # 2. List workspaces
    res = client.get("/api/v1/workspaces")
    assert res.status_code == 200
    workspaces = res.json()
    assert len(workspaces) == 1
    assert workspaces[0]["id"] == ws_id

    # 3. Get single workspace
    res = client.get(f"/api/v1/workspaces/{ws_id}")
    assert res.status_code == 200
    assert res.json()["id"] == ws_id

    # 4. Create radar project under workspace
    proj_res = client.post(
        f"/api/v1/workspaces/{ws_id}/projects",
        json={
            "name": "Air Fryers Central Europe",
            "category": "Small Domestic Appliances",
            "markets": ["DE", "AT", "PL"],
            "competitor_brands": ["Ninja", "Cosori", "Tefal"],
        },
    )
    assert proj_res.status_code == 201
    proj_data = proj_res.json()
    assert proj_data["name"] == "Air Fryers Central Europe"
    assert proj_data["markets"] == ["DE", "AT", "PL"]

    # 5. List projects
    res = client.get(f"/api/v1/workspaces/{ws_id}/projects")
    assert res.status_code == 200
    projects = res.json()
    assert len(projects) == 1
    assert projects[0]["name"] == "Air Fryers Central Europe"

    # 6. Tenant isolation test: another user should not see this workspace
    app = client.app
    app.dependency_overrides[get_current_user] = lambda: other_user

    res_other = client.get(f"/api/v1/workspaces/{ws_id}")
    assert res_other.status_code == 404

    res_other_list = client.get("/api/v1/workspaces")
    assert res_other_list.status_code == 200
    assert len(res_other_list.json()) == 0


def test_project_name_duplicate_conflict(client):
    res = client.post("/api/v1/workspaces", json={"name": "Retail Insights Lab"})
    assert res.status_code == 201
    ws_id = res.json()["id"]

    body = {
        "name": "Roborock Vacuum Track",
        "category": "Robot Vacuums",
        "markets": ["DE", "CH"],
        "competitor_brands": ["Dreame", "Ecovacs"],
    }

    res1 = client.post(f"/api/v1/workspaces/{ws_id}/projects", json=body)
    assert res1.status_code == 201

    # Conflict on same project name in same workspace
    res2 = client.post(f"/api/v1/workspaces/{ws_id}/projects", json=body)
    assert res2.status_code == 409
