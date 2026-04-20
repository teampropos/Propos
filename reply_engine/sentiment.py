"""Sentiment classification for 4-star edge case reviews."""

from .claude_client import classify


def check_sentiment(review_text: str) -> str:
    """Classify review text as 'positive' or 'negative'.

    Used only for 4-star reviews to determine routing.
    """
    system_prompt = (
        "You are a sentiment classifier for Google reviews. "
        "Classify the following review text as either 'positive' or 'negative'. "
        "Reply with exactly one word: positive or negative. Nothing else."
    )
    user_prompt = f'Review: "{review_text}"'

    result = classify(system_prompt, user_prompt)

    if "negative" in result:
        return "negative"
    return "positive"
