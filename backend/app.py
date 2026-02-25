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

    # One-time prompt patches (safe to re-run, no-ops if already applied)
    with app.app_context():
        _patch_amy_bot_twitter_exception(app)

    app.logger.info("[OK] Mimic API initialized")
    return app


def _patch_amy_bot_twitter_exception(app):
    """Strengthen X/Twitter quote exception in Amy Bot prompt."""
    from models.prompt import Prompt
    old_fragment = "Do NOT flag Q-UNVERIFIED for X/Twitter sources."
    new_exception = (
        "EXCEPTION — X/Twitter posts: If the source material is identified as coming from "
        "X (x.com) or Twitter (twitter.com), the post content IS the verified direct quote "
        "from the account holder. This applies unconditionally — even if the URL is a "
        "placeholder, broken, or unresolvable. If the pitch identifies the source as a tweet "
        "or X post, the quotes are verified. Do NOT flag Q-UNVERIFIED for any X/Twitter-sourced content."
    )
    prompt = Prompt.query.filter_by(prompt_type="amy-bot", is_active=True).first()
    if not prompt:
        return
    if "This applies unconditionally" in prompt.prompt_text:
        return  # Already patched
    if old_fragment in prompt.prompt_text:
        # Replace the old exception block
        old_block = (
            "EXCEPTION — X/Twitter posts: If the source is an X (x.com) or Twitter "
            "(twitter.com) post, the text of that post IS the verified quote from the "
            "account holder. Treat the post content as a direct, verified quote from that "
            "person. Do NOT flag Q-UNVERIFIED for X/Twitter sources."
        )
        prompt.prompt_text = prompt.prompt_text.replace(old_block, new_exception)
        db.session.commit()
        app.logger.info("[OK] Patched Amy Bot prompt: strengthened X/Twitter exception")
