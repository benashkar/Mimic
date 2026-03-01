"""
Queue routes — Shared review queue for scheduled source list results.

GET    /api/queue          — List pending items (permission-filtered)
POST   /api/queue/claim    — Mark items as claimed by current user
POST   /api/queue/discard  — Mark items as discarded
POST   /api/queue/execute  — Run pipeline on a queue item (background thread)
GET    /api/queue/stats    — Counts by status for dashboard
"""
import logging
import threading
from datetime import datetime, timezone

from flask import Blueprint, request, jsonify, g, current_app

from models import db
from models.queue_item import QueueItem
from models.prompt import Prompt
from models.story import Story
from models.pipeline_run import PipelineRun
from models.user_agency import UserAgency
from decorators.login_required import login_required
from services.pipeline_service import run_pipeline

logger = logging.getLogger(__name__)

queue_bp = Blueprint("queue", __name__)


def _filter_queue_items_by_permissions(items, user):
    """Filter queue items by user's agency/opportunity permissions.

    Admin users see all items. Non-admin users only see items matching
    their UserAgency assignments (same logic as prompts filtering).
    """
    if user.role == "admin":
        return items

    user_agencies = UserAgency.query.filter_by(user_id=user.id).all()
    if not user_agencies:
        return []

    allowed = []
    for item in items:
        for ua in user_agencies:
            agency_match = (
                (item.agency or "").lower() == (ua.agency or "").lower()
            )
            if not agency_match:
                continue

            # NULL opportunity on assignment = wildcard (all opportunities)
            if not ua.opportunity:
                allowed.append(item)
                break

            # Specific opportunity must match
            if (item.opportunity or "").lower() == ua.opportunity.lower():
                allowed.append(item)
                break

    return allowed


@queue_bp.route("", methods=["GET"])
@login_required
def list_queue():
    """
    List queue items filtered by status and user permissions.

    Query params:
      - status: filter by status (default: 'pending')
    """
    status = request.args.get("status", "pending")

    items = QueueItem.query.filter_by(status=status).order_by(
        QueueItem.created_at.desc()
    ).all()

    # Permission filtering for non-admin users
    items = _filter_queue_items_by_permissions(items, g.current_user)

    return jsonify([item.to_dict() for item in items])


@queue_bp.route("/claim", methods=["POST"])
@login_required
def claim_items():
    """
    Mark queue items as claimed by the current user.

    Body: { "item_ids": [int, ...] }
    """
    body = request.get_json(silent=True) or {}
    item_ids = body.get("item_ids") or []

    if not item_ids:
        return jsonify({"error": "item_ids is required"}), 400

    now = datetime.now(timezone.utc)
    claimed = []
    for item_id in item_ids:
        item = db.session.get(QueueItem, item_id)
        if not item:
            continue
        if item.status != "pending":
            continue
        item.status = "claimed"
        item.claimed_by = g.current_user.email
        item.claimed_at = now
        claimed.append(item.id)

    db.session.commit()
    logger.info("[OK] Claimed %d queue items by %s", len(claimed), g.current_user.email)
    return jsonify({"claimed": claimed})


@queue_bp.route("/discard", methods=["POST"])
@login_required
def discard_items():
    """
    Mark queue items as discarded.

    Body: { "item_ids": [int, ...] }
    """
    body = request.get_json(silent=True) or {}
    item_ids = body.get("item_ids") or []

    if not item_ids:
        return jsonify({"error": "item_ids is required"}), 400

    discarded = []
    for item_id in item_ids:
        item = db.session.get(QueueItem, item_id)
        if not item:
            continue
        if item.status not in ("pending", "claimed"):
            continue
        item.status = "discarded"
        discarded.append(item.id)

    db.session.commit()
    logger.info("[OK] Discarded %d queue items", len(discarded))
    return jsonify({"discarded": discarded})


def _run_queue_pipeline_background(app, item_id, story_id, selected_story, refinement_prompt_id, user_email):
    """Run pipeline for a queue item in a background thread."""
    with app.app_context():
        try:
            run_pipeline(
                story_id=story_id,
                selected_story=selected_story,
                refinement_prompt_id=refinement_prompt_id,
                user_email=user_email,
            )
            item = db.session.get(QueueItem, item_id)
            if item:
                item.status = "completed"
                item.refinement_prompt_id = refinement_prompt_id
                item.pipeline_story_id = story_id
                db.session.commit()
            logger.info("[OK] Queue item %d pipeline completed (story=%d)", item_id, story_id)
        except Exception as exc:
            logger.error("[ERR] Queue item %d pipeline failed: %s", item_id, exc)
            try:
                item = db.session.get(QueueItem, item_id)
                if item:
                    item.status = "failed"
                db.session.commit()
            except Exception:
                db.session.rollback()


@queue_bp.route("/execute", methods=["POST"])
@login_required
def execute_item():
    """
    Run pipeline on a queue item (async, same pattern as /api/pipeline/run).

    Body: { "item_id": int, "refinement_prompt_id": int }
    Returns 202 with { item_id, story_id, status: "running" }
    """
    body = request.get_json(silent=True) or {}
    item_id = body.get("item_id")
    refinement_prompt_id = body.get("refinement_prompt_id")

    if not item_id or not refinement_prompt_id:
        return jsonify({"error": "item_id and refinement_prompt_id are required"}), 400

    item = db.session.get(QueueItem, item_id)
    if not item:
        return jsonify({"error": "Queue item not found"}), 404

    if item.status not in ("pending", "claimed"):
        return jsonify({"error": f"Cannot execute item with status '{item.status}'"}), 400

    # Use the item's parent story_id and body as selected_story
    selected_story = item.body[:2000]
    story_id = item.story_id

    # Mark as claimed
    item.status = "claimed"
    item.claimed_by = g.current_user.email
    item.claimed_at = datetime.now(timezone.utc)

    # Create placeholder "running" refinement run for status tracking
    placeholder_run = PipelineRun(
        story_id=story_id,
        prompt_id=refinement_prompt_id,
        step_type="refinement",
        status="running",
        input_text="(pipeline starting...)",
    )
    db.session.add(placeholder_run)
    db.session.commit()

    # Launch background thread
    app = current_app._get_current_object()
    thread = threading.Thread(
        target=_run_queue_pipeline_background,
        args=(app, item.id, story_id, selected_story, refinement_prompt_id, g.current_user.email),
    )
    thread.start()

    return jsonify({
        "item_id": item.id,
        "story_id": story_id,
        "status": "running",
    }), 202


@queue_bp.route("/stats", methods=["GET"])
@login_required
def queue_stats():
    """
    Get queue item counts by status for dashboard display.

    Returns: { pending, claimed, completed, failed, discarded, total }
    """
    counts = {}
    for status in ("pending", "claimed", "completed", "failed", "discarded"):
        counts[status] = QueueItem.query.filter_by(status=status).count()
    counts["total"] = sum(counts.values())

    return jsonify(counts)
