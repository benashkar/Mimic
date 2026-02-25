"""
Tests for services/validation_service.py — APPROVE/REJECT parsing.

Covers: various APPROVE formats, REJECT formats, garbage input.
"""
from services.validation_service import parse_decision


class TestParseDecision:
    """Tests for parse_decision."""

    def test_approve_standard(self):
        """Standard APPROVE format returns True."""
        assert parse_decision('DECISION: APPROVE\n"All fields meet editorial standards."') is True

    def test_approve_no_space(self):
        """APPROVE without space after colon returns True."""
        assert parse_decision("DECISION:APPROVE") is True

    def test_approve_lowercase(self):
        """Case-insensitive APPROVE returns True."""
        assert parse_decision("decision: approve") is True

    def test_approve_with_extra_text(self):
        """APPROVE buried in longer output returns True."""
        output = "After review:\nDECISION: APPROVE\nAll good."
        assert parse_decision(output) is True

    def test_reject_standard(self):
        """Standard REJECT format returns False."""
        output = "DECISION: REJECT — with fixes\nHeadline: HL-VAGUE → ..."
        assert parse_decision(output) is False

    def test_reject_lowercase(self):
        """Case-insensitive REJECT returns False."""
        assert parse_decision("decision: reject") is False

    def test_garbage_input(self):
        """Unexpected output returns False (safe default = kill)."""
        assert parse_decision("Something went wrong") is False

    def test_empty_input(self):
        """Empty string returns False."""
        assert parse_decision("") is False

    def test_none_input(self):
        """None input returns False."""
        assert parse_decision(None) is False
