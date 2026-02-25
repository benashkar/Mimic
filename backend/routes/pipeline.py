"""
Pipeline routes — Source List runner and full pipeline execution.

POST /api/pipeline/source-list  — run a Source List prompt through Grok
POST /api/pipeline/run          — run full pipeline: refinement → Amy Bot → CMS/kill
"""
import logging
from datetime import datetime, timezone

from flask import Blueprint, request, jsonify, g

from models import db
from models.prompt import Prompt
from models.story import Story
from models.pipeline_run import PipelineRun
from decorators.login_required import login_required
from services.grok_service import call_grok, GrokAPIError
from services.pipeline_service import run_pipeline
import time

logger = logging.getLogger(__name__)

pipeline_bp = Blueprint("pipeline", __name__)


@pipeline_bp.route("/source-list", methods=["POST"])
@login_required
def run_source_list():
    """
    Run a Source List prompt through the Grok API.

    Body: { "prompt_id": int }
    Returns: { story_id, source_list_output, routing metadata }

    Creates a Story record and a PipelineRun audit row.
    """
    body = request.get_json(silent=True) or {}
    prompt_id = body.get("prompt_id")

    if not prompt_id:
        return jsonify({"error": "prompt_id is required"}), 400

    prompt = db.session.get(Prompt, prompt_id)
    if not prompt:
        return jsonify({"error": "Prompt not found"}), 404

    if prompt.prompt_type != "source-list":
        return jsonify({"error": "Prompt is not a source-list type"}), 400

    # Build context from routing metadata
    context_parts = []
    if prompt.opportunity:
        context_parts.append(f"Opportunity: {prompt.opportunity}")
    if prompt.state:
        context_parts.append(f"State: {prompt.state}")
    if prompt.publications:
        context_parts.append(f"Publications: {prompt.publications}")
    if prompt.topic_summary:
        context_parts.append(f"Topic: {prompt.topic_summary}")
    if prompt.context:
        context_parts.append(f"Context: {prompt.context}")
    context_str = "\n".join(context_parts)

    # Create Story record with routing snapshot
    story = Story(
        source_list_prompt_id=prompt.id,
        source_list_input=prompt.prompt_text,
        opportunity=prompt.opportunity,
        state=prompt.state,
        publications=prompt.publications,
        topic_summary=prompt.topic_summary,
        context=prompt.context,
        created_by=g.current_user.email,
    )
    db.session.add(story)
    db.session.flush()

    # Create PipelineRun audit record
    run = PipelineRun(
        story_id=story.id,
        prompt_id=prompt.id,
        step_type="source-list",
        status="running",
        input_text=prompt.prompt_text,
    )
    db.session.add(run)
    db.session.flush()

    # Call Grok API
    start_ms = int(time.time() * 1000)
    try:
        output = call_grok(prompt.prompt_text, context=context_str)
        duration_ms = int(time.time() * 1000) - start_ms

        story.source_list_output = output
        run.output_text = output
        run.status = "completed"
        run.duration_ms = duration_ms
        run.completed_at = datetime.now(timezone.utc)

        db.session.commit()
        logger.info("[OK] Source List run completed (story_id=%d)", story.id)

        return jsonify({
            "story_id": story.id,
            "source_list_output": output,
            "opportunity": story.opportunity,
            "state": story.state,
            "publications": story.publications,
        })

    except GrokAPIError as exc:
        duration_ms = int(time.time() * 1000) - start_ms
        run.status = "failed"
        run.error_message = str(exc)
        run.duration_ms = duration_ms
        run.completed_at = datetime.now(timezone.utc)
        db.session.commit()

        logger.error("[ERR] Source List run failed: %s", exc)
        status_code = exc.status_code or 502
        return jsonify({"error": str(exc)}), status_code


@pipeline_bp.route("/run", methods=["POST"])
@login_required
def run_full_pipeline():
    """
    Run the full pipeline: refinement (PAPA/PSST) → Amy Bot → CMS/kill.

    Body: {
        "story_id": int,
        "selected_story": str,
        "refinement_prompt_id": int
    }
    """
    body = request.get_json(silent=True) or {}
    story_id = body.get("story_id")
    selected_story = body.get("selected_story") or ""
    refinement_prompt_id = body.get("refinement_prompt_id")

    if not story_id or not selected_story or not refinement_prompt_id:
        return jsonify({"error": "story_id, selected_story, and refinement_prompt_id are required"}), 400

    try:
        result = run_pipeline(
            story_id=story_id,
            selected_story=selected_story,
            refinement_prompt_id=refinement_prompt_id,
            user_email=g.current_user.email,
        )
        return jsonify(result)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    except GrokAPIError as exc:
        status_code = exc.status_code or 502
        return jsonify({"error": str(exc)}), status_code
