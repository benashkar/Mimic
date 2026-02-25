"""
Flask application factory.

Creates and configures the Flask app with:
  - SQLAlchemy database connection
  - CORS for frontend communication
  - Route registration
  - Health check endpoint
  - Structured logging with [OK]/[ERR] markers (no Unicode)
"""
import logging
import sys

from flask import Flask, jsonify
from flask_cors import CORS

from config import Config
from models import db
from routes import register_routes


def create_app(config_class=Config):
    """
    Create and configure the Flask application.

    Args:
        config_class: Configuration class to use (default: Config).
                      Pass TestConfig for testing with SQLite in-memory.

    Returns:
        Configured Flask app instance.
    """
    app = Flask(__name__)
    app.config.from_object(config_class)

    # Set up logging — [OK]/[ERR] markers, no Unicode symbols
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter(
        "[%(asctime)s] [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    ))
    app.logger.handlers = [handler]
    app.logger.setLevel(logging.INFO)

    # Initialize extensions
    db.init_app(app)
    CORS(app, origins=[app.config["FRONTEND_URL"]])

    # Register routes (blueprints added in later phases)
    register_routes(app)

    # Health check endpoint — confirms API is running
    @app.route("/api/health")
    def health():
        """Return service health status."""
        app.logger.info("[OK] Health check passed")
        return jsonify({"status": "ok", "service": "mimic-api"})

    app.logger.info("[OK] Mimic API initialized")
    return app
