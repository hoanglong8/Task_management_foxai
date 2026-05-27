"""API integration tests using SQLite in-memory DB."""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.database import Base, get_db
from backend.main import app
from backend.services.auth_service import seed_admin

TEST_DB_URL = "sqlite:///./test.db"
engine = create_engine(TEST_DB_URL, connect_args={"check_same_thread": False})
TestSessionLocal = sessionmaker(bind=engine)


def override_get_db():
    db = TestSessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture(scope="session", autouse=True)
def setup_db():
    Base.metadata.create_all(bind=engine)
    db = TestSessionLocal()
    seed_admin(db)
    db.close()
    yield
    Base.metadata.drop_all(bind=engine)
    import os
    if os.path.exists("test.db"):
        os.remove("test.db")


@pytest.fixture
def client(setup_db):
    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def admin_token(client):
    r = client.post("/auth/login", json={"email": "hoanglong208@gmail.com", "password": "change_me"})
    assert r.status_code == 200
    return r.json()["access_token"]


def auth_header(token):
    return {"Authorization": f"Bearer {token}"}


class TestAuth:
    def test_login_success(self, client):
        r = client.post("/auth/login", json={"email": "hoanglong208@gmail.com", "password": "change_me"})
        assert r.status_code == 200
        assert "access_token" in r.json()

    def test_login_wrong_password(self, client):
        r = client.post("/auth/login", json={"email": "hoanglong208@gmail.com", "password": "wrong"})
        assert r.status_code == 401

    def test_me(self, client, admin_token):
        r = client.get("/auth/me", headers=auth_header(admin_token))
        assert r.status_code == 200
        assert r.json()["email"] == "hoanglong208@gmail.com"
        assert r.json()["role"] == "admin"


class TestTasks:
    def test_create_task(self, client, admin_token):
        r = client.post("/tasks", json={
            "title": "Test Task",
            "owner_name": "Quốc Anh",
            "deadline": "2026-06-30",
        }, headers=auth_header(admin_token))
        assert r.status_code == 200
        data = r.json()
        assert data["title"] == "Test Task"
        assert data["status"] == "pending"

    def test_list_tasks(self, client, admin_token):
        r = client.get("/tasks", headers=auth_header(admin_token))
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_update_status(self, client, admin_token):
        # Create a task first
        r = client.post("/tasks", json={"title": "Update me", "owner_name": "Test", "deadline": "2026-06-30"},
                        headers=auth_header(admin_token))
        task_id = r.json()["id"]
        # Update it
        r = client.patch(f"/tasks/{task_id}", json={"status": "in_progress"},
                         headers=auth_header(admin_token))
        assert r.status_code == 200
        assert r.json()["status"] == "in_progress"

    def test_delete_task(self, client, admin_token):
        r = client.post("/tasks", json={"title": "Delete me", "owner_name": "Test", "deadline": "2026-06-30"},
                        headers=auth_header(admin_token))
        task_id = r.json()["id"]
        r = client.delete(f"/tasks/{task_id}", headers=auth_header(admin_token))
        assert r.status_code == 204

    def test_summary(self, client, admin_token):
        r = client.get("/tasks/summary", headers=auth_header(admin_token))
        assert r.status_code == 200
        data = r.json()
        assert "total" in data
        assert "pending" in data
        assert "completed" in data


class TestReports:
    def test_standup(self, client, admin_token):
        r = client.get("/reports/standup", headers=auth_header(admin_token))
        assert r.status_code == 200
        assert "report" in r.json()

    def test_weekly(self, client, admin_token):
        r = client.get("/reports/weekly", headers=auth_header(admin_token))
        assert r.status_code == 200
