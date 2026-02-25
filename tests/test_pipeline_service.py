"""
Tests for services/pipeline_service.py and routes/pipeline.py.

All Grok API calls are mocked. Covers:
  - Source list route: returns 202 (async), wrong type
  - Source list background: completes successfully
  - Full pipeline service: APPROVE flow, REJECT flow, refinement failure
  - Pipeline route: returns 202 (async)
  - Status endpoint: polling, not-found, auth
"""
import json
from unittest.mock import patch

import pytest

from models import db
from models.prompt import Prompt
from models.story import Story
from models.pipeline_run import PipelineRun


class _SyncThread:
    """Drop-in replacement for threading.Thread that runs synchronously."""
    def __init__(self, target=None, args=(), kwargs=None):
        self.target = target
        self.args = args
        self.kwargs = kwargs or {}

    def start(self):
        self.target(*self.args, **self.kwargs)


class TestSourceListRoute:
    """Tests for POST /api/pipeline/source-list."""

    @patch("routes.pipeline.threading.Thread", _SyncThread)
    @patch("routes.pipeline.call_grok")
    def test_source_list_success(self, mock_grok, client, db_session, auth_headers):
        """Valid source-list prompt returns 202, background processes, status shows result."""
        mock_grok.return_value = "Topic 1: Illinois budget...\nTopic 2: Chicago transit..."

        prompt = Prompt(
            prompt_type="source-list", name="IL Test",
            prompt_text="Find stories...", opportunity="IL News",
            state="Illinois", is_active=True,
        )
        db_session.add(prompt)
        db_session.commit()

        headers = auth_headers("runner@plmediaagency.com", "user")
        resp = client.post(
            "/api/pipeline/source-list",
            data=json.dumps({"prompt_id": prompt.id}),
            content_type="application/json",
            headers=headers,
        )
        assert resp.status_code == 202
        data = resp.get_json()
        assert "story_id" in data
        assert data["status"] == "running"

        # Expire stale objects so status endpoint reads fresh from DB
        db_session.expire_all()

        # Poll status endpoint (sync thread already completed)
        status_resp = client.get(
            f"/api/pipeline/status/{data['story_id']}",
            headers=headers,
        )
        assert status_resp.status_code == 200
        status_data = status_resp.get_json()
        assert status_data["status"] == "completed"
        assert "Illinois budget" in status_data["source_list_output"]

    def test_source_list_wrong_type(self, client, db_session, auth_headers):
        """Non-source-list prompt returns 400."""
        prompt = Prompt(
            prompt_type="papa", name="PAPA",
            prompt_text="text", is_active=True,
        )
        db_session.add(prompt)
        db_session.commit()

        headers = auth_headers("runner2@plmediaagency.com", "user")
        resp = client.post(
            "/api/pipeline/source-list",
            data=json.dumps({"prompt_id": prompt.id}),
            content_type="application/json",
            headers=headers,
        )
        assert resp.status_code == 400
        assert "not a source-list" in resp.get_json()["error"]


class TestPipelineService:
    """Tests for run_pipeline() directly — no threading/context issues."""

    def _setup_prompts_and_story(self, db_session):
        """Create the prompts and story needed for pipeline tests."""
        source_prompt = Prompt(
            prompt_type="source-list", name="SL Test",
            prompt_text="Find...", is_active=True,
        )
        refinement_prompt = Prompt(
            prompt_type="papa", name="PAPA Test",
            prompt_text="Process announcements...", is_active=True,
        )
        amy_prompt = Prompt(
            prompt_type="amy-bot", name="Amy Bot Test",
            prompt_text="Review pitch...", is_active=True,
        )
        db_session.add_all([source_prompt, refinement_prompt, amy_prompt])
        db_session.flush()

        story = Story(
            source_list_prompt_id=source_prompt.id,
            source_list_output="Topic about Illinois budget",
            opportunity="IL News",
            state="Illinois",
        )
        db_session.add(story)
        db_session.commit()

        return story, refinement_prompt, amy_prompt

    @patch("services.pipeline_service.call_grok")
    def test_pipeline_approve(self, mock_grok, client, db_session, auth_headers):
        """Pipeline with APPROVE decision pushes to CMS."""
        story, ref_prompt, _ = self._setup_prompts_and_story(db_session)

        mock_grok.side_effect = [
            "Headline: Illinois budget...\nLede: ...\nFactoid 1: ...",
            'DECISION: APPROVE\n"All fields meet editorial standards."',
        ]

        from services.pipeline_service import run_pipeline
        result = run_pipeline(
            story_id=story.id,
            selected_story="Illinois governor signs budget bill",
            refinement_prompt_id=ref_prompt.id,
            user_email="pipeline@plmediaagency.com",
        )

        assert result["validation_decision"] == "APPROVE"
        assert result["is_valid"] is True
        assert result["pushed_to_cms"] is True

    @patch("services.pipeline_service.call_grok")
    def test_pipeline_reject(self, mock_grok, client, db_session, auth_headers):
        """Pipeline with REJECT decision kills the story."""
        story, ref_prompt, _ = self._setup_prompts_and_story(db_session)

        mock_grok.side_effect = [
            "Headline: Bad headline...",
            "DECISION: REJECT \u2014 with fixes\nHL-VAGUE: headline needs context",
        ]

        from services.pipeline_service import run_pipeline
        result = run_pipeline(
            story_id=story.id,
            selected_story="Some story text",
            refinement_prompt_id=ref_prompt.id,
            user_email="pipeline2@plmediaagency.com",
        )

        assert result["validation_decision"] == "REJECT"
        assert result["is_valid"] is False
        assert result["pushed_to_cms"] is False

    @patch("services.pipeline_service.call_grok")
    def test_pipeline_refinement_fails(self, mock_grok, client, db_session, auth_headers):
        """If refinement step fails, no Amy Bot call happens."""
        from services.grok_service import GrokAPIError

        story, ref_prompt, _ = self._setup_prompts_and_story(db_session)
        mock_grok.side_effect = GrokAPIError("API timeout", status_code=408)

        from services.pipeline_service import run_pipeline
        with pytest.raises(GrokAPIError):
            run_pipeline(
                story_id=story.id,
                selected_story="Story text",
                refinement_prompt_id=ref_prompt.id,
                user_email="pipeline3@plmediaagency.com",
            )
        # Grok was only called once (refinement failed, Amy Bot never called)
        assert mock_grok.call_count == 1


