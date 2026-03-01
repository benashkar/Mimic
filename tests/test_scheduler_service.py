"""
Tests for services/scheduler_service.py — daily scheduled source list runner.

Covers: Grok call, Story/PipelineRun/QueueItem creation, error isolation,
        no schedule-enabled prompts, URL enrichment integration.
"""
import json
from unittest.mock import patch, MagicMock

from models import db
from models.prompt import Prompt
from models.story import Story
from models.pipeline_run import PipelineRun
from models.queue_item import QueueItem


MOCK_GROK_OUTPUT = """**List A: Michigan Sources**
https://x.com/reporter1/status/111 - Healthcare bill update
https://x.com/reporter2/status/222 - Education funding news"""


class TestRunScheduledSourceLists:
    """Tests for the main scheduler orchestrator."""

    @patch("services.scheduler_service.enrich_urls")
    @patch("services.scheduler_service.call_grok_with_search")
    def test_creates_story_and_queue_items(self, mock_grok, mock_enrich, app, db_session):
        """Scheduled run creates Story, PipelineRun, and QueueItems."""
        from services.scheduler_service import run_scheduled_source_lists

        mock_grok.return_value = MOCK_GROK_OUTPUT
        mock_enrich.return_value = None

        prompt = Prompt(
            prompt_type="source-list",
            name="Michigan SL",
            prompt_text="Find Michigan stories",
            agency="Agency A",
            opportunity="Michigan",
            state="MI",
            is_active=True,
            schedule_enabled=True,
            created_by="test",
        )
        db_session.add(prompt)
        db_session.commit()

        with app.app_context():
            result = run_scheduled_source_lists()

        assert result["prompts_run"] == 1
        assert result["items_created"] == 2
        assert result["errors"] == []

        # Verify Story created
        story = Story.query.filter_by(source_list_prompt_id=prompt.id).first()
        assert story is not None
        assert story.created_by == "scheduler"
        assert story.opportunity == "Michigan"
        assert story.source_list_output == MOCK_GROK_OUTPUT

        # Verify PipelineRun created
        run = PipelineRun.query.filter_by(story_id=story.id).first()
        assert run is not None
        assert run.status == "completed"
        assert run.step_type == "source-list"

        # Verify QueueItems created
        items = QueueItem.query.filter_by(story_id=story.id).all()
        assert len(items) == 2
        assert items[0].status == "pending"
        assert items[0].agency == "Agency A"
        assert items[0].opportunity == "Michigan"

    @patch("services.scheduler_service.enrich_urls")
    @patch("services.scheduler_service.call_grok_with_search")
    def test_skips_inactive_prompts(self, mock_grok, mock_enrich, app, db_session):
        """Inactive prompts are not run even if schedule_enabled."""
        from services.scheduler_service import run_scheduled_source_lists

        prompt = Prompt(
            prompt_type="source-list",
            name="Inactive",
            prompt_text="test",
            is_active=False,
            schedule_enabled=True,
            created_by="test",
        )
        db_session.add(prompt)
        db_session.commit()

        with app.app_context():
            result = run_scheduled_source_lists()

        assert result["prompts_run"] == 0
        assert result["items_created"] == 0
        mock_grok.assert_not_called()

    @patch("services.scheduler_service.enrich_urls")
    @patch("services.scheduler_service.call_grok_with_search")
    def test_skips_non_scheduled_prompts(self, mock_grok, mock_enrich, app, db_session):
        """Prompts without schedule_enabled=True are not run."""
        from services.scheduler_service import run_scheduled_source_lists

        prompt = Prompt(
            prompt_type="source-list",
            name="Manual Only",
            prompt_text="test",
            is_active=True,
            schedule_enabled=False,
            created_by="test",
        )
        db_session.add(prompt)
        db_session.commit()

        with app.app_context():
            result = run_scheduled_source_lists()

        assert result["prompts_run"] == 0
        mock_grok.assert_not_called()

    @patch("services.scheduler_service.enrich_urls")
    @patch("services.scheduler_service.call_grok_with_search")
    def test_one_failure_does_not_block_others(self, mock_grok, mock_enrich, app, db_session):
        """If one prompt fails, others still run successfully."""
        from services.scheduler_service import run_scheduled_source_lists

        # First call fails, second succeeds
        mock_grok.side_effect = [
            RuntimeError("Grok API timeout"),
            MOCK_GROK_OUTPUT,
        ]
        mock_enrich.return_value = None

        p1 = Prompt(
            prompt_type="source-list", name="Failing", prompt_text="fail",
            is_active=True, schedule_enabled=True, created_by="test",
        )
        p2 = Prompt(
            prompt_type="source-list", name="Succeeding", prompt_text="ok",
            agency="Agency B", opportunity="Ohio", is_active=True,
            schedule_enabled=True, created_by="test",
        )
        db_session.add_all([p1, p2])
        db_session.commit()

        with app.app_context():
            result = run_scheduled_source_lists()

        assert result["prompts_run"] == 1
        assert result["items_created"] == 2
        assert len(result["errors"]) == 1
        assert "Failing" in result["errors"][0]

    @patch("services.scheduler_service.enrich_urls")
    @patch("services.scheduler_service.call_grok_with_search")
    def test_enrichment_failure_does_not_block(self, mock_grok, mock_enrich, app, db_session):
        """URL enrichment failure still creates queue items."""
        from services.scheduler_service import run_scheduled_source_lists

        mock_grok.return_value = MOCK_GROK_OUTPUT
        mock_enrich.side_effect = RuntimeError("enrichment boom")

        prompt = Prompt(
            prompt_type="source-list", name="Test", prompt_text="t",
            is_active=True, schedule_enabled=True, created_by="test",
        )
        db_session.add(prompt)
        db_session.commit()

        with app.app_context():
            result = run_scheduled_source_lists()

        assert result["prompts_run"] == 1
        assert result["items_created"] == 2
        assert result["errors"] == []

    @patch("services.scheduler_service.enrich_urls")
    @patch("services.scheduler_service.call_grok_with_search")
    def test_no_sources_parsed_creates_no_items(self, mock_grok, mock_enrich, app, db_session):
        """If Grok output has no parseable sources, no queue items created."""
        from services.scheduler_service import run_scheduled_source_lists

        mock_grok.return_value = "No relevant sources found for this query."
        mock_enrich.return_value = None

        prompt = Prompt(
            prompt_type="source-list", name="Empty", prompt_text="t",
            is_active=True, schedule_enabled=True, created_by="test",
        )
        db_session.add(prompt)
        db_session.commit()

        with app.app_context():
            result = run_scheduled_source_lists()

        assert result["prompts_run"] == 1
        assert result["items_created"] == 0
