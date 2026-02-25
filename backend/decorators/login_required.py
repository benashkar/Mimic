"""
Decorator: @login_required — enforces JWT authentication.

Extracts Bearer token from Authorization header, decodes JWT,
looks up the User, and sets g.current_user. Returns 401 on failure.
"""
from functools import wraps

from flask import request, g, jsonify

from models import db
from services.auth_service import decode_jwt
from models.user import User


def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        auth_header = request.headers.get("Authorization") or ""
        if not auth_header.startswith("Bearer "):
            return jsonify({"error": "Missing or invalid token"}), 401

        token = auth_header.split("Bearer ", 1)[1]
        claims = decode_jwt(token)
        if claims is None:
            return jsonify({"error": "Invalid or expired token"}), 401

        user = db.session.get(User, claims.get("user_id"))
        if user is None:
            return jsonify({"error": "User not found"}), 401

        g.current_user = user
        return f(*args, **kwargs)

    return decorated
