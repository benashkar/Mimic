"""
Tests for SQLAlchemy models — CRUD and default values.

Tests all 4 models: User, Prompt, Story, PipelineRun.
Uses db_session fixture for per-test isolation (rollback after each).
"""
from models.user import User
from models.prompt import Prompt
from models.story import Story
from models.pipeline_run import PipelineRun


def test_create_user(db_session):
    """Can create a user with required fields, defaults applied."""
    user = User(
        google_id="google-123",
        email="test@plmediaagency.com",
        display_name="Test User",
    )
    db_session.add(user)
    db_session.flush()

    assert user.id is not None
    assert user.role == "user"
    assert user.is_active is True
    assert user.created_at is not None


def test_create_prompt_source_list(db_session):
    """Can create a source-list prompt with routing metadata."""
    prompt = Prompt(
        prompt_type="source-list",
        name="IL Local Gov - Pritzker",
        prompt_text="Find the most recent information about...",
        issuer="Max",
        opportunity="Illinois Local Government News",
        state="IL",
        publications="Chicago City Wire",
        pitches_per_week=4,
    )
    db_session.add(prompt)
    db_session.flush()

    assert prompt.id is not None
    assert prompt.prompt_type == "source-list"
    assert prompt.issuer == "Max"
    assert prompt.is_active is True


def test_create_prompt_papa_nullable_routing(db_session):
    """PAPA/PSST prompts have NULL routing metadata fields."""
    prompt = Prompt(
        prompt_type="papa",
        name="PAPA - Provided Announcement Pitch Assistant",
        prompt_text="Process this announcement into a structured pitch...",
    )
    db_session.add(prompt)
    db_session.flush()

    assert prompt.id is not None
    assert prompt.issuer is None
    assert prompt.opportunity is None
    assert prompt.state is None
    assert prompt.pitches_per_week is None


def test_create_story(db_session):
    """Can create a story with default values for is_valid and pushed_to_cms."""
    story = Story(
        selected_story="Breaking: Governor signs new bill",
        opportunity="Illinois Local Government News",
        state="IL",
        created_by="test@plmediaagency.com",
    )
    db_session.add(story)
    db_session.flush()

    assert story.id is not None
    assert story.is_valid is False
    assert story.pushed_to_cms is False
    assert story.created_at is not None


def test_create_pipeline_run(db_session):
    """Can create a pipeline run with required step_type."""
    run = PipelineRun(
        step_type="source-list",
        input_text="Search prompt input",
    )
    db_session.add(run)
    db_session.flush()

    assert run.id is not None
    assert run.status == "pending"
    assert run.started_at is not None
    assert run.completed_at is None


def test_user_to_dict(db_session):
    """User.to_dict() returns all expected keys."""
    user = User(
        google_id="google-456",
        email="admin@plmediaagency.com",
        display_name="Admin",
        role="admin",
    )
    db_session.add(user)
    db_session.flush()

    d = user.to_dict()
    assert d["email"] == "admin@plmediaagency.com"
    assert d["role"] == "admin"
    assert "id" in d
    assert "created_at" in d
