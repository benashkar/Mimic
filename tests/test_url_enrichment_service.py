"""
Tests for services/url_enrichment_service.py — URL extraction, Twitter oEmbed,
website scraping, and batch enrichment.
"""
import json
from unittest.mock import patch, MagicMock

import pytest

from services.url_enrichment_service import (
    extract_urls,
    is_twitter_url,
    enrich_twitter_url,
    enrich_website_url,
    enrich_urls,
)


class TestExtractUrls:
    """Tests for extract_urls()."""

    def test_extracts_http_and_https(self):
        text = "Check http://example.com and https://other.com/page"
        urls = extract_urls(text)
        assert urls == ["http://example.com", "https://other.com/page"]

    def test_deduplicates(self):
        text = "Visit https://example.com and again https://example.com"
        urls = extract_urls(text)
        assert urls == ["https://example.com"]

    def test_strips_trailing_punctuation(self):
        text = "See https://example.com. Also https://other.com, and (https://third.com)"
        urls = extract_urls(text)
        assert "https://example.com" in urls
        assert "https://other.com" in urls
        assert "https://third.com" in urls

    def test_empty_text(self):
        assert extract_urls("") == []
        assert extract_urls(None) == []

    def test_no_urls(self):
        assert extract_urls("No links here, just plain text.") == []

    def test_preserves_query_params(self):
        text = "Link: https://example.com/page?foo=bar&baz=1"
        urls = extract_urls(text)
        assert urls == ["https://example.com/page?foo=bar&baz=1"]


class TestIsTwitterUrl:
    """Tests for is_twitter_url()."""

    def test_x_com_status(self):
        assert is_twitter_url("https://x.com/user123/status/123456789")

    def test_twitter_com_status(self):
        assert is_twitter_url("https://twitter.com/someuser/status/99999")

    def test_www_prefix(self):
        assert is_twitter_url("https://www.x.com/user/status/111")
        assert is_twitter_url("https://www.twitter.com/user/status/222")

    def test_non_status_url(self):
        assert not is_twitter_url("https://x.com/user")
        assert not is_twitter_url("https://twitter.com/settings")

    def test_other_domain(self):
        assert not is_twitter_url("https://example.com/status/123")

    def test_http_scheme(self):
        assert is_twitter_url("http://x.com/user/status/123")


class TestEnrichTwitterUrl:
    """Tests for enrich_twitter_url()."""

    @patch("services.url_enrichment_service.requests.get")
    def test_success_fxtwitter(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "tweet": {
                "text": "This is a tweet about basketball",
                "created_at": "2026-02-15T12:00:00Z",
                "author": {"name": "John Doe"},
            }
        }
        mock_get.return_value = mock_resp

        result = enrich_twitter_url("https://x.com/johndoe/status/123")
        assert result is not None
        assert result["type"] == "twitter"
        assert result["author_name"] == "John Doe"
        assert "basketball" in result["text"]
        assert result["created_at"] == "2026-02-15T12:00:00Z"
        assert result["url"] == "https://x.com/johndoe/status/123"

    @patch("services.url_enrichment_service.requests.get")
    def test_404_returns_none(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 404
        mock_get.return_value = mock_resp

        result = enrich_twitter_url("https://x.com/deleted/status/999")
        assert result is None

    @patch("services.url_enrichment_service.requests.get")
    def test_timeout_returns_none(self, mock_get):
        import requests
        mock_get.side_effect = requests.Timeout("Connection timed out")

        result = enrich_twitter_url("https://x.com/slow/status/111")
        assert result is None


class TestEnrichWebsiteUrl:
    """Tests for enrich_website_url()."""

    @patch("services.url_enrichment_service.requests.get")
    def test_success(self, mock_get):
        html = """
        <html>
        <head><title>Breaking News Article</title></head>
        <body>
            <nav>Menu items</nav>
            <p>This is the main article content about something important.</p>
        </body>
        </html>
        """
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = html
        mock_get.return_value = mock_resp

        result = enrich_website_url("https://news.example.com/article")
        assert result is not None
        assert result["type"] == "website"
        assert result["title"] == "Breaking News Article"
        assert "main article content" in result["text"]
        assert "Menu items" not in result["text"]  # nav stripped
        assert result["url"] == "https://news.example.com/article"

    @patch("services.url_enrichment_service.requests.get")
    def test_truncates_to_500_chars(self, mock_get):
        long_text = "A" * 1000
        html = f"<html><head><title>T</title></head><body><p>{long_text}</p></body></html>"
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = html
        mock_get.return_value = mock_resp

        result = enrich_website_url("https://example.com/long")
        assert result is not None
        assert len(result["text"]) == 500

    @patch("services.url_enrichment_service.requests.get")
    def test_403_returns_none(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 403
        mock_get.return_value = mock_resp

        result = enrich_website_url("https://blocked.example.com")
        assert result is None

    @patch("services.url_enrichment_service.requests.get")
    def test_connection_error_returns_none(self, mock_get):
        import requests
        mock_get.side_effect = requests.ConnectionError("Failed to connect")

        result = enrich_website_url("https://down.example.com")
        assert result is None


class TestEnrichUrls:
    """Tests for the batch enrich_urls() function."""

    @patch("services.url_enrichment_service.enrich_website_url")
    @patch("services.url_enrichment_service.enrich_twitter_url")
    def test_mixed_urls(self, mock_twitter, mock_website):
        mock_twitter.return_value = {
            "type": "twitter",
            "author_name": "User",
            "text": "Tweet text",
            "url": "https://x.com/user/status/123",
        }
        mock_website.return_value = {
            "type": "website",
            "title": "Page",
            "text": "Content",
            "url": "https://example.com/article",
        }

        text = "Sources: https://x.com/user/status/123 and https://example.com/article"
        result = enrich_urls(text)
        assert result is not None

        data = json.loads(result)
        assert "https://x.com/user/status/123" in data
        assert data["https://x.com/user/status/123"]["type"] == "twitter"
        assert "https://example.com/article" in data
        assert data["https://example.com/article"]["type"] == "website"

    def test_no_urls_returns_none(self):
        result = enrich_urls("No URLs in this text at all.")
        assert result is None

    @patch("services.url_enrichment_service.enrich_website_url")
    def test_all_failures_returns_none(self, mock_website):
        mock_website.return_value = None
        result = enrich_urls("Check https://fail.example.com for info")
        assert result is None

    @patch("services.url_enrichment_service.enrich_twitter_url")
    def test_single_failure_does_not_block_others(self, mock_twitter):
        # First call fails, second succeeds
        mock_twitter.side_effect = [
            None,
            {"type": "twitter", "author_name": "B", "text": "OK", "url": "https://x.com/b/status/2"},
        ]
        text = "https://x.com/a/status/1 and https://x.com/b/status/2"
        result = enrich_urls(text)
        assert result is not None
        data = json.loads(result)
        assert "https://x.com/a/status/1" not in data
        assert "https://x.com/b/status/2" in data
