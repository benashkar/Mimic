"""
Story routes — browse pipeline results.

GET /api/stories              — list stories (filter by decision, opportunity, state)
GET /api/stories/:id          — get single story with all pipeline data
GET /api/stories/stats        — dashboard statistics
POST /api/stories/source-stats — per-source PAPA/PSST/rejection counts
"""
import logging

from flask import Blueprint, request, jsonify

from models import db
from models.story import Story
from models.prompt import Prompt
from decorators.login_required import login_required

logger = logging.getLogger(__name__)

stories_bp = Blueprint("stories", __name__)


@stories_bp.route("", methods=["GET"])
@login_required
def list_stories():
    """
    List stories with optional filters.

    Query params:
      - decision: filter by validation_decision (APPROVE, REJECT)
      - opportunity: filter by opportunity
      - state: filter by state
      - page: page number (default 1)
      - per_page: items per page (default 20)
    """
    query = Story.query

    decision = request.args.get("decision")
    if decision:
        query = query.filter(Story.validation_decision == decision.upper())

    opportunity = request.args.get("opportunity")
    if opportunity:
        query = query.filter(Story.opportunity.ilike(f"%{opportunity}%"))

    state = request.args.get("state")
    if state:
        query = query.filter(Story.state.ilike(f"%{state}%"))

    page = int(request.args.get("page") or "1")
    per_page = int(request.args.get("per_page") or "20")

    pagination = query.order_by(Story.created_at.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )

    return jsonify({
        "stories": [s.to_dict() for s in pagination.items],
        "total": pagination.total,
        "page": pagination.page,
        "pages": pagination.pages,
    })


@stories_bp.route("/stats", methods=["GET"])
@login_required
def story_stats():
    """
    Dashboard statistics — approval rate, counts, per opportunity.

    Returns: { total, approved, rejected, pending, approval_rate,
               by_opportunity: [{name, total, approved}] }
    """
    total = Story.query.count()
    approved = Story.query.filter_by(validation_decision="APPROVE").count()
    rejected = Story.query.filter_by(validation_decision="REJECT").count()
    pending = total - approved - rejected

    approval_rate = round((approved / total * 100), 1) if total > 0 else 0

    # Per-opportunity breakdown
    opportunities = db.session.query(
        Story.opportunity,
        db.func.count(Story.id).label("total"),
        db.func.sum(db.case((Story.validation_decision == "APPROVE", 1), else_=0)).label("approved"),
    ).group_by(Story.opportunity).all()

    by_opportunity = [
        {"name": opp or "Unknown", "total": t, "approved": a}
        for opp, t, a in opportunities
    ]

    return jsonify({
        "total": total,
        "approved": approved,
        "rejected": rejected,
        "pending": pending,
        "approval_rate": approval_rate,
        "by_opportunity": by_opportunity,
    })


@stories_bp.route("/source-stats", methods=["POST"])
@login_required
def get_source_stats():
    """
    Per-source history — how many times each source text has been run
    through PAPA vs PSST and how many times it was rejected.

    Body: { "sources": ["source text 1", "source text 2", ...] }
    Returns: { "stats": { "0": { "papa": 1, "psst": 0, "rejected": 0 }, ... } }
    Keys are string indices matching the input array.
    """
    body = request.get_json(silent=True) or {}
    sources = body.get("sources", [])
    if not sources:
        return jsonify({"stats": {}})

    # Truncate to 2000 chars — same as pipeline does on selected_story
    truncated = [s[:2000] for s in sources]
    unique_texts = list(set(truncated))

    # Single query: all matching stories joined with their refinement prompt
    rows = db.session.query(
        Story.selected_story,
        Prompt.name,
        Story.validation_decision,
    ).join(
        Prompt, Story.refinement_prompt_id == Prompt.id
    ).filter(
        Story.selected_story.in_(unique_texts)
    ).all()

    # Aggregate per source text
    text_stats = {}
    for selected_story, prompt_name, decision in rows:
        if selected_story not in text_stats:
            text_stats[selected_story] = {"papa": 0, "psst": 0, "rejected": 0}
        s = text_stats[selected_story]
        if "papa" in prompt_name.lower():
            s["papa"] += 1
        else:
            s["psst"] += 1
        if decision and decision.lower() != "approve":
            s["rejected"] += 1

    # Map back to input indices
    stats = {}
    for i, t in enumerate(truncated):
        if t in text_stats:
            stats[str(i)] = text_stats[t]

    return jsonify({"stats": stats})


@stories_bp.route("/<int:story_id>", methods=["GET"])
@login_required
def get_story(story_id):
    """Get a single story with all pipeline data."""
    story = db.session.get(Story, story_id)
    if not story:
        return jsonify({"error": "Story not found"}), 404

    result = story.to_dict()
    result["pipeline_runs"] = [r.to_dict() for r in story.pipeline_runs]
    return jsonify(result)
