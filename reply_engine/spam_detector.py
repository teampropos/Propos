"""Spam detection for incoming reviews."""

from .claude_client import classify


def check_spam(review_text: str) -> bool:
    """Check if a review is spam, gibberish, or incoherent.

    Returns True if the review is spam.
    """
    system_prompt = (
        "You are a spam detector for Google reviews. "
        "Determine if the following review is spam, gibberish, incoherent, "
        "or suspiciously generic (e.g. copy-pasted template text, random characters, "
        "completely unrelated to a business). "
        "Reply with exactly one word: spam or legitimate. Nothing else."
    )
    user_prompt = f'Review: "{review_text}"'

    result = classify(system_prompt, user_prompt)

    return "spam" in result
