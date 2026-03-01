"""
Tests for routes/scheduler.py — cron endpoint authentication and execution.

Covers: missing secret, wrong secret, correct secret, success response.
"""
from unittest.mock import patch


class TestSchedulerAuth:
    """Tests for POST /api/scheduler/run authentication."""

    def test_missing_secret_returns_401(self, client, app):
        """Request without X-Scheduler-Secret header returns 401."""
        app.config["SCHEDULER_SECRET"] = "test-secret-123"
        resp = client.post("/api/scheduler/run")
        assert resp.status_code == 401
        assert "Unauthorized" in resp.get_json()["error"]

    def test_wrong_secret_returns_401(self, client, app):
        """Request with incorrect secret returns 401."""
        app.config["SCHEDULER_SECRET"] = "test-secret-123"
        resp = client.post(
            "/api/scheduler/run",
            headers={"X-Scheduler-Secret": "wrong-secret"},
        )
        assert resp.status_code == 401

    def test_empty_config_secret_returns_401(self, client, app):
        """If SCHEDULER_SECRET is empty, all requests are rejected."""
        app.config["SCHEDULER_SECRET"] = ""
        resp = client.post(
            "/api/scheduler/run",
            headers={"X-Scheduler-Secret": "anything"},
        )
        assert resp.status_code == 401

    @patch("routes.scheduler.run_scheduled_source_lists")
    def test_correct_secret_returns_200(self, mock_run, client, app):
        """Request with correct secret calls the scheduler and returns results."""
        app.config["SCHEDULER_SECRET"] = "test-secret-123"
        mock_run.return_value = {
            "prompts_run": 3,
            "items_created": 15,
            "errors": [],
        }

        resp = client.post(
            "/api/scheduler/run",
            headers={"X-Scheduler-Secret": "test-secret-123"},
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["prompts_run"] == 3
        assert data["items_created"] == 15
        assert data["errors"] == []
        mock_run.assert_called_once()

    @patch("routes.scheduler.run_scheduled_source_lists")
    def test_returns_errors_from_scheduler(self, mock_run, client, app):
        """Errors from individual prompt runs are included in the response."""
        app.config["SCHEDULER_SECRET"] = "test-secret-123"
        mock_run.return_value = {
            "prompts_run": 1,
            "items_created": 5,
            "errors": ["Prompt 42 (Michigan SL): Grok API timeout"],
        }

        resp = client.post(
            "/api/scheduler/run",
            headers={"X-Scheduler-Secret": "test-secret-123"},
        )
        data = resp.get_json()
        assert len(data["errors"]) == 1
        assert "Prompt 42" in data["errors"][0]
