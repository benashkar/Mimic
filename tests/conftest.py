"""
Shared pytest fixtures for Mimic tests.

Uses TestConfig (SQLite in-memory) so tests run without PostgreSQL.
Session-scoped app fixture creates tables once.
Per-test db_session rolls back after each test for isolation.
"""
import sys
import os
from unittest.mock import patch

import pytest

# Add backend to Python path so imports work
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from app import create_app  # noqa: E402
from config import TestConfig  # noqa: E402
from models import db as _db  # noqa: E402
from models.user import User  # noqa: E402
from services.auth_service import generate_jwt  # noqa: E402


@pytest.fixture(scope="session")
def app():
    """Create Flask app with TestConfig (SQLite in-memory) once per session."""
    app = create_app(config_class=TestConfig)
    with app.app_context():
        _db.create_all()
    yield app


@pytest.fixture(scope="function")
def client(app):
    """Flask test client for making HTTP requests."""
    return app.test_client()


@pytest.fixture(scope="function")
def db_session(app):
    """
    Per-test database session with rollback.

    Uses a savepoint (nested transaction) so each test's data is
    rolled back without affecting the session-scoped table creation.
    Compatible with Flask-SQLAlchemy 3.x.
    """
    with app.app_context():
        # Begin a nested transaction (savepoint)
        _db.session.begin_nested()

        yield _db.session

        # Rollback the savepoint after each test
        _db.session.rollback()


@pytest.fixture()
def make_user(db_session):
    """Factory fixture to create a User in the test database."""
    def _make_user(email="test@plmediaagency.com", role="user",
                   google_id="google-123", display_name="Test User"):
        user = User(
            google_id=google_id,
            email=email,
            display_name=display_name,
            role=role,
        )
        db_session.add(user)
        db_session.flush()
        return user
    return _make_user


@pytest.fixture()
def auth_headers(app, make_user):
    """
    Create a user and return Authorization headers with a valid JWT.

    Usage: headers = auth_headers("email@plmediaagency.com", "admin")
    """
    def _auth_headers(email="test@plmediaagency.com", role="user"):
        user = make_user(email=email, role=role, google_id=f"gid-{email}")
        with app.app_context():
            token = generate_jwt(user)
        return {"Authorization": f"Bearer {token}"}
    return _auth_headers


@pytest.fixture()
def mock_verify_google_token():
    """Patch google.oauth2.id_token.verify_oauth2_token to return test claims."""
    with patch("services.auth_service.id_token.verify_oauth2_token") as mock:
        mock.return_value = {
            "sub": "google-test-sub-123",
            "email": "testuser@plmediaagency.com",
            "name": "Test User",
            "picture": "https://example.com/photo.jpg",
        }
        yield mock
