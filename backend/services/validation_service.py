"""
Validation service — parses Amy Bot APPROVE/REJECT decisions.

Amy Bot returns structured output starting with either:
  'DECISION: APPROVE' → True (valid, push to CMS)
  'DECISION: REJECT'  → False (kill, do nothing)

Any non-APPROVE result = kill. Safe default.
"""


def parse_decision(amy_bot_output):
    """
    Parse Amy Bot output for APPROVE or REJECT.

    Looks for 'DECISION: APPROVE' or 'DECISION:APPROVE' (case-insensitive).
    Anything else — including malformed output — returns False (kill).

    Args:
        amy_bot_output: The full text response from Amy Bot.

    Returns:
        True if APPROVE, False otherwise.
    """
    output_upper = (amy_bot_output or "").upper()
    if "DECISION: APPROVE" in output_upper or "DECISION:APPROVE" in output_upper:
        return True
    return False
