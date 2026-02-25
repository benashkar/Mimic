"""
Tests for routes/auth.py — login, me, logout endpoints.

Google token verification is mocked via the mock_verify_google_token fixture.
"""
import json


class TestLoginRoute:
    """Tests for POST /api/auth/login."""

    def test_login_valid_token(
        self, client, db_session, mock_verify_google_token
    ):
        """Valid Google token returns JWT and user dict."""
        resp = client.post(
            "/api/auth/login",
            data=json.dumps({"token": "valid-google-id-token"}),
            content_type="application/json",
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert "token" in data
        assert data["user"]["email"] == "testuser@plmediaagency.com"

    def test_login_wrong_domain(
        self, client, db_session, mock_verify_google_token
    ):
        """Google token with wrong email domain returns 403."""
        mock_verify_google_token.return_value = {
            "sub": "google-wrong-domain",
            "email": "hacker@gmail.com",
            "name": "Hacker",
            "picture": "",
        }
        resp = client.post(
            "/api/auth/login",
            data=json.dumps({"token": "wrong-domain-token"}),
            content_type="application/json",
        )
        assert resp.status_code == 403

    def test_login_missing_token(self, client, db_session):
        """POST /login with no token returns 400."""
        resp = client.post(
            "/api/auth/login",
            data=json.dumps({}),
            content_type="application/json",
        )
        assert resp.status_code == 400


class TestMeRoute:
    """Tests for GET /api/auth/me."""

    def test_me_without_token(self, client, db_session):
        """GET /me without token returns 401."""
        resp = client.get("/api/auth/me")
        assert resp.status_code == 401

    def test_me_with_valid_token(self, client, db_session, auth_headers):
        """GET /me with valid JWT returns user data."""
        headers = auth_headers("me@plmediaagency.com", "admin")
        resp = client.get("/api/auth/me", headers=headers)
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["email"] == "me@plmediaagency.com"
        assert data["role"] == "admin"


class TestLogoutRoute:
    """Tests for POST /api/auth/logout."""

    def test_logout_returns_200(self, client, db_session):
        """POST /logout always returns success message."""
        resp = client.post("/api/auth/logout")
        assert resp.status_code == 200
        assert resp.get_json()["message"] == "logged out"
