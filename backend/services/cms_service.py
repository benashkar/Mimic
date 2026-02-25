"""
CMS service — stub for Lumen CMS API integration.

This is a placeholder until the Lumen API docs are provided.
Phase 8 will replace this with real CMS push calls.
"""
import logging

logger = logging.getLogger(__name__)


def push_to_cms(story):
    """
    Push an approved story to the Lumen CMS.

    Currently a stub — logs the action and returns a mock response.
    Phase 8 will implement real API calls.

    Args:
        story: Story model instance with all pipeline data.

    Returns:
        dict with CMS response info.
    """
    logger.info(
        "[OK] CMS push (stub): story_id=%d, opportunity=%s",
        story.id,
        story.opportunity or "unknown",
    )
    return {
        "status": "stub",
        "message": "CMS integration pending — story logged as approved",
        "story_id": story.id,
    }
