"""
Shared pytest fixtures for Mimic tests.

Uses TestConfig (SQLite in-memory) so tests run without PostgreSQL.
Session-scoped app fixture creates tables once.
Per-test db_session rolls back after each test for isolation.
"""
import sys
import os
import pytest

# Add backend to Python path so imports work
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from app import create_app  # noqa: E402
from config import TestConfig  # noqa: E402
from models import db as _db  # noqa: E402


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
