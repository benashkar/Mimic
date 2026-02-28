"""
URL enrichment service — fetch context for bare URLs in Grok source list output.

For Twitter/X URLs: calls public oEmbed API to get author + tweet text.
For other URLs: fetches page HTML, extracts <title> + first 500 chars visible text.

Each URL has a 10-second timeout and its own try/except so one failure
never blocks the rest.
"""
import json
import logging
import re

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

URL_TIMEOUT = 10  # seconds per URL fetch

# Browser-like User-Agent so news sites don't 403 us
_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/131.0.0.0 Safari/537.36"
)


def extract_urls(text):
    """Extract unique HTTP/HTTPS URLs from text.

    Strips trailing punctuation (periods, commas, parentheses) that often
    gets attached when URLs appear in prose.
    """
    if not text:
        return []
    raw = re.findall(r'https?://[^\s<>"\']+', text)
    cleaned = []
    seen = set()
    for url in raw:
        url = url.rstrip(".,;:!?)>]}")
        if url not in seen:
            seen.add(url)
            cleaned.append(url)
    return cleaned


def is_twitter_url(url):
    """Detect x.com or twitter.com status URLs."""
    return bool(re.match(
        r'https?://(?:www\.)?(?:x|twitter)\.com/\w+/status/\d+',
        url,
    ))


def _parse_twitter_id_and_user(url):
    """Extract username and status ID from a Twitter/X URL."""
    m = re.match(
        r'https?://(?:www\.)?(?:x|twitter)\.com/(\w+)/status/(\d+)',
        url,
    )
    if m:
        return m.group(1), m.group(2)
    return None, None


def enrich_twitter_url(url):
    """Fetch tweet context. Tries FxTwitter first (has date), falls back to oEmbed.

    Returns dict with author_name, text, created_at, and url,
    or None on failure.
    """
    # --- Attempt 1: FxTwitter API (has date, preferred) ---
    username, status_id = _parse_twitter_id_and_user(url)
    if username and status_id:
        try:
            fx_url = f"https://api.fxtwitter.com/{username}/status/{status_id}"
            resp = requests.get(fx_url, timeout=URL_TIMEOUT)
            if resp.status_code == 200:
                data = resp.json()
                tweet = data.get("tweet") or {}
                author = tweet.get("author") or {}

                return {
                    "type": "twitter",
                    "author_name": author.get("name") or username,
                    "text": tweet.get("text") or "",
                    "created_at": tweet.get("created_at") or "",
                    "url": url,
                }
            logger.info("[--] FxTwitter %d for %s, trying oEmbed", resp.status_code, url)
        except requests.RequestException as exc:
            logger.info("[--] FxTwitter error for %s: %s, trying oEmbed", url, exc)

    # --- Attempt 2: Twitter oEmbed (no date, fallback) ---
    oembed_url = "https://publish.twitter.com/oembed"
    try:
        resp = requests.get(
            oembed_url,
            params={"url": url, "omit_script": "true"},
            timeout=URL_TIMEOUT,
        )
        if resp.status_code == 200:
            data = resp.json()
            html = data.get("html") or ""
            soup = BeautifulSoup(html, "html.parser")
            tweet_text = soup.get_text(separator=" ").strip()

            return {
                "type": "twitter",
                "author_name": data.get("author_name") or "",
                "text": tweet_text,
                "created_at": "",
                "url": url,
            }
        logger.info("[--] Twitter oEmbed %d for %s", resp.status_code, url)
    except requests.RequestException as exc:
        logger.info("[--] Twitter oEmbed error for %s: %s", url, exc)

    return None


def enrich_website_url(url):
    """Fetch page title + first 500 chars of visible body text.

    Strips scripts, styles, nav, header, and footer elements before
    extracting text.
    """
    try:
        resp = requests.get(
            url,
            timeout=URL_TIMEOUT,
            headers={"User-Agent": _USER_AGENT},
        )
        if resp.status_code != 200:
            logger.info("[--] Website fetch %d for %s", resp.status_code, url)
            return None

        soup = BeautifulSoup(resp.text, "html.parser")

        # Extract title
        title_tag = soup.find("title")
        title = title_tag.get_text(strip=True) if title_tag else ""

        # Remove noise elements
        for tag in soup.find_all(["script", "style", "nav", "header", "footer", "noscript"]):
            tag.decompose()

        body_text = soup.get_text(separator=" ", strip=True)
        # Collapse whitespace
        body_text = re.sub(r'\s+', ' ', body_text).strip()
        preview = body_text[:500]

        return {
            "type": "website",
            "title": title,
            "text": preview,
            "url": url,
        }
    except requests.RequestException as exc:
        logger.info("[--] Website fetch error for %s: %s", url, exc)
        return None


def enrich_urls(text):
    """Extract URLs from text, enrich each, return JSON string keyed by URL.

    Returns None if no URLs found or all enrichments failed.
    """
    urls = extract_urls(text)
    if not urls:
        return None

    results = {}
    for url in urls:
        try:
            if is_twitter_url(url):
                enrichment = enrich_twitter_url(url)
            else:
                enrichment = enrich_website_url(url)

            if enrichment:
                results[url] = enrichment
                logger.info("[OK] Enriched URL: %s", url)
            else:
                logger.info("[--] No enrichment for URL: %s", url)
        except Exception as exc:
            logger.warning("[--] Enrichment error for %s: %s", url, exc)

    if not results:
        return None

    return json.dumps(results)
