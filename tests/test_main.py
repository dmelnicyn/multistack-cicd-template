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
