"""
Tests for services/grok_service.py.

All tests mock the requests.post call — no real API calls are made.
Covers: success, timeout, rate limit, missing key, malformed response.
"""
from unittest.mock import patch, MagicMock

import pytest

from services.grok_service import call_grok, GrokAPIError


def _mock_response(status_code=200, json_data=None, text=""):
    """Create a mock requests.Response."""
    mock = MagicMock()
    mock.status_code = status_code
    mock.json.return_value = json_data or {}
    mock.text = text
    return mock


class TestCallGrok:
    """Tests for call_grok function."""

    @patch("services.grok_service.requests.post")
    def test_success(self, mock_post, app):
        """Valid API call returns assistant content."""
        mock_post.return_value = _mock_response(200, {
            "choices": [{"message": {"content": "Here are the results..."}}]
        })
        with app.app_context():
            result = call_grok("Find stories about Illinois")
            assert result == "Here are the results..."
            mock_post.assert_called_once()

    @patch("services.grok_service.requests.post")
    def test_with_context(self, mock_post, app):
        """System context is included in messages when provided."""
        mock_post.return_value = _mock_response(200, {
            "choices": [{"message": {"content": "Response"}}]
        })
        with app.app_context():
            call_grok("prompt", context="You are a news assistant")
            payload = mock_post.call_args[1]["json"]
            assert len(payload["messages"]) == 2
            assert payload["messages"][0]["role"] == "system"

    @patch("services.grok_service.requests.post")
    def test_timeout(self, mock_post, app):
        """Timeout raises GrokAPIError with 408 status."""
        import requests as req
        mock_post.side_effect = req.Timeout()
        with app.app_context():
            with pytest.raises(GrokAPIError, match="timed out"):
                call_grok("prompt")

    @patch("services.grok_service.requests.post")
    def test_rate_limit(self, mock_post, app):
        """429 response raises GrokAPIError."""
        mock_post.return_value = _mock_response(429, text="rate limited")
        with app.app_context():
            with pytest.raises(GrokAPIError, match="rate limit"):
                call_grok("prompt")

    @patch("services.grok_service.requests.post")
    def test_server_error(self, mock_post, app):
        """500 response raises GrokAPIError."""
        mock_post.return_value = _mock_response(500, text="internal error")
        with app.app_context():
            with pytest.raises(GrokAPIError, match="HTTP 500"):
                call_grok("prompt")

    def test_missing_api_key(self, app):
        """Missing GROK_API_KEY raises GrokAPIError."""
        with app.app_context():
            app.config["GROK_API_KEY"] = ""
            with pytest.raises(GrokAPIError, match="not configured"):
                call_grok("prompt")
            app.config["GROK_API_KEY"] = "test-grok-key"

    @patch("services.grok_service.requests.post")
    def test_malformed_response(self, mock_post, app):
        """Response missing choices key raises GrokAPIError."""
        mock_post.return_value = _mock_response(200, {"bad": "data"})
        with app.app_context():
            with pytest.raises(GrokAPIError, match="Malformed"):
                call_grok("prompt")
