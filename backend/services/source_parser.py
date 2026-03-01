"""
Source parser — Python port of frontend/src/utils/sourceParser.jsx parseSources().

Parses Grok source list output into individual sources. Handles 3 formats:
  - Format A: **List X: ...** headers with URLs underneath
  - Format B: ### Topic N: headers with numbered posts
  - Format C: Fallback blank-line-separated blocks

Returns list of dicts with 'label' and 'body' keys — one entry per source.
"""
import re


def parse_sources(text):
    """Parse Grok source list output into individual sources.

    Args:
        text: Raw Grok output text.

    Returns:
        list[dict]: Each dict has 'label' (str) and 'body' (str).
    """
    if not text:
        return []

    items = []

    # --- Format A: **List X: ...** headers with URLs underneath ---
    if re.search(r'\*\*List\s+[A-Z]', text):
        sections = re.split(r'\n(?=\*\*List\s+[A-Z])', text)
        for section in sections:
            s = section.strip()
            if not s:
                continue
            header_match = re.match(r'^\*\*(.+?)\*\*\s*\n?([\s\S]*)$', s)
            if not header_match:
                continue
            group_title = header_match.group(1).strip()
            body = header_match.group(2).strip()
            lines = [l.strip() for l in body.split('\n') if l.strip()]
            for line in lines:
                items.append({
                    'label': f'{group_title}: {line[:80]}',
                    'body': line,
                })
        if items:
            return items

    # --- Format B: ### or #### topic headers with numbered posts ---
    if re.search(r'#{3,4}\s+(?:Topic\s+)?\d', text):
        sections = re.split(r'\n(?=#{3,4}\s+(?:Topic\s+)?\d)', text)
        for section in sections:
            trimmed = section.strip()
            if not trimmed:
                continue
            header_match = re.match(
                r'^#{3,4}\s+(?:Topic\s+)?(\d+)[.:]\s*(.+?)\s*\n([\s\S]*)$',
                trimmed,
            )
            if not header_match:
                continue
            topic_num = header_match.group(1)
            topic_title = re.sub(r'^\*+|\*+$', '', header_match.group(2)).strip()
            topic_body = header_match.group(3)

            post_parts = re.split(r'\n(?=\s*\d+\.\s+\*\*)', topic_body)
            found_posts = False

            for part in post_parts:
                p = part.strip()
                if not p or not re.match(r'^\d+\.\s+\*\*', p):
                    continue
                found_posts = True

                author_match = re.search(r'\*\*Author\*\*:\s*(.+?)(?:\n|$)', p)
                author = author_match.group(1).strip() if author_match else ''

                content_match = re.search(
                    r'\*\*Post(?:\s+Content)?\*\*:\s*["\u201C\u201D]?([\s\S]*?)["\u201C\u201D]?\s*(?:\*\*Link\*\*:|\*\*Engagement\*\*:|$)',
                    p,
                )
                content = ''
                if content_match:
                    content = re.sub(r'["\u201C\u201D]', '', content_match.group(1)).strip()

                if author:
                    label = f'{topic_title} \u2014 {author}'
                    if content:
                        label += f': {content[:80]}...'
                else:
                    label = f'{topic_title} \u2014 Post'

                items.append({'label': label, 'body': p})

            if not found_posts:
                cleaned_body = re.sub(r'^---\s*\n?', '', topic_body).strip()
                items.append({
                    'label': f'{topic_num}. {topic_title}',
                    'body': cleaned_body,
                })

        if items:
            return items

    # --- Format C: Fallback — split on blank-line-separated blocks ---
    blocks = [b.strip() for b in re.split(r'\n\s*\n', text) if b.strip()]
    if len(blocks) > 1:
        for block in blocks:
            has_url = bool(re.search(r'https?://', block))
            has_handle = bool(re.search(r'@\w+', block))
            has_tweet_indicator = bool(
                re.search(r'\b(Author|Tweet|Content|Post \d):', block, re.IGNORECASE)
            )

            if not has_url and not has_handle and not has_tweet_indicator:
                continue

            # Exclusion patterns
            if re.match(r'^\*\*Search Parameters\*\*', block, re.IGNORECASE):
                continue
            if re.match(r'^\*\*Context\*\*', block, re.IGNORECASE):
                continue
            if re.match(r'^\*\*Localization Note\*\*', block, re.IGNORECASE):
                continue
            if re.match(r'^#{1,4}\s+.*Search Results', block, re.IGNORECASE):
                continue

            label = block[:100] + ('...' if len(block) > 100 else '')
            items.append({'label': label, 'body': block})

    return items
