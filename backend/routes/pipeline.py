"""
Pipeline routes — Source List runner and full pipeline execution.

Uses background threads to avoid Render's 30-second proxy timeout.
POST returns immediately with a story_id, GET polls for the result.
"""
import logging
import threading
import time
from datetime import datetime, timezone

from flask import Blueprint, request, jsonify, g, current_app

from models import db
from models.prompt import Prompt
from models.story import Story
from models.pipeline_run import PipelineRun
from decorators.login_required import login_required
from services.grok_service import call_grok, GrokAPIError
from services.pipeline_service import run_pipeline
from services.url_enrichment_service import enrich_urls

logger = logging.getLogger(__name__)

pipeline_bp = Blueprint("pipeline", __name__)


def _run_source_list_background(app, story_id, prompt_text, context_str, prompt_id):
    """Run Grok API call in a background thread with its own app context."""
    with app.app_context():
        story = db.session.get(Story, story_id)
        run = PipelineRun.query.filter_by(story_id=story_id, step_type="source-list").first()

        start_ms = int(time.time() * 1000)
        try:
            output = call_grok(prompt_text, context=context_str)
            duration_ms = int(time.time() * 1000) - start_ms

            story.source_list_output = output

            # Enrich any URLs found in the output (best-effort)
            try:
                enrichments = enrich_urls(output)
                if enrichments:
                    story.url_enrichments = enrichments
            except Exception as enrich_exc:
                logger.warning("[--] URL enrichment failed: %s", enrich_exc)

            run.output_text = output
            run.status = "completed"
            run.duration_ms = duration_ms
            run.completed_at = datetime.now(timezone.utc)
            db.session.commit()
            logger.info("[OK] Source List run completed (story_id=%d)", story_id)

        except GrokAPIError as exc:
            duration_ms = int(time.time() * 1000) - start_ms
            run.status = "failed"
            run.error_message = str(exc)
            run.duration_ms = duration_ms
            run.completed_at = datetime.now(timezone.utc)
            db.session.commit()
            logger.error("[ERR] Source List run failed: %s", exc)

        except Exception as exc:
            run.status = "failed"
            run.error_message = str(exc)
            run.completed_at = datetime.now(timezone.utc)
            db.session.commit()
            logger.error("[ERR] Source List run unexpected error: %s", exc)


@pipeline_bp.route("/source-list", methods=["POST"])
@login_required
def run_source_list():
    """
    Start a Source List prompt run (async).

    Body: { "prompt_id": int }
    Returns immediately: { story_id, status: "running" }
    Poll GET /api/pipeline/status/<story_id> for the result.
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
    db.session.commit()

    # Launch background thread
    app = current_app._get_current_object()
    thread = threading.Thread(
        target=_run_source_list_background,
        args=(app, story.id, prompt.prompt_text, context_str, prompt.id),
    )
    thread.start()

    return jsonify({"story_id": story.id, "status": "running"}), 202


def _run_pipeline_background(app, story_id, selected_story, refinement_prompt_id, user_email):
    """Run full pipeline in a background thread."""
    with app.app_context():
        try:
            run_pipeline(
                story_id=story_id,
                selected_story=selected_story,
                refinement_prompt_id=refinement_prompt_id,
                user_email=user_email,
            )
        except Exception as exc:
            logger.error("[ERR] Pipeline run failed: %s", exc)
            # Commit any flushed failure statuses from _run_grok_step
            try:
                db.session.commit()
            except Exception:
                db.session.rollback()


@pipeline_bp.route("/run", methods=["POST"])
@login_required
def run_full_pipeline():
    """
    Start full pipeline (async): refinement → Amy Bot → CMS/kill.

    Body: { "story_id": int, "selected_story": str, "refinement_prompt_id": int }
    Returns immediately: { story_id, status: "running" }
    Poll GET /api/pipeline/status/<story_id> for the result.
    """
    body = request.get_json(silent=True) or {}
    story_id = body.get("story_id")
    selected_story = body.get("selected_story") or ""
    refinement_prompt_id = body.get("refinement_prompt_id")

    if not story_id or not selected_story or not refinement_prompt_id:
        return jsonify({"error": "story_id, selected_story, and refinement_prompt_id are required"}), 400

    story = db.session.get(Story, story_id)
    if not story:
        return jsonify({"error": "Story not found"}), 404

    # Create a placeholder "running" refinement run so the status endpoint
    # knows the pipeline is in progress before the background thread starts
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
        target=_run_pipeline_background,
        args=(app, story_id, selected_story, refinement_prompt_id, g.current_user.email),
    )
    thread.start()

    return jsonify({"story_id": story_id, "status": "running"}), 202


@pipeline_bp.route("/status/<int:story_id>", methods=["GET"])
@login_required
def get_pipeline_status(story_id):
    """
    Poll for pipeline status.

    Returns the story with its current state and pipeline runs.
    """
    story = db.session.get(Story, story_id)
    if not story:
        return jsonify({"error": "Story not found"}), 404

    runs = PipelineRun.query.filter_by(story_id=story_id).order_by(PipelineRun.id).all()

    # Determine overall status from runs
    statuses = [r.status for r in runs]
    if "running" in statuses:
        overall = "running"
    elif "failed" in statuses:
        overall = "failed"
    else:
        overall = "completed"

    return jsonify({
        "story_id": story.id,
        "status": overall,
        "source_list_output": story.source_list_output,
        "url_enrichments": story.url_enrichments,
        "selected_story": story.selected_story,
        "refinement_output": story.refinement_output,
        "amy_bot_output": story.amy_bot_output,
        "validation_decision": story.validation_decision,
        "is_valid": story.is_valid,
        "pushed_to_cms": story.pushed_to_cms,
        "opportunity": story.opportunity,
        "state": story.state,
        "publications": story.publications,
        "runs": [
            {
                "step_type": r.step_type,
                "status": r.status,
                "error_message": r.error_message,
                "duration_ms": r.duration_ms,
            }
            for r in runs
        ],
    })
