"""
Grok API service — calls xAI's chat completions endpoint.

Wraps the xAI Grok API with error handling for:
  - Missing API key
  - HTTP errors (rate limits, server errors)
  - Timeouts
  - Malformed responses

Returns the assistant's message content as a string.
"""
import logging
import time

import requests
from flask import current_app

logger = logging.getLogger(__name__)


class GrokAPIError(Exception):
    """Raised when the Grok API returns an error or is unreachable."""

    def __init__(self, message, status_code=None):
        super().__init__(message)
        self.status_code = status_code


def call_grok(prompt_text, context=""):
    """
    Send a prompt to the xAI Grok API and return the response text.

    Builds a chat message with an optional system context and the user
    prompt. Uses the model, API URL, and timeout from app config.

    Args:
        prompt_text: The user-facing prompt to send to Grok.
        context: Optional system-level context (routing metadata, etc.).

    Returns:
        str: The assistant's response text.

    Raises:
        GrokAPIError: On missing key, HTTP error, timeout, or bad response.
    """
    api_key = current_app.config.get("GROK_API_KEY") or ""
    api_url = current_app.config.get("GROK_API_URL") or ""
    model = current_app.config.get("GROK_MODEL") or "grok-3"
    timeout = current_app.config.get("GROK_TIMEOUT_SECONDS") or 60

    if not api_key:
        raise GrokAPIError("GROK_API_KEY is not configured")

    # Build messages array — system context is optional
    messages = []
    if context:
        messages.append({"role": "system", "content": context})
    messages.append({"role": "user", "content": prompt_text})

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    payload = {
        "model": model,
        "messages": messages,
        "temperature": 0.7,
    }

    start_ms = int(time.time() * 1000)

    try:
        resp = requests.post(
            api_url,
            json=payload,
            headers=headers,
            timeout=timeout,
        )
    except requests.Timeout:
        logger.error("[ERR] Grok API timeout after %ds", timeout)
        raise GrokAPIError("Grok API request timed out", status_code=408)
    except requests.ConnectionError:
        logger.error("[ERR] Grok API connection failed")
        raise GrokAPIError("Could not connect to Grok API", status_code=503)

    duration_ms = int(time.time() * 1000) - start_ms

    # Handle HTTP errors
    if resp.status_code == 429:
        logger.error("[ERR] Grok API rate limited")
        raise GrokAPIError("Grok API rate limit exceeded", status_code=429)

    if resp.status_code != 200:
        logger.error(
            "[ERR] Grok API HTTP %d: %s", resp.status_code, resp.text[:200]
        )
        raise GrokAPIError(
            f"Grok API returned HTTP {resp.status_code}",
            status_code=resp.status_code,
        )

    # Parse response — extract assistant message content
    try:
        data = resp.json()
        content = data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, ValueError) as exc:
        logger.error("[ERR] Grok API malformed response: %s", exc)
        raise GrokAPIError("Malformed response from Grok API")

    logger.info(
        "[OK] Grok API call completed in %dms (model=%s)", duration_ms, model
    )
    return content
