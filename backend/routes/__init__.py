"""
Route registration for the Flask app.

Registers all route blueprints:
  - auth routes (Google OAuth login/logout/me)
  - prompt routes (CRUD for Prompt Library — Phase 3)
  - pipeline routes (Source List runner — Phase 4)
  - story routes (browse pipeline results — Phase 6)
  - admin routes (user management, agency assignments)
"""
from routes.auth import auth_bp
from routes.prompts import prompts_bp
from routes.pipeline import pipeline_bp
from routes.stories import stories_bp
from routes.admin import admin_bp


def register_routes(app):
    """
    Register all route blueprints with the Flask app.

    Args:
        app: Flask application instance.
    """
    app.register_blueprint(auth_bp, url_prefix="/api/auth")
    app.register_blueprint(prompts_bp, url_prefix="/api/prompts")
    app.register_blueprint(pipeline_bp, url_prefix="/api/pipeline")
    app.register_blueprint(stories_bp, url_prefix="/api/stories")
    app.register_blueprint(admin_bp, url_prefix="/api/admin")
