"""
Prompt Library routes — CRUD for prompts.

GET    /api/prompts          — list prompts (filter by type, opportunity, state)
GET    /api/prompts/:id      — get single prompt
POST   /api/prompts          — create prompt (admin only)
PUT    /api/prompts/:id      — update prompt (admin only)
DELETE /api/prompts/:id      — soft-delete prompt (admin only)
"""
import logging

from flask import Blueprint, request, jsonify, g

from models import db
from models.prompt import Prompt
from models.user_agency import UserAgency
from decorators.login_required import login_required
from decorators.admin_required import admin_required

logger = logging.getLogger(__name__)

prompts_bp = Blueprint("prompts", __name__)


@prompts_bp.route("", methods=["GET"])
@login_required
def list_prompts():
    """
    List prompts with optional filters.

    Query params:
      - type: filter by prompt_type (source-list, papa, amy-bot)
      - opportunity: filter source-list prompts by opportunity
      - state: filter source-list prompts by state
      - agency: filter by agency
      - active: filter by is_active (default true)

    Permission filtering:
      - Admin users see all prompts.
      - Non-admin users only see source-list prompts matching their
        UserAgency assignments. PAPA/PSST and Amy Bot prompts are
        visible to all authenticated users (shared tools).
    """
    query = Prompt.query

    prompt_type = request.args.get("type")
    if prompt_type:
        query = query.filter(Prompt.prompt_type == prompt_type)

    opportunity = request.args.get("opportunity")
    if opportunity:
        query = query.filter(Prompt.opportunity.ilike(f"%{opportunity}%"))

    state = request.args.get("state")
    if state:
        query = query.filter(Prompt.state.ilike(f"%{state}%"))

    agency = request.args.get("agency")
    if agency:
        query = query.filter(Prompt.agency.ilike(f"%{agency}%"))

    # Default to active-only unless explicitly set to 'false'
    active = request.args.get("active", "true")
    if active.lower() != "false":
        query = query.filter(Prompt.is_active.is_(True))

    prompts = query.order_by(Prompt.created_at.desc()).all()

    # Permission filtering for non-admin users
    user = g.current_user
    if user.role != "admin":
        user_agencies = UserAgency.query.filter_by(user_id=user.id).all()
        prompts = _filter_by_permissions(prompts, user_agencies)

    return jsonify([p.to_dict() for p in prompts])


def _filter_by_permissions(prompts, user_agencies):
    """Filter prompts based on user's agency assignments.

    - PAPA/PSST and Amy Bot prompts are visible to all (shared tools).
    - Source-list prompts require matching agency (and optionally opportunity).
    - If a UserAgency has opportunity=NULL, it grants access to all
      opportunities under that agency.
    """
    if not user_agencies:
        # No assignments — only show non-source-list prompts
        return [p for p in prompts if p.prompt_type != "source-list"]

    allowed = []
    for p in prompts:
        if p.prompt_type != "source-list":
            allowed.append(p)
            continue

        # Check if any user_agency grants access to this prompt
        for ua in user_agencies:
            agency_match = (
                (p.agency or "").lower() == (ua.agency or "").lower()
            )
            if not agency_match:
                continue

            # NULL opportunity on assignment = wildcard (all opportunities)
            if not ua.opportunity:
                allowed.append(p)
                break

            # Specific opportunity must match
            if (p.opportunity or "").lower() == ua.opportunity.lower():
                allowed.append(p)
                break

    return allowed


@prompts_bp.route("/<int:prompt_id>", methods=["GET"])
@login_required
def get_prompt(prompt_id):
    """Get a single prompt by ID."""
    prompt = db.session.get(Prompt, prompt_id)
    if not prompt:
        return jsonify({"error": "Prompt not found"}), 404
    return jsonify(prompt.to_dict())


@prompts_bp.route("", methods=["POST"])
@admin_required
def create_prompt():
    """
    Create a new prompt (admin only).

    Body: { prompt_type, name, prompt_text, description?,
            issuer?, opportunity?, state?, publications?,
            topic_summary?, context?, pitches_per_week? }
    """
    body = request.get_json(silent=True) or {}

    # Required fields
    prompt_type = body.get("prompt_type") or ""
    name = body.get("name") or ""
    prompt_text = body.get("prompt_text") or ""

    if not prompt_type or not name or not prompt_text:
        return jsonify({"error": "prompt_type, name, and prompt_text are required"}), 400

    prompt = Prompt(
        prompt_type=prompt_type,
        name=name,
        prompt_text=prompt_text,
        description=body.get("description") or "",
        agency=body.get("agency") or "",
        is_active=True,
        created_by=g.current_user.email,
        updated_by=g.current_user.email,
    )

    # Source list routing metadata (only relevant for source-list type)
    if prompt_type == "source-list":
        prompt.issuer = body.get("issuer") or ""
        prompt.opportunity = body.get("opportunity") or ""
        prompt.state = body.get("state") or ""
        prompt.publications = body.get("publications") or ""
        prompt.topic_summary = body.get("topic_summary") or ""
        prompt.context = body.get("context") or ""
        prompt.pitches_per_week = body.get("pitches_per_week")

    db.session.add(prompt)
    db.session.commit()

    logger.info("[OK] Prompt created: %s (type=%s)", name, prompt_type)
    return jsonify(prompt.to_dict()), 201


@prompts_bp.route("/<int:prompt_id>", methods=["PUT"])
@admin_required
def update_prompt(prompt_id):
    """
    Update an existing prompt (admin only).

    Body: any fields to update.
    """
    prompt = db.session.get(Prompt, prompt_id)
    if not prompt:
        return jsonify({"error": "Prompt not found"}), 404

    body = request.get_json(silent=True) or {}

    # Update common fields if provided
    if "name" in body:
        prompt.name = body["name"]
    if "prompt_text" in body:
        prompt.prompt_text = body["prompt_text"]
    if "description" in body:
        prompt.description = body["description"]
    if "is_active" in body:
        prompt.is_active = body["is_active"]
    if "agency" in body:
        prompt.agency = body["agency"]

    # Update routing metadata for source-list prompts
    if prompt.prompt_type == "source-list":
        for field in ["issuer", "opportunity", "state", "publications",
                       "topic_summary", "context", "pitches_per_week"]:
            if field in body:
                setattr(prompt, field, body[field])

    prompt.updated_by = g.current_user.email
    db.session.commit()

    logger.info("[OK] Prompt updated: %s (id=%d)", prompt.name, prompt.id)
    return jsonify(prompt.to_dict())


@prompts_bp.route("/<int:prompt_id>", methods=["DELETE"])
@admin_required
def delete_prompt(prompt_id):
    """Soft-delete a prompt by setting is_active=False (admin only)."""
    prompt = db.session.get(Prompt, prompt_id)
    if not prompt:
        return jsonify({"error": "Prompt not found"}), 404

    prompt.is_active = False
    prompt.updated_by = g.current_user.email
    db.session.commit()

    logger.info("[OK] Prompt deactivated: %s (id=%d)", prompt.name, prompt.id)
    return jsonify({"message": f"Prompt '{prompt.name}' deactivated"})
