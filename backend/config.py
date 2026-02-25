"""
Flask configuration classes.

Config reads from environment variables with sensible defaults.
TestConfig overrides for pytest with SQLite in-memory.

The postgres:// → postgresql:// fix handles Render's connection string
format, which uses the older 'postgres://' prefix that SQLAlchemy 1.4+
no longer accepts.
"""
import os


class Config:
    """Base configuration for Flask app."""

    # Flask core
    SECRET_KEY = os.environ.get("SECRET_KEY") or "dev-secret-key-change-me"

    # Database — Render uses postgres:// but SQLAlchemy needs postgresql://
    _raw_db_url = os.environ.get("DATABASE_URL") or "sqlite:///mimic_dev.db"
    SQLALCHEMY_DATABASE_URI = _raw_db_url.replace(
        "postgres://", "postgresql://", 1
    )

    # SQLAlchemy pool settings for production PostgreSQL
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_pre_ping": True,  # Verify connections before use
        "pool_recycle": 300,    # Recycle connections every 5 minutes
    }

    # xAI Grok API
    GROK_API_KEY = os.environ.get("GROK_API_KEY") or ""
    GROK_API_URL = os.environ.get("GROK_API_URL") or "https://api.x.ai/v1/chat/completions"
    GROK_MODEL = os.environ.get("GROK_MODEL") or "grok-3"
    GROK_TIMEOUT_SECONDS = int(os.environ.get("GROK_TIMEOUT_SECONDS") or "60")

    # Google OAuth
    GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID") or ""

    # JWT settings
    JWT_EXPIRY_HOURS = int(os.environ.get("JWT_EXPIRY_HOURS") or "24")

    # CORS — frontend URL for allowed origins
    FRONTEND_URL = os.environ.get("FRONTEND_URL") or "http://localhost:5173"


class TestConfig(Config):
    """Test configuration — SQLite in-memory, no external dependencies."""

    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    SQLALCHEMY_ENGINE_OPTIONS = {}  # No pool settings needed for SQLite
    GOOGLE_CLIENT_ID = "test-client-id"
    GROK_API_KEY = "test-grok-key"
    GROK_API_URL = "https://api.x.ai/v1/chat/completions"
    GROK_TIMEOUT_SECONDS = 5
