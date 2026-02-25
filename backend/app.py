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
        _patch_amy_bot_prompt(app)

    app.logger.info("[OK] Mimic API initialized")
    return app


def _patch_amy_bot_prompt(app):
    """Apply accumulated Amy Bot prompt patches."""
    from models.prompt import Prompt
    try:
        prompt = Prompt.query.filter_by(prompt_type="amy-bot", is_active=True).first()
    except Exception:
        return  # Table doesn't exist yet (test env before create_all)
    if not prompt:
        return

    changed = False
    text = prompt.prompt_text

    # Patch: make headlines non-rejectable
    old_headlines = (
        "2. HEADLINES\n"
        "HL-VAGUE: The headline must tell you what happened.\n"
        "HL-MISQUOTE: Do not put someone else's words in a headline attributed to another person.\n"
        "HL-WRONGFOCUS: Lead with the news, not the amplifier.\n"
        "HL-IDENTITY: People need real names and titles. Never use a social media handle as a name."
    )
    new_headlines = (
        "2. HEADLINES (advisory only — never reject for headline issues)\n"
        "Headlines are NOT grounds for rejection. Note suggestions if helpful, but always APPROVE regardless of headline quality."
    )
    if old_headlines in text:
        text = text.replace(old_headlines, new_headlines)
        changed = True

    # Patch: make ledes non-rejectable
    old_ledes = (
        "3. LEDES\n"
        "LD-CONTEXT: Ledes need who, what, when, where, and why.\n"
        "LD-EDITORIAL: Keep it neutral. Opinions must be attributed.\n"
        "LD-ANNOUNCE: For Provided Announcements, say \"announced.\"\n"
        "LD-VAGUE: Do not use vague references."
    )
    new_ledes = (
        "3. LEDES (advisory only — never reject for lede issues)\n"
        "Ledes are NOT grounds for rejection. Note suggestions if helpful, but always APPROVE regardless of lede quality."
    )
    if old_ledes in text:
        text = text.replace(old_ledes, new_ledes)
        changed = True

    if changed:
        prompt.prompt_text = text
        db.session.commit()
        app.logger.info("[OK] Patched Amy Bot prompt: headlines/ledes now non-rejectable")