class TestPipelineRoute:
    """Tests for POST /api/pipeline/run returns 202."""

    def test_pipeline_run_returns_202(self, client, db_session, auth_headers):
        """POST /api/pipeline/run returns 202 and launches background thread."""
        source_prompt = Prompt(
            prompt_type="source-list", name="SL", prompt_text="Find...", is_active=True,
        )
        ref_prompt = Prompt(
            prompt_type="papa", name="PAPA", prompt_text="Process...", is_active=True,
        )
        amy_prompt = Prompt(
            prompt_type="amy-bot", name="Amy Bot", prompt_text="Review...", is_active=True,
        )
        db_session.add_all([source_prompt, ref_prompt, amy_prompt])
        db_session.flush()

        story = Story(
            source_list_prompt_id=source_prompt.id,
            source_list_output="Test story",
        )
        db_session.add(story)
        db_session.commit()

        headers = auth_headers("runner@plmediaagency.com", "user")
        with patch("routes.pipeline.threading.Thread") as mock_thread:
            mock_thread.return_value.start = lambda: None  # Don't actually start
            resp = client.post(
                "/api/pipeline/run",
                data=json.dumps({
                    "story_id": story.id,
                    "selected_story": "Selected story text",
                    "refinement_prompt_id": ref_prompt.id,
                }),
                content_type="application/json",
                headers=headers,
            )
        assert resp.status_code == 202
        data = resp.get_json()
        assert data["story_id"] == story.id
        assert data["status"] == "running"

    def test_pipeline_run_missing_fields(self, client, db_session, auth_headers):
        """POST /api/pipeline/run with missing fields returns 400."""
        headers = auth_headers("runner@plmediaagency.com", "user")
        resp = client.post(
            "/api/pipeline/run",
            data=json.dumps({"story_id": 1}),
            content_type="application/json",
            headers=headers,
        )
        assert resp.status_code == 400


class TestStatusEndpoint:
    """Tests for GET /api/pipeline/status/<story_id>."""

    def test_status_completed(self, client, db_session, auth_headers):
        """Status endpoint returns completed story data."""
        prompt = Prompt(
            prompt_type="source-list", name="SL", prompt_text="Find...", is_active=True,
        )
        db_session.add(prompt)
        db_session.flush()

        story = Story(
            source_list_prompt_id=prompt.id,
            source_list_output="Output text",
            validation_decision="APPROVE",
            is_valid=True,
            pushed_to_cms=True,
        )
        db_session.add(story)
        db_session.flush()

        run = PipelineRun(
            story_id=story.id, prompt_id=prompt.id,
            step_type="source-list", status="completed",
        )
        db_session.add(run)
        db_session.commit()

        headers = auth_headers("poll@plmediaagency.com", "user")
        resp = client.get(f"/api/pipeline/status/{story.id}", headers=headers)
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["status"] == "completed"
        assert data["validation_decision"] == "APPROVE"
        assert data["source_list_output"] == "Output text"

    def test_status_not_found(self, client, db_session, auth_headers):
        """Non-existent story returns 404."""
        headers = auth_headers("poll@plmediaagency.com", "user")
        resp = client.get("/api/pipeline/status/99999", headers=headers)
        assert resp.status_code == 404

    def test_status_requires_auth(self, client, db_session):
        """Status endpoint requires authentication."""
        resp = client.get("/api/pipeline/status/1")
        assert resp.status_code == 401
