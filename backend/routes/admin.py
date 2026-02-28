"""
Admin routes — user management and agency assignments.

GET    /api/admin/users              — list all users with agency assignments
GET    /api/admin/users/:id          — get single user with assignments
PUT    /api/admin/users/:id/role     — change a user's role (admin/user)
PUT    /api/admin/users/:id/agencies — set a user's agency/opportunity access
POST   /api/admin/users/invite       — pre-invite a user by email
GET    /api/admin/agencies           — list distinct agencies from prompts

All endpoints require @admin_required.
"""
import logging

from flask import Blueprint, request, jsonify

from models import db
from models.user import User
from models.prompt import Prompt
from models.user_agency import UserAgency
from decorators.admin_required import admin_required

logger = logging.getLogger(__name__)

admin_bp = Blueprint("admin", __name__)


@admin_bp.route("/users", methods=["GET"])
@admin_required
def list_users():
    """List all users with their agency assignments."""
    users = User.query.order_by(User.created_at.desc()).all()
    result = []
    for u in users:
        user_dict = u.to_dict()
        user_dict["agencies"] = [ua.to_dict() for ua in u.agencies]
        result.append(user_dict)
    return jsonify(result)


@admin_bp.route("/users/<int:user_id>", methods=["GET"])
@admin_required
def get_user(user_id):
    """Get a single user with agency assignments."""
    user = db.session.get(User, user_id)
    if not user:
        return jsonify({"error": "User not found"}), 404
    user_dict = user.to_dict()
    user_dict["agencies"] = [ua.to_dict() for ua in user.agencies]
    return jsonify(user_dict)


@admin_bp.route("/users/invite", methods=["POST"])
@admin_required
def invite_user():
    """
    Pre-invite a user by email before they log in.

    Body: { "email": "...", "role": "user"|"admin" }

    Creates a User record with no google_id. When the user later logs in
    via Google OAuth, their pre-assigned role and agencies are preserved.
    """
    body = request.get_json(silent=True) or {}
    email = (body.get("email") or "").strip().lower()
    role = (body.get("role") or "").strip().lower()

    if not email or "@" not in email:
        return jsonify({"error": "Valid email is required"}), 400
    if role not in ("admin", "user"):
        return jsonify({"error": "Role must be 'admin' or 'user'"}), 400

    existing = User.query.filter(
        db.func.lower(User.email) == email.lower()
    ).first()
    if existing:
        return jsonify({"error": "Email already registered"}), 409

    user = User(email=email, role=role)
    db.session.add(user)
    db.session.commit()

    logger.info("[OK] Pre-invited user %s with role=%s", email, role)

    user_dict = user.to_dict()
    user_dict["agencies"] = []
    return jsonify(user_dict), 201


@admin_bp.route("/users/<int:user_id>/role", methods=["PUT"])
@admin_required
def set_user_role(user_id):
    """
    Change a user's role.

    Body: { "role": "admin"|"user" }
    """
    user = db.session.get(User, user_id)
    if not user:
        return jsonify({"error": "User not found"}), 404

    body = request.get_json(silent=True) or {}
    role = (body.get("role") or "").strip().lower()

    if role not in ("admin", "user"):
        return jsonify({"error": "Role must be 'admin' or 'user'"}), 400

    user.role = role
    db.session.commit()

    logger.info("[OK] Updated role for user %s (id=%d) to %s", user.email, user_id, role)

    user_dict = user.to_dict()
    user_dict["agencies"] = [ua.to_dict() for ua in user.agencies]
    return jsonify(user_dict)


@admin_bp.route("/users/<int:user_id>/agencies", methods=["PUT"])
@admin_required
def set_user_agencies(user_id):
    """
    Replace a user's agency assignments.

    Body: { "agencies": [ { "agency": "...", "opportunity": "..." or null }, ... ] }

    Replaces all existing assignments for this user.
    """
    user = db.session.get(User, user_id)
    if not user:
        return jsonify({"error": "User not found"}), 404

    body = request.get_json(silent=True) or {}
    agencies_data = body.get("agencies")
    if agencies_data is None:
        return jsonify({"error": "agencies array is required"}), 400

    # Delete existing assignments
    UserAgency.query.filter_by(user_id=user_id).delete()

    # Create new assignments
    for entry in agencies_data:
        agency_name = (entry.get("agency") or "").strip()
        if not agency_name:
            continue
        opportunity = (entry.get("opportunity") or "").strip() or None
        ua = UserAgency(
            user_id=user_id,
            agency=agency_name,
            opportunity=opportunity,
        )
        db.session.add(ua)

    db.session.commit()

    logger.info(
        "[OK] Updated agencies for user %s (id=%d): %d assignments",
        user.email, user_id, len(agencies_data),
    )

    # Return updated user with assignments
    user_dict = user.to_dict()
    user_dict["agencies"] = [ua.to_dict() for ua in user.agencies]
    return jsonify(user_dict)


@admin_bp.route("/agencies", methods=["GET"])
@admin_required
def list_agencies():
    """List distinct agency values from existing prompts."""
    rows = (
        db.session.query(Prompt.agency)
        .filter(Prompt.agency.isnot(None), Prompt.agency != "")
        .distinct()
        .order_by(Prompt.agency)
        .all()
    )
    agencies = [r[0] for r in rows]
    return jsonify(agencies)
