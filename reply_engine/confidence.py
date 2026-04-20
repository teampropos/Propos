"""Confidence check for generated replies."""

from .claude_client import classify


def check_confidence(review_text: str, reply_text: str) -> tuple[bool, str | None]:
    """Check if the AI reply needs human review due to low confidence.

    Returns (low_confidence, reason).
    low_confidence=True means the reply should be held for human editing.
    """
    system_prompt = (
        "You are a confidence checker for AI-generated Google review replies. "
        "Given a review and the AI's reply, determine if a human should review "
        "the reply before posting.\n\n"
        "Flag as LOW CONFIDENCE ONLY if any of these serious issues apply:\n"
        "- The review mentions a specific incident or date that the reply should not assume details about\n"
        "- The review mentions a staff member by name in a negative context\n"
        "- The review contains legal language, threats, or mentions of authorities\n"
        "- The AI reply makes factual claims about the business that could be wrong\n\n"
        "DO NOT flag as low confidence for:\n"
        "- Using the reviewer's first name (we always have this from their Google account — it is NOT an assumption)\n"
        "- Standard review reply language\n"
        "- Short or simple reviews\n"
        "- The reply being generic for a star-only review\n\n"
        "Default to CONFIDENT unless there is a clear, serious reason to flag.\n\n"
        "Reply in this exact format:\n"
        "CONFIDENT\n"
        "or\n"
        "LOW CONFIDENCE: [one-line reason]"
    )
    user_prompt = f'Review: "{review_text}"\n\nAI Reply: "{reply_text}"'

    result = classify(system_prompt, user_prompt)

    if "low confidence" in result:
        # Extract reason after the colon
        reason = None
        if ":" in result:
            reason = result.split(":", 1)[1].strip()
        return True, reason or "AI flagged low confidence"

    return False, None
