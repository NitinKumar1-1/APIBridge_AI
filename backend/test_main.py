"""Tests for APIBridge AI FastAPI Backend
"""

from fastapi.testclient import TestClient
from main import app

client = TestClient(app)


def test_root_endpoint():
    """Verify that root endpoint returns service metadata and running status."""
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "APIBridge AI"
    assert data["status"] == "running"
    assert data["version"] == "0.1.0"
    assert "operational" in data["message"].lower()


def test_health_check_endpoint():
    """Verify that health check endpoint returns 200 and healthy status."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["service"] == "apibridge-backend"


def test_nonexistent_endpoint_returns_404():
    """Verify that unmapped routes return 404 Not Found."""
    response = client.get("/nonexistent-endpoint")
    assert response.status_code == 404
