"""
Tests for services/source_parser.py — Python port parity with JS parseSources().

Covers: all 3 formats (List A/B headers, topic headers, fallback blocks),
        empty input, no-URL blocks, exclusion patterns.
"""
from services.source_parser import parse_sources


class TestEmptyInput:
    """Edge cases: None, empty string, whitespace."""

    def test_none_returns_empty(self):
        assert parse_sources(None) == []

    def test_empty_string_returns_empty(self):
        assert parse_sources("") == []

    def test_whitespace_returns_empty(self):
        assert parse_sources("   \n\n  ") == []


class TestFormatA:
    """Format A: **List X: ...** headers with URLs underneath."""

    def test_basic_list_format(self):
        text = """**List A: National Coverage**
https://x.com/user1/status/111 - Breaking news about policy
https://x.com/user2/status/222 - Local impact story

**List B: Regional Coverage**
https://x.com/user3/status/333 - State legislature update"""

        items = parse_sources(text)
        assert len(items) == 3
        assert "List A: National Coverage" in items[0]["label"]
        assert "https://x.com/user1/status/111" in items[0]["body"]
        assert "List B: Regional Coverage" in items[2]["label"]

    def test_single_list_section(self):
        text = """**List A: Sources**
https://x.com/reporter/status/456 - Tweet about healthcare"""

        items = parse_sources(text)
        assert len(items) == 1
        assert "List A: Sources" in items[0]["label"]

    def test_label_truncated_at_80_chars(self):
        long_line = "https://x.com/user/status/123 - " + "A" * 100
        text = f"**List A: Test**\n{long_line}"

        items = parse_sources(text)
        assert len(items) == 1
        # Label should be group_title + ": " + first 80 chars of line
        assert len(items[0]["label"]) <= len("List A: Test: ") + 80


class TestFormatB:
    """Format B: ### Topic N: headers with numbered posts."""

    def test_topic_with_numbered_posts(self):
        text = """### Topic 1: Healthcare Policy
1. **Post by @reporter1**
**Author**: @reporter1
**Post Content**: "New healthcare bill introduced today"
**Link**: https://x.com/reporter1/status/111

2. **Post by @reporter2**
**Author**: @reporter2
**Post Content**: "Analysis of healthcare spending"
**Link**: https://x.com/reporter2/status/222

### Topic 2: Education
1. **Post by @teacher**
**Author**: @teacher
**Post Content**: "School funding update"
**Link**: https://x.com/teacher/status/333"""

        items = parse_sources(text)
        assert len(items) == 3
        assert "Healthcare Policy" in items[0]["label"]
        assert "@reporter1" in items[0]["label"]
        assert "Education" in items[2]["label"]

    def test_topic_without_posts_falls_back(self):
        text = """### Topic 1: General News
Some content without numbered posts here.
Just general text about the topic.

### Topic 2: Sports Update
More general content without post formatting."""

        items = parse_sources(text)
        assert len(items) == 2
        assert "1. General News" in items[0]["label"]
        assert "2. Sports Update" in items[1]["label"]

    def test_four_hash_headers(self):
        text = """#### Topic 1: Breaking News
1. **Post by @journalist**
**Author**: @journalist
**Post Content**: "Major development in downtown area"
**Link**: https://x.com/journalist/status/999"""

        items = parse_sources(text)
        assert len(items) == 1
        assert "Breaking News" in items[0]["label"]

    def test_topic_title_strips_asterisks(self):
        text = """### Topic 1: **Bold Title**
1. **Post by @user**
**Author**: @user
**Post Content**: "Content here"
**Link**: https://x.com/user/status/123"""

        items = parse_sources(text)
        assert len(items) == 1
        assert "Bold Title" in items[0]["label"]
        assert "**" not in items[0]["label"].split(" \u2014 ")[0]


class TestFormatC:
    """Format C: Fallback blank-line-separated blocks."""

    def test_blocks_with_urls(self):
        text = """First source block about something.
Author: @reporter1
https://x.com/reporter1/status/111

Second source block about something else.
Author: @reporter2
https://x.com/reporter2/status/222

Third block without any links or handles.
Just plain text that should be excluded."""

        items = parse_sources(text)
        assert len(items) == 2  # Third block excluded (no URL/handle)

    def test_blocks_with_handles_only(self):
        text = """Tweet by @user1 about local politics.
Content about city council meeting.

Response from @user2 regarding the budget.
Discussion about funding allocation."""

        items = parse_sources(text)
        assert len(items) == 2

    def test_blocks_with_tweet_indicators(self):
        text = """Post 1: Breaking news about the election.
Content: Details about vote counting.

Post 2: Follow-up on the results.
Tweet: Official statement released."""

        items = parse_sources(text)
        assert len(items) == 2

    def test_excludes_search_parameters(self):
        text = """**Search Parameters**
Query: healthcare michigan
Date range: last 7 days

Source about healthcare from @reporter
https://x.com/reporter/status/123"""

        items = parse_sources(text)
        assert len(items) == 1
        assert "Search Parameters" not in items[0]["body"]

    def test_excludes_context_block(self):
        text = """**Context**
This search was performed for Michigan healthcare opportunities.

Actual source content here @reporter
https://x.com/reporter/status/456"""

        items = parse_sources(text)
        assert len(items) == 1
        assert "Context" not in items[0]["body"]

    def test_excludes_localization_note(self):
        text = """**Localization Note**
Results filtered for Michigan region.

Real source content @journalist
https://x.com/journalist/status/789"""

        items = parse_sources(text)
        assert len(items) == 1

    def test_excludes_search_results_header(self):
        text = """## Search Results
Overview of findings.

Actual tweet by @user1
https://x.com/user1/status/100"""

        items = parse_sources(text)
        assert len(items) == 1

    def test_label_truncated_at_100_chars(self):
        long_block = "A" * 150 + " https://example.com"
        text = f"{long_block}\n\nAnother block @user\nhttps://example.com/2"

        items = parse_sources(text)
        for item in items:
            assert len(item["label"]) <= 103  # 100 + "..."

    def test_single_block_returns_empty(self):
        """Single block (no blank-line separation) returns empty."""
        text = "Just one block of text with https://example.com"
        items = parse_sources(text)
        assert items == []


class TestFormatPriority:
    """Format A is tried first, then B, then C."""

    def test_format_a_takes_priority(self):
        """When text matches Format A, Format B/C are not used."""
        text = """**List A: Sources**
https://x.com/user/status/111

**List B: More Sources**
https://x.com/user/status/222"""

        items = parse_sources(text)
        # Format A matched — all items parsed as List headers, not topic/fallback
        assert len(items) == 2
        assert "List A" in items[0]["label"]
        assert "List B" in items[1]["label"]
