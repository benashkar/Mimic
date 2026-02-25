"""
Route registration for the Flask app.

Registers all route blueprints:
  - auth routes (Google OAuth login/logout/me)
  - prompt routes (CRUD for Prompt Library — Phase 3)
  - pipeline routes (Source List runner — Phase 4)
  - story routes (browse pipeline results — Phase 6)
"""
from routes.auth import auth_bp


def register_routes(app):
    """
    Register all route blueprints with the Flask app.

    Args:
        app: Flask application instance.
    """
    app.register_blueprint(auth_bp, url_prefix="/api/auth")
