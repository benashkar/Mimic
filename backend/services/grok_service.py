"""
Grok API service — calls xAI's chat completions and responses endpoints.

Two calling modes:
  - call_grok(): Standard chat completions (refinement, Amy Bot)
  - call_grok_with_search(): Responses API with live X search (source list)

Wraps the xAI Grok API with error handling for:
  - Missing API key
  - HTTP errors (rate limits, server errors)
  - Timeouts
  - Malformed responses

Returns the assistant's message content as a string.
"""
import logging
import time
from datetime import datetime, timedelta, timezone

import requests
from flask import current_app

logger = logging.getLogger(__name__)

RESPONSES_API_URL = "https://api.x.ai/v1/responses"


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
    model = current_app.config.get("GROK_MODEL") or "grok-3-fast"
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


def call_grok_with_search(prompt_text, context=""):
    """
    Send a prompt to the xAI Responses API with live X search enabled.

    Uses the Responses API (not chat completions) with the x_search tool
    so Grok searches real, live X/Twitter data instead of hallucinating.

    Args:
        prompt_text: The user-facing prompt to send to Grok.
        context: Optional system-level context (routing metadata, etc.).

    Returns:
        str: The assistant's response text.

    Raises:
        GrokAPIError: On missing key, HTTP error, timeout, or bad response.
    """
    api_key = current_app.config.get("GROK_API_KEY") or ""
    timeout = current_app.config.get("GROK_TIMEOUT_SECONDS") or 60

    if not api_key:
        raise GrokAPIError("GROK_API_KEY is not configured")

    # Build input array — system context + user prompt
    input_messages = []
    if context:
        input_messages.append({"role": "system", "content": context})
    input_messages.append({"role": "user", "content": prompt_text})

    # Date range: last 7 days to cover "24-48 hours or up to 7 days"
    today = datetime.now(timezone.utc)
    from_date = (today - timedelta(days=7)).strftime("%Y-%m-%d")
    to_date = today.strftime("%Y-%m-%d")

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    payload = {
        "model": "grok-3-fast",
        "input": input_messages,
        "tools": [
            {
                "type": "x_search",
                "from_date": from_date,
                "to_date": to_date,
            }
        ],
        "temperature": 0.7,
    }

    start_ms = int(time.time() * 1000)

    try:
        resp = requests.post(
            RESPONSES_API_URL,
            json=payload,
            headers=headers,
            timeout=timeout,
        )
    except requests.Timeout:
        logger.error("[ERR] Grok Responses API timeout after %ds", timeout)
        raise GrokAPIError("Grok API request timed out", status_code=408)
    except requests.ConnectionError:
        logger.error("[ERR] Grok Responses API connection failed")
        raise GrokAPIError("Could not connect to Grok API", status_code=503)

    duration_ms = int(time.time() * 1000) - start_ms

    if resp.status_code == 429:
        logger.error("[ERR] Grok Responses API rate limited")
        raise GrokAPIError("Grok API rate limit exceeded", status_code=429)

    if resp.status_code != 200:
        logger.error(
            "[ERR] Grok Responses API HTTP %d: %s", resp.status_code, resp.text[:500]
        )
        raise GrokAPIError(
            f"Grok API returned HTTP {resp.status_code}",
            status_code=resp.status_code,
        )

    # Parse Responses API output — find the assistant's text output
    try:
        data = resp.json()
        output_items = data.get("output") or []
        text_parts = []
        for item in output_items:
            if item.get("type") == "message":
                for content_block in item.get("content") or []:
                    if content_block.get("type") == "output_text":
                        text_parts.append(content_block.get("text") or "")
        content = "\n".join(text_parts)
        if not content:
            raise ValueError("No text output in response")
    except (KeyError, ValueError) as exc:
        logger.error("[ERR] Grok Responses API malformed response: %s", exc)
        raise GrokAPIError("Malformed response from Grok Responses API")

    logger.info(
        "[OK] Grok Responses API call completed in %dms (with x_search)", duration_ms
    )
    return content
