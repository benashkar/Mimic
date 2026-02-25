"""
Tests for the /api/health endpoint.

Verifies the health check returns correct status, payload, and content type.
"""


def test_health_returns_200(client):
    """Health endpoint should return HTTP 200."""
    response = client.get("/api/health")
    assert response.status_code == 200


def test_health_returns_correct_json(client):
    """Health endpoint should return expected JSON payload."""
    response = client.get("/api/health")
    data = response.get_json()
    assert data["status"] == "ok"
    assert data["service"] == "mimic-api"


def test_health_content_type_is_json(client):
    """Health endpoint should return application/json content type."""
    response = client.get("/api/health")
    assert "application/json" in response.content_type
