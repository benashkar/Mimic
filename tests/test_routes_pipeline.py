"""
Tests for routes/pipeline.py — Source List, Pipeline Run, and Status endpoints.

Covers: async background execution, placeholder run creation, status polling,
input validation, error handling in background threads.
"""
from unittest.mock import patch, MagicMock

from models import db
from models.prompt import Prompt
from models.story import Story
from models.pipeline_run import PipelineRun


class TestSourceListRoute:
    """Tests for POST /api/pipeline/source-list."""

    def test_missing_prompt_id(self, client, auth_headers):
        """POST without prompt_id returns 400."""
        headers = auth_headers(role="admin")
        resp = client.post("/api/pipeline/source-list", json={}, headers=headers)
        assert resp.status_code == 400
        assert "prompt_id" in resp.get_json()["error"]

    def test_prompt_not_found(self, client, auth_headers):
        """POST with nonexistent prompt_id returns 404."""
        headers = auth_headers(role="admin")
        resp = client.post(
            "/api/pipeline/source-list",
            json={"prompt_id": 9999},
            headers=headers,
        )
        assert resp.status_code == 404

    def test_wrong_prompt_type(self, client, auth_headers, db_session):
        """POST with non-source-list prompt returns 400."""
        headers = auth_headers(role="admin")
        prompt = Prompt(
            prompt_type="papa", name="PAPA", prompt_text="test", created_by="test"
        )
        db_session.add(prompt)
        db_session.flush()

        resp = client.post(
            "/api/pipeline/source-list",
            json={"prompt_id": prompt.id},
            headers=headers,
        )
        assert resp.status_code == 400
        assert "source-list" in resp.get_json()["error"]

    @patch("routes.pipeline.threading.Thread")
    def test_success_returns_202(self, mock_thread, client, auth_headers, db_session):
        """Valid source-list prompt creates story + pipeline_run, returns 202."""
        headers = auth_headers(role="admin")
        prompt = Prompt(
            prompt_type="source-list",
            name="Test SL",
            prompt_text="Find stories",
            opportunity="TestOpp",
            state="IL",
            created_by="test",
        )
        db_session.add(prompt)
        db_session.flush()

        mock_thread.return_value = MagicMock()

        resp = client.post(
            "/api/pipeline/source-list",
            json={"prompt_id": prompt.id},
            headers=headers,
        )
        assert resp.status_code == 202
        data = resp.get_json()
        assert "story_id" in data
        assert data["status"] == "running"

        # Verify story and pipeline_run were created
        story = db_session.get(Story, data["story_id"])
        assert story is not None
        assert story.opportunity == "TestOpp"
        assert story.state == "IL"

        run = PipelineRun.query.filter_by(story_id=story.id).first()
        assert run is not None
        assert run.step_type == "source-list"
        assert run.status == "running"

    def test_requires_auth(self, client):
        """POST without auth token returns 401."""
        resp = client.post("/api/pipeline/source-list", json={"prompt_id": 1})
        assert resp.status_code == 401


class TestPipelineRunRoute:
    """Tests for POST /api/pipeline/run."""

    def test_missing_fields(self, client, auth_headers):
        """POST without required fields returns 400."""
        headers = auth_headers(role="admin")
        resp = client.post("/api/pipeline/run", json={}, headers=headers)
        assert resp.status_code == 400

    def test_missing_selected_story(self, client, auth_headers):
        """POST without selected_story returns 400."""
        headers = auth_headers(role="admin")
        resp = client.post(
            "/api/pipeline/run",
            json={"story_id": 1, "refinement_prompt_id": 1},
            headers=headers,
        )
        assert resp.status_code == 400

    def test_story_not_found(self, client, auth_headers):
        """POST with nonexistent story returns 404."""
        headers = auth_headers(role="admin")
        resp = client.post(
            "/api/pipeline/run",
            json={
                "story_id": 9999,
                "selected_story": "test",
                "refinement_prompt_id": 1,
            },
            headers=headers,
        )
        assert resp.status_code == 404

    @patch("routes.pipeline.threading.Thread")
    def test_creates_placeholder_run(self, mock_thread, client, auth_headers, db_session):
        """POST creates placeholder refinement run before starting thread."""
        headers = auth_headers(role="admin")
        prompt = Prompt(
            prompt_type="source-list", name="SL", prompt_text="t", created_by="t"
        )
        db_session.add(prompt)
        db_session.flush()

        story = Story(source_list_prompt_id=prompt.id, created_by="test")
        db_session.add(story)
        db_session.flush()

        mock_thread.return_value = MagicMock()

        resp = client.post(
            "/api/pipeline/run",
            json={
                "story_id": story.id,
                "selected_story": "Some tweet content",
                "refinement_prompt_id": prompt.id,
            },
            headers=headers,
        )
        assert resp.status_code == 202

        # Verify placeholder run exists
        placeholder = PipelineRun.query.filter_by(
            story_id=story.id, step_type="refinement", status="running"
        ).first()
        assert placeholder is not None
        assert placeholder.input_text == "(pipeline starting...)"

    def test_requires_auth(self, client):
        """POST without auth returns 401."""
        resp = client.post(
            "/api/pipeline/run",
            json={"story_id": 1, "selected_story": "x", "refinement_prompt_id": 1},
        )
        assert resp.status_code == 401


