import pytest

from app import create_app
from db import init_db


@pytest.fixture()
def app(tmp_path):
    database = tmp_path / "focusboard-test.sqlite"
    app = create_app(
        {
            "TESTING": True,
            "SECRET_KEY": "test",
            "DATABASE": str(database),
        }
    )
    with app.app_context():
        init_db()
    yield app


@pytest.fixture()
def client(app):
    return app.test_client()


def register_and_login(client):
    client.post(
        "/register",
        data={
            "username": "demo",
            "email": "demo@example.com",
            "password": "password123",
            "confirmation": "password123",
        },
        follow_redirects=True,
    )
    return client.post(
        "/login",
        data={"username": "demo", "password": "password123"},
        follow_redirects=True,
    )


def test_auth_project_task_flow(client):
    response = register_and_login(client)
    assert b"Dashboard" in response.data

    response = client.post(
        "/projects/new",
        data={
            "name": "Master Application",
            "description": "Prepare documents and deadlines",
            "deadline": "2026-12-31",
            "color": "green",
        },
        follow_redirects=True,
    )
    assert b"Master Application" in response.data

    client.post(
        "/labels/new",
        data={"name": "University", "color": "blue", "project_id": "1"},
        follow_redirects=True,
    )

    response = client.post(
        "/projects/1/tasks/new",
        data={
            "title": "Write motivation letter",
            "notes": "Draft and revise",
            "status": "todo",
            "priority": "high",
            "due_date": "2026-11-15",
            "estimated_minutes": "90",
            "labels": ["1"],
        },
        follow_redirects=True,
    )
    assert b"Write motivation letter" in response.data
    assert b"University" in response.data

    response = client.post(
        "/tasks/1/status",
        data={"status": "in_progress"},
        follow_redirects=True,
    )
    assert b"In Progress" in response.data

    response = client.get("/smart-plan")
    assert b"Recommended tasks" in response.data
    assert b"Write motivation letter" in response.data
    assert b"score" in response.data

    response = client.get("/export/tasks.csv")
    assert response.status_code == 200
    assert b"Write motivation letter" in response.data


def test_login_required_redirect(client):
    response = client.get("/dashboard", follow_redirects=True)
    assert b"Log in" in response.data
