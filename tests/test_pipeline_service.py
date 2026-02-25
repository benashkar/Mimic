"""
Tests for services/pipeline_service.py and routes/pipeline.py.

All Grok API calls are mocked. Covers:
  - Source list run: success, wrong type
  - Full pipeline: APPROVE flow, REJECT flow, refinement failure
"""
import json
from unittest.mock import patch

import pytest

from models.prompt import Prompt
from models.story import Story


class TestSourceListRoute:
    """Tests for POST /api/pipeline/source-list."""

    @patch("routes.pipeline.call_grok")
    def test_source_list_success(self, mock_grok, client, db_session, auth_headers):
        """Valid source-list prompt returns story with output."""
        mock_grok.return_value = "Topic 1: Illinois budget...\nTopic 2: Chicago transit..."

        prompt = Prompt(
            prompt_type="source-list", name="IL Test",
            prompt_text="Find stories...", opportunity="IL News",
            state="Illinois", is_active=True,
        )
        db_session.add(prompt)
        db_session.flush()

        headers = auth_headers("runner@plmediaagency.com", "user")
        resp = client.post(
            "/api/pipeline/source-list",
            data=json.dumps({"prompt_id": prompt.id}),
            content_type="application/json",
            headers=headers,
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert "story_id" in data
        assert "Illinois budget" in data["source_list_output"]

    def test_source_list_wrong_type(self, client, db_session, auth_headers):
        """Non-source-list prompt returns 400."""
        prompt = Prompt(
            prompt_type="papa", name="PAPA",
            prompt_text="text", is_active=True,
        )
        db_session.add(prompt)
        db_session.flush()

        headers = auth_headers("runner2@plmediaagency.com", "user")
        resp = client.post(
            "/api/pipeline/source-list",
            data=json.dumps({"prompt_id": prompt.id}),
            content_type="application/json",
            headers=headers,
        )
        assert resp.status_code == 400
        assert "not a source-list" in resp.get_json()["error"]


class TestFullPipeline:
    """Tests for POST /api/pipeline/run (full pipeline execution)."""

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
        db_session.flush()

        return story, refinement_prompt, amy_prompt

    @patch("services.pipeline_service.call_grok")
    def test_pipeline_approve(self, mock_grok, client, db_session, auth_headers):
        """Pipeline with APPROVE decision pushes to CMS."""
        story, ref_prompt, _ = self._setup_prompts_and_story(db_session)

        # First call = refinement output, second call = Amy Bot APPROVE
        mock_grok.side_effect = [
            "Headline: Illinois budget...\nLede: ...\nFactoid 1: ...",
            'DECISION: APPROVE\n"All fields meet editorial standards."',
        ]

        headers = auth_headers("pipeline@plmediaagency.com", "user")
        resp = client.post(
            "/api/pipeline/run",
            data=json.dumps({
                "story_id": story.id,
                "selected_story": "Illinois governor signs budget bill",
                "refinement_prompt_id": ref_prompt.id,
            }),
            content_type="application/json",
            headers=headers,
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["validation_decision"] == "APPROVE"
        assert data["is_valid"] is True
        assert data["pushed_to_cms"] is True

    @patch("services.pipeline_service.call_grok")
    def test_pipeline_reject(self, mock_grok, client, db_session, auth_headers):
        """Pipeline with REJECT decision kills the story."""
        story, ref_prompt, _ = self._setup_prompts_and_story(db_session)

        mock_grok.side_effect = [
            "Headline: Bad headline...",
            "DECISION: REJECT — with fixes\nHL-VAGUE: headline needs context",
        ]

        headers = auth_headers("pipeline2@plmediaagency.com", "user")
        resp = client.post(
            "/api/pipeline/run",
            data=json.dumps({
                "story_id": story.id,
                "selected_story": "Some story text",
                "refinement_prompt_id": ref_prompt.id,
            }),
            content_type="application/json",
            headers=headers,
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["validation_decision"] == "REJECT"
        assert data["is_valid"] is False
        assert data["pushed_to_cms"] is False

    @patch("services.pipeline_service.call_grok")
    def test_pipeline_refinement_fails(self, mock_grok, client, db_session, auth_headers):
        """If refinement step fails, no Amy Bot call happens."""
        from services.grok_service import GrokAPIError

        story, ref_prompt, _ = self._setup_prompts_and_story(db_session)
        mock_grok.side_effect = GrokAPIError("API timeout", status_code=408)

        headers = auth_headers("pipeline3@plmediaagency.com", "user")
        resp = client.post(
            "/api/pipeline/run",
            data=json.dumps({
                "story_id": story.id,
                "selected_story": "Story text",
                "refinement_prompt_id": ref_prompt.id,
            }),
            content_type="application/json",
            headers=headers,
        )
        assert resp.status_code == 408
        # Grok was only called once (refinement failed, Amy Bot never called)
        assert mock_grok.call_count == 1
