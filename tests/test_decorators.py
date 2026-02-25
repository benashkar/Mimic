"""
Tests for decorators/login_required.py and decorators/admin_required.py.

Covers: missing token, bad token, valid token, admin enforcement.
"""
from flask import jsonify

from app import create_app
from config import TestConfig
from models import db as _db
from models.user import User
from services.auth_service import generate_jwt


class TestLoginRequired:
    """Tests for @login_required decorator."""

    def test_no_token_returns_401(self, client, db_session):
        """Request without Authorization header returns 401."""
        resp = client.get("/api/auth/me")
        assert resp.status_code == 401

    def test_bad_token_returns_401(self, client, db_session):
        """Request with garbage token returns 401."""
        resp = client.get(
            "/api/auth/me",
            headers={"Authorization": "Bearer garbage-token"},
        )
        assert resp.status_code == 401

    def test_valid_token_returns_200(self, client, db_session, auth_headers):
        """Request with valid JWT returns 200 and user data."""
        headers = auth_headers("valid@plmediaagency.com", "user")
        resp = client.get("/api/auth/me", headers=headers)
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["email"] == "valid@plmediaagency.com"


class TestAdminRequired:
    """Tests for @admin_required decorator."""

    def test_user_role_on_admin_route_returns_403(self):
        """Non-admin user gets 403 on admin-only endpoint."""
        from decorators.admin_required import admin_required

        # Create a fresh app so we can register a test route before any requests
        app = create_app(config_class=TestConfig)

        @app.route("/api/test-admin-only")
        @admin_required
        def _test_admin():
            return jsonify({"ok": True})

        with app.app_context():
            _db.create_all()
            user = User(
                google_id="gid-admin-test",
                email="nonadmin@plmediaagency.com",
                display_name="Regular User",
                role="user",
            )
            _db.session.add(user)
            _db.session.commit()

            token = generate_jwt(user)
            client = app.test_client()
            resp = client.get(
                "/api/test-admin-only",
                headers={"Authorization": f"Bearer {token}"},
            )
            assert resp.status_code == 403

            # Cleanup
            _db.session.rollback()
