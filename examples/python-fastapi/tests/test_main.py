"""Tests for the FastAPI application."""

from fastapi.testclient import TestClient

from ai_cicd_demo.main import app

client = TestClient(app)


def test_health_check() -> None:
    """Test that health endpoint returns ok status."""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_get_item() -> None:
    """Test that item endpoint returns correct item data."""
    response = client.get("/items/42")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == 42
    assert data["name"] == "Item 42"
    assert data["description"] == "This is item number 42"


def test_create_user() -> None:
    """Test creating a new user."""
    response = client.post(
        "/users",
        json={
            "username": "testuser",
            "email": "test@example.com",
            "full_name": "Test User",
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert data["username"] == "testuser"
    assert data["email"] == "test@example.com"
    assert data["full_name"] == "Test User"
    assert "id" in data


def test_create_user_duplicate_username() -> None:
    """Test that duplicate username returns 400."""
    # Create first user
    client.post(
        "/users",
        json={"username": "duplicate", "email": "first@example.com"},
    )
    # Try to create duplicate
    response = client.post(
        "/users",
        json={"username": "duplicate", "email": "second@example.com"},
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "Username already exists"


def test_get_user() -> None:
    """Test getting a user by ID."""
    # Create a user first
    create_response = client.post(
        "/users",
        json={"username": "getuser", "email": "get@example.com"},
    )
    user_id = create_response.json()["id"]

    response = client.get(f"/users/{user_id}")
    assert response.status_code == 200
    assert response.json()["username"] == "getuser"


def test_get_user_not_found() -> None:
    """Test 404 when user doesn't exist."""
    response = client.get("/users/99999")
    assert response.status_code == 404
    assert response.json()["detail"] == "User not found"


def test_list_users() -> None:
    """Test listing all users."""
    response = client.get("/users")
    assert response.status_code == 200
    assert isinstance(response.json(), list)
