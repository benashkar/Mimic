"""
Scheduler routes — Cron job endpoint for daily source list runs.

POST /api/scheduler/run — Authenticated via X-Scheduler-Secret header
(not JWT — cron jobs have no user session). Triggers all schedule-enabled
source list prompts and populates the queue.
"""
import logging

from flask import Blueprint, request, jsonify, current_app

from services.scheduler_service import run_scheduled_source_lists

logger = logging.getLogger(__name__)

scheduler_bp = Blueprint("scheduler", __name__)


@scheduler_bp.route("/run", methods=["POST"])
def run_scheduler():
    """
    Trigger scheduled source list runs (cron endpoint).

    Auth: X-Scheduler-Secret header must match SCHEDULER_SECRET env var.
    Returns: { prompts_run, items_created, errors }
    """
    secret = current_app.config.get("SCHEDULER_SECRET") or ""
    provided = request.headers.get("X-Scheduler-Secret") or ""

    if not secret or not provided or provided != secret:
        logger.warning("[ERR] Scheduler auth failed: invalid or missing secret")
        return jsonify({"error": "Unauthorized"}), 401

    logger.info("[OK] Scheduler triggered via cron endpoint")
    result = run_scheduled_source_lists()
    return jsonify(result)
