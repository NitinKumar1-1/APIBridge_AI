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


def test_api_diff_endpoint_success():
    """Verify that POST /api/diff processes valid OpenAPI specs and returns 200 with diff summary."""
    v1 = "openapi: 3.0.0\ninfo:\n  title: Test\n  version: 1.0\npaths:\n  /items:\n    get:\n      responses:\n        '200':\n          description: OK"
    v2 = "openapi: 3.0.0\ninfo:\n  title: Test\n  version: 2.0\npaths:\n  /items:\n    get:\n      responses:\n        '200':\n          description: OK\n  /new:\n    get:\n      responses:\n        '200':\n          description: OK"

    response = client.post("/api/diff", json={"spec_v1": v1, "spec_v2": v2})
    assert response.status_code == 200
    data = response.json()
    assert data["is_compatible"] is True
    assert data["non_breaking_count"] == 1
    assert data["breaking_count"] == 0
    assert len(data["changes"]) == 1
    assert data["changes"][0]["change_type"] == "PATH_ADDED"


def test_api_diff_endpoint_validation_error():
    """Verify that POST /api/diff returns 400 when malformed specs are provided."""
    response = client.post("/api/diff", json={"spec_v1": "bad: [unclosed", "spec_v2": "openapi: 3.0.0\npaths: {}"})
    assert response.status_code == 400
    assert "could not be parsed" in response.json()["detail"]


def test_api_samples_endpoint():
    """Verify that GET /api/samples returns sample v1 and v2 specifications."""
    response = client.get("/api/samples")
    assert response.status_code == 200
    data = response.json()
    assert "v1" in data and len(data["v1"]) > 0
    assert "v2" in data and len(data["v2"]) > 0
    assert "v1_user_service.yaml" in data["v1_filename"]
    assert "v2_user_service.yaml" in data["v2_filename"]


def test_api_analyze_fixes_endpoint_success():
    """Verify that POST /api/analyze-fixes evaluates compatibility and generates fixes."""
    v1 = """
    openapi: 3.0.0
    info:
      title: API
      version: 1.0.0
    paths:
      /users:
        post:
          requestBody:
            required: true
            content:
              application/json:
                schema:
                  type: object
                  required:
                    - full_name
                  properties:
                    full_name:
                      type: string
          responses:
            '201':
              description: Created
    """
    v2 = """
    openapi: 3.0.0
    info:
      title: API
      version: 2.0.0
    paths:
      /users:
        post:
          requestBody:
            required: true
            content:
              application/json:
                schema:
                  type: object
                  required:
                    - first_name
                    - last_name
                  properties:
                    first_name:
                      type: string
                    last_name:
                      type: string
          responses:
            '201':
              description: Created
    """
    sample_req = {"full_name": "Bob Vance"}
    response = client.post(
        "/api/analyze-fixes",
        json={
            "spec_v1": v1,
            "spec_v2": v2,
            "sample_request": sample_req,
            "target_path": "/users",
            "target_method": "POST",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["total_changes"] > 0
    assert "sample_request_transformed" in data
    assert data["sample_request_transformed"]["first_name"] == "Bob"
    assert data["sample_request_transformed"]["last_name"] == "Vance"
    assert data["payload_validation"]["is_valid"] is True