class TestStatusEndpoint:
    """Tests for GET /api/pipeline/status/<story_id>."""

    def test_not_found(self, client, auth_headers):
        """GET with nonexistent story returns 404."""
        headers = auth_headers(role="user")
        resp = client.get("/api/pipeline/status/9999", headers=headers)
        assert resp.status_code == 404

    def test_running_status(self, client, auth_headers, db_session):
        """Status shows 'running' when any pipeline_run is running."""
        headers = auth_headers(role="user")
        story = Story(created_by="test")
        db_session.add(story)
        db_session.flush()

        run = PipelineRun(
            story_id=story.id, step_type="refinement", status="running"
        )
        db_session.add(run)
        db_session.flush()

        resp = client.get(f"/api/pipeline/status/{story.id}", headers=headers)
        assert resp.status_code == 200
        assert resp.get_json()["status"] == "running"

    def test_failed_status(self, client, auth_headers, db_session):
        """Status shows 'failed' when any run has failed."""
        headers = auth_headers(role="user")
        story = Story(created_by="test")
        db_session.add(story)
        db_session.flush()

        run = PipelineRun(
            story_id=story.id,
            step_type="source-list",
            status="failed",
            error_message="API timeout",
        )
        db_session.add(run)
        db_session.flush()

        resp = client.get(f"/api/pipeline/status/{story.id}", headers=headers)
        data = resp.get_json()
        assert data["status"] == "failed"
        assert data["runs"][0]["error_message"] == "API timeout"

    def test_completed_with_approval(self, client, auth_headers, db_session):
        """Status includes validation_decision and is_valid for completed stories."""
        headers = auth_headers(role="user")
        story = Story(
            created_by="test",
            validation_decision="APPROVE",
            is_valid=True,
            pushed_to_cms=True,
        )
        db_session.add(story)
        db_session.flush()

        run = PipelineRun(
            story_id=story.id, step_type="amy-bot", status="completed"
        )
        db_session.add(run)
        db_session.flush()

        resp = client.get(f"/api/pipeline/status/{story.id}", headers=headers)
        data = resp.get_json()
        assert data["status"] == "completed"
        assert data["validation_decision"] == "APPROVE"
        assert data["is_valid"] is True
        assert data["pushed_to_cms"] is True

    def test_requires_auth(self, client):
        """GET without auth returns 401."""
        resp = client.get("/api/pipeline/status/1")
        assert resp.status_code == 401

    def test_returns_runs_in_order(self, client, auth_headers, db_session):
        """Status endpoint returns pipeline runs ordered by ID."""
        headers = auth_headers(role="user")
        story = Story(created_by="test")
        db_session.add(story)
        db_session.flush()

        for step in ["source-list", "refinement", "amy-bot"]:
            run = PipelineRun(
                story_id=story.id, step_type=step, status="completed"
            )
            db_session.add(run)
        db_session.flush()

        resp = client.get(f"/api/pipeline/status/{story.id}", headers=headers)
        runs = resp.get_json()["runs"]
        assert len(runs) == 3
        assert runs[0]["step_type"] == "source-list"
        assert runs[1]["step_type"] == "refinement"
        assert runs[2]["step_type"] == "amy-bot"
