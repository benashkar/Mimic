"""
Admin routes — user management and agency assignments.

GET    /api/admin/users              — list all users with agency assignments
GET    /api/admin/users/:id          — get single user with assignments
PUT    /api/admin/users/:id/agencies — set a user's agency/opportunity access
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
