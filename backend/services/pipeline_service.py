"""
Pipeline service — orchestrates the full story pipeline.

Flow:
  1. Look up story and refinement prompt
  2. Build refinement input (PAPA/PSST prompt + selected story + routing)
  3. Call Grok: refinement
  4. Look up active Amy Bot prompt
  5. Call Grok: Amy Bot validation
  6. Parse decision: APPROVE → push to CMS, REJECT → kill
  7. Log all steps as PipelineRun records

REJECT means the story is dead. Fixes in Amy Bot output are logged
but never applied. No retry.
"""
import logging
import time
from datetime import datetime, timezone

from models import db
from models.prompt import Prompt
from models.story import Story
from models.pipeline_run import PipelineRun
from services.grok_service import call_grok, GrokAPIError
from services.validation_service import parse_decision
from services import cms_service

logger = logging.getLogger(__name__)


def run_pipeline(story_id, selected_story, refinement_prompt_id, user_email):
    """
    Run the full pipeline: refinement → Amy Bot → CMS or kill.

    Args:
        story_id: ID of the Story created during Source List run.
        selected_story: The user's selected story/source text.
        refinement_prompt_id: ID of the PAPA or PSST prompt to use.
        user_email: Email of the user running the pipeline.

    Returns:
        dict with story data and pipeline result.

    Raises:
        ValueError: If story or prompts not found.
        GrokAPIError: If a Grok API call fails.
    """
    story = db.session.get(Story, story_id)
    if not story:
        raise ValueError(f"Story {story_id} not found")

    refinement_prompt = db.session.get(Prompt, refinement_prompt_id)
    if not refinement_prompt:
        raise ValueError(f"Refinement prompt {refinement_prompt_id} not found")

    if refinement_prompt.prompt_type != "papa":
        raise ValueError("Refinement prompt must be type 'papa' (PAPA or PSST)")

    # Find active Amy Bot prompt
    amy_prompt = Prompt.query.filter_by(
        prompt_type="amy-bot", is_active=True
    ).first()
    if not amy_prompt:
        raise ValueError("No active Amy Bot prompt found")

    # Store selected story on the Story record
    story.selected_story = selected_story
    story.refinement_prompt_id = refinement_prompt.id
    story.amy_bot_prompt_id = amy_prompt.id

    # ---- Step 1: Refinement (PAPA or PSST) ----
    refinement_context = _build_refinement_context(story)
    refinement_input = f"{refinement_prompt.prompt_text}\n\n---\n\nSource material:\n{selected_story}\n\n{refinement_context}"

    story.refinement_input = refinement_input
    refinement_output = _run_grok_step(
        story=story,
        prompt=refinement_prompt,
        step_type="refinement",
        input_text=refinement_input,
    )
    story.refinement_output = refinement_output

    # ---- Step 2: Amy Bot Validation ----
    amy_input = f"{amy_prompt.prompt_text}\n\n---\n\nPitch to review:\n{refinement_output}"
    story.amy_bot_input = amy_input
    amy_output = _run_grok_step(
        story=story,
        prompt=amy_prompt,
        step_type="amy-bot",
        input_text=amy_input,
    )
    story.amy_bot_output = amy_output

    # ---- Step 3: Parse Decision ----
    is_valid = parse_decision(amy_output)
    story.is_valid = is_valid

    if is_valid:
        story.validation_decision = "APPROVE"
        cms_response = cms_service.push_to_cms(story)
        story.pushed_to_cms = True
        story.cms_push_date = datetime.now(timezone.utc)
        story.cms_response = str(cms_response)
        logger.info("[OK] Pipeline APPROVED: story_id=%d", story.id)
    else:
        # Kill it. Log. Do nothing else.
        story.validation_decision = "REJECT"
        story.is_valid = False
        logger.info("[--] Pipeline REJECTED: story_id=%d (story killed)", story.id)

    db.session.commit()

    return story.to_dict()


def _build_refinement_context(story):
    """Build context string from story's routing metadata."""
    parts = []
    if story.opportunity:
        parts.append(f"Opportunity: {story.opportunity}")
    if story.state:
        parts.append(f"State: {story.state}")
    if story.publications:
        parts.append(f"Target Publications: {story.publications}")
    if story.topic_summary:
        parts.append(f"Topic: {story.topic_summary}")
    if story.context:
        parts.append(f"Context: {story.context}")
    return "\n".join(parts)


def _run_grok_step(story, prompt, step_type, input_text):
    """
    Call Grok and log the result as a PipelineRun.

    Args:
        story: Story instance.
        prompt: Prompt instance used for this step.
        step_type: 'refinement' or 'amy-bot'.
        input_text: The full input sent to Grok.

    Returns:
        str: Grok response content.

    Raises:
        GrokAPIError: If the API call fails (logged and re-raised).
    """
    run = PipelineRun(
        story_id=story.id,
        prompt_id=prompt.id,
        step_type=step_type,
        status="running",
        input_text=input_text,
    )
    db.session.add(run)
    db.session.flush()

    start_ms = int(time.time() * 1000)
    try:
        output = call_grok(input_text)
        duration_ms = int(time.time() * 1000) - start_ms

        run.output_text = output
        run.status = "completed"
        run.duration_ms = duration_ms
        run.completed_at = datetime.now(timezone.utc)
        db.session.flush()

        return output

    except GrokAPIError:
        duration_ms = int(time.time() * 1000) - start_ms
        run.status = "failed"
        run.error_message = str(GrokAPIError)
        run.duration_ms = duration_ms
        run.completed_at = datetime.now(timezone.utc)
        db.session.flush()
        raise
