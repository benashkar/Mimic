"""
Tests for model relationships, serialization, and edge cases.

Covers: Story.to_dict(), Prompt.to_dict(), foreign key relationships,
default values, nullable fields.
"""
from datetime import datetime, timezone

from models import db
from models.user import User
from models.prompt import Prompt
from models.story import Story
from models.pipeline_run import PipelineRun


class TestStoryToDict:
    """Tests for Story.to_dict() serialization."""

    def test_includes_all_key_fields(self, app, db_session):
        """to_dict includes pipeline fields."""
        with app.app_context():
            story = Story(
                created_by="test",
                validation_decision="APPROVE",
                is_valid=True,
                pushed_to_cms=True,
                opportunity="TestOpp",
                state="IL",
            )
            db_session.add(story)
            db_session.flush()

            d = story.to_dict()
            assert d["id"] == story.id
            assert d["validation_decision"] == "APPROVE"
            assert d["is_valid"] is True
            assert d["pushed_to_cms"] is True
            assert d["opportunity"] == "TestOpp"

    def test_defaults_for_new_story(self, app, db_session):
        """New story has correct defaults."""
        with app.app_context():
            story = Story(created_by="test")
            db_session.add(story)
            db_session.flush()

            assert story.is_valid is False
            assert story.pushed_to_cms is False
            assert story.validation_decision is None
            assert story.refinement_output is None
            assert story.amy_bot_output is None


class TestPromptToDict:
    """Tests for Prompt.to_dict() serialization."""

    def test_source_list_includes_routing(self, app, db_session):
        """Source list prompt serialization includes routing metadata."""
        with app.app_context():
            prompt = Prompt(
                prompt_type="source-list",
                name="Test SL",
                prompt_text="Find stories",
                opportunity="Kin",
                state="CA",
                publications="LA Times",
                pitches_per_week=4,
                created_by="test",
            )
            db_session.add(prompt)
            db_session.flush()

            d = prompt.to_dict()
            assert d["opportunity"] == "Kin"
            assert d["state"] == "CA"
            assert d["publications"] == "LA Times"
            assert d["pitches_per_week"] == 4

    def test_papa_excludes_routing(self, app, db_session):
        """PAPA prompt to_dict does not include routing fields."""
        with app.app_context():
            prompt = Prompt(
                prompt_type="papa",
                name="PAPA",
                prompt_text="Process announcements",
                created_by="test",
            )
            db_session.add(prompt)
            db_session.flush()

            d = prompt.to_dict()
            assert "opportunity" not in d
            assert "state" not in d
            assert "pitches_per_week" not in d


class TestPipelineRunModel:
    """Tests for PipelineRun model."""

    def test_completed_run_has_duration(self, app, db_session):
        """Completed run stores duration_ms."""
        with app.app_context():
            story = Story(created_by="test")
            db_session.add(story)
            db_session.flush()

            run = PipelineRun(
                story_id=story.id,
                step_type="refinement",
                status="completed",
                duration_ms=5432,
                output_text="Refined output here",
                completed_at=datetime.now(timezone.utc),
            )
            db_session.add(run)
            db_session.flush()

            assert run.duration_ms == 5432
            assert run.output_text == "Refined output here"
            assert run.completed_at is not None

    def test_failed_run_has_error(self, app, db_session):
        """Failed run stores error_message."""
        with app.app_context():
            story = Story(created_by="test")
            db_session.add(story)
            db_session.flush()

            run = PipelineRun(
                story_id=story.id,
                step_type="source-list",
                status="failed",
                error_message="Rate limit exceeded (429)",
                duration_ms=1200,
            )
            db_session.add(run)
            db_session.flush()

            assert run.status == "failed"
            assert "429" in run.error_message


class TestForeignKeyRelationships:
    """Tests for model FK relationships."""

    def test_story_references_prompts(self, app, db_session):
        """Story can reference source_list, refinement, and amy_bot prompts."""
        with app.app_context():
            sl = Prompt(prompt_type="source-list", name="SL", prompt_text="t", created_by="t")
            papa = Prompt(prompt_type="papa", name="PAPA", prompt_text="t", created_by="t")
            amy = Prompt(prompt_type="amy-bot", name="Amy", prompt_text="t", created_by="t")
            db_session.add_all([sl, papa, amy])
            db_session.flush()

            story = Story(
                source_list_prompt_id=sl.id,
                refinement_prompt_id=papa.id,
                amy_bot_prompt_id=amy.id,
                created_by="test",
            )
            db_session.add(story)
            db_session.flush()

            assert story.source_list_prompt_id == sl.id
            assert story.refinement_prompt_id == papa.id
            assert story.amy_bot_prompt_id == amy.id

    def test_pipeline_run_references_story(self, app, db_session):
        """PipelineRun is linked to a Story."""
        with app.app_context():
            story = Story(created_by="test")
            db_session.add(story)
            db_session.flush()

            run = PipelineRun(story_id=story.id, step_type="refinement", status="pending")
            db_session.add(run)
            db_session.flush()

            assert run.story_id == story.id
            fetched = PipelineRun.query.filter_by(story_id=story.id).first()
            assert fetched.id == run.id
