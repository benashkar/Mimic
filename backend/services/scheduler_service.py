"""
Scheduler service — runs scheduled source list prompts daily.

Called by the cron endpoint (POST /api/scheduler/run). For each
schedule-enabled source-list prompt:
  1. Calls Grok with search (same as manual run)
  2. Enriches URLs (best-effort)
  3. Parses sources with the Python source parser
  4. Creates QueueItem rows for human review

Prompts run sequentially to avoid Grok rate limits. Each prompt is
wrapped in try/except so one failure doesn't block others.
"""
import logging
import time
from datetime import datetime, timedelta, timezone

from models import db
from models.prompt import Prompt
from models.story import Story
from models.pipeline_run import PipelineRun
from models.queue_item import QueueItem
from services.grok_service import call_grok_with_search
from services.url_enrichment_service import enrich_urls
from services.source_parser import parse_sources

logger = logging.getLogger(__name__)


def run_scheduled_source_lists():
    """Run all schedule-enabled source list prompts and populate the queue.

    Returns:
        dict with keys: prompts_run (int), items_created (int), errors (list[str])
    """
    prompts = Prompt.query.filter_by(
        prompt_type="source-list",
        is_active=True,
        schedule_enabled=True,
    ).all()

    logger.info("[OK] Scheduler starting: %d prompts to run", len(prompts))

    results = {
        "prompts_run": 0,
        "items_created": 0,
        "errors": [],
    }

    for prompt in prompts:
        try:
            items_created = _run_single_prompt(prompt)
            results["prompts_run"] += 1
            results["items_created"] += items_created
            logger.info(
                "[OK] Scheduler completed prompt %d (%s): %d items",
                prompt.id, prompt.name, items_created,
            )
        except Exception as exc:
            error_msg = f"Prompt {prompt.id} ({prompt.name}): {exc}"
            results["errors"].append(error_msg)
            logger.error("[ERR] Scheduler failed for prompt %d: %s", prompt.id, exc)
            # Rollback any partial state from this prompt
            db.session.rollback()

    logger.info(
        "[OK] Scheduler finished: %d prompts, %d items, %d errors",
        results["prompts_run"], results["items_created"], len(results["errors"]),
    )
    return results


def _run_single_prompt(prompt):
    """Run a single source list prompt through Grok and create queue items.

    Args:
        prompt: Prompt instance (source-list, active, schedule_enabled).

    Returns:
        int: Number of QueueItem rows created.
    """
    # Build context (same logic as routes/pipeline.py lines 97-121)
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
    today = datetime.now(timezone.utc).strftime("%B %d, %Y")
    context_parts.append(f"Today's date is {today}.")
    context_parts.append(
        "CRITICAL: For every X/Twitter post, you MUST include the real, "
        "actual direct URL to the tweet (e.g. https://x.com/username/status/123456). "
        "Never use placeholders like '(Placeholder for actual X post link)'. "
        "Include the date each post was published. "
        "Only include posts from the timeframe specified in the prompt — "
        "if the prompt says 'last 24-48 hours' or 'last 7 days', do NOT "
        "include older posts. Use today's date above to calculate recency."
    )
    context_str = "\n".join(context_parts)

    # Create Story record (created_by='scheduler')
    story = Story(
        source_list_prompt_id=prompt.id,
        source_list_input=prompt.prompt_text,
        opportunity=prompt.opportunity,
        state=prompt.state,
        publications=prompt.publications,
        topic_summary=prompt.topic_summary,
        context=prompt.context,
        created_by="scheduler",
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

    # Call Grok with search
    start_ms = int(time.time() * 1000)
    output = call_grok_with_search(prompt.prompt_text, context=context_str)
    duration_ms = int(time.time() * 1000) - start_ms

    story.source_list_output = output

    # Enrich URLs (best-effort)
    try:
        enrichments = enrich_urls(output)
        if enrichments:
            story.url_enrichments = enrichments
    except Exception as enrich_exc:
        logger.warning("[--] URL enrichment failed for prompt %d: %s", prompt.id, enrich_exc)

    # Mark pipeline run complete
    run.output_text = output
    run.status = "completed"
    run.duration_ms = duration_ms
    run.completed_at = datetime.now(timezone.utc)

    # Parse sources and create queue items
    sources = parse_sources(output)
    items_created = 0
    for source in sources:
        item = QueueItem(
            story_id=story.id,
            prompt_id=prompt.id,
            label=source["label"],
            body=source["body"],
            agency=prompt.agency,
            opportunity=prompt.opportunity,
            state=prompt.state,
            status="pending",
        )
        db.session.add(item)
        items_created += 1

    db.session.commit()
    return items_created
