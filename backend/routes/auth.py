"""
Auth routes — login, me, logout.

POST /api/auth/login  — exchange Google ID token for JWT
GET  /api/auth/me     — return current user info
POST /api/auth/logout — placeholder (frontend clears localStorage)
"""
import logging

from flask import Blueprint, request, jsonify, g

from services.auth_service import (
    verify_google_token,
    get_or_create_user,
    generate_jwt,
)
from decorators.login_required import login_required

logger = logging.getLogger(__name__)

auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/login", methods=["POST"])
def login():
    """Exchange a Google ID token for a JWT session token."""
    body = request.get_json(silent=True) or {}
    id_token_str = body.get("token") or ""

    if not id_token_str:
        return jsonify({"error": "Missing token"}), 400

    try:
        claims = verify_google_token(id_token_str)
    except ValueError as exc:
        logger.error("[ERR] Google token verification failed: %s", exc)
        return jsonify({"error": "Invalid Google token"}), 401

    try:
        user = get_or_create_user(claims)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 403

    token = generate_jwt(user)
    return jsonify({"token": token, "user": user.to_dict()})


@auth_bp.route("/me", methods=["GET"])
@login_required
def me():
    """Return the currently authenticated user."""
    return jsonify(g.current_user.to_dict())


@auth_bp.route("/logout", methods=["POST"])
def logout():
    """Logout placeholder — frontend clears localStorage."""
    return jsonify({"message": "logged out"})
