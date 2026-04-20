"""Prompt construction for the Claude reply engine."""

from .models import BusinessProfile, Review, TONE_DESCRIPTIONS


def build_system_prompt(profile: BusinessProfile, tone_memory_examples: list[str]) -> str:
    """Build the system prompt for reply generation."""
    tone_desc = TONE_DESCRIPTIONS[profile.tone_preference]

    parts = [
        f"You are a review reply assistant for {profile.name}, "
        f"a {profile.business_type} in {profile.city}.",
        "",
        "RULES — follow these exactly:",
        "- Keep replies proportional to the review's detail. Short review = short reply (2-3 sentences). Detailed review = longer reply acknowledging specifics.",
        "- Absolute maximum: 200 words. Most replies should be well under this.",
        "- For negative reviews: keep it SHORT. Acknowledge the specific issue, apologise briefly, invite them to contact you directly. Never argue or get defensive. Over-explaining makes it worse.",
        "- Use the reviewer's first name naturally in the reply.",
        "- Be specific to what the reviewer actually mentioned. Never use generic filler.",
        '- NEVER use hollow phrases like "We appreciate your feedback", "Thank you for taking the time", "We value your opinion", "Your satisfaction is important to us".',
        "- No promises, no mention of discounts, no mention of refunds or compensation.",
        "- Output the reply text ONLY. No preamble, no quotes, no labels, no explanation.",
        "",
        f"TONE: {tone_desc}",
    ]

    if profile.owner_name:
        parts.append("")
        parts.append(
            f"Sign off replies naturally with the name '{profile.owner_name}'. "
            "Don't force it — use it where a sign-off feels natural, "
            "like 'Cheers, [name]' or 'Thanks, [name]'. Skip the sign-off "
            "for very short replies where it would feel awkward."
        )

    if tone_memory_examples:
        parts.append("")
        parts.append(
            "The following are previously approved replies for this business. "
            "Use them as a style reference to match the owner's voice and preferences. "
            "Do not copy them directly — use them to inform your tone and phrasing."
        )
        parts.append("")
        parts.append("<examples>")
        for i, example in enumerate(tone_memory_examples, 1):
            parts.append(f"  <reply>{example}</reply>")
        parts.append("</examples>")

    return "\n".join(parts)


def build_user_prompt(review: Review) -> str:
    """Build the user prompt for reply generation."""
    # Extract first name from reviewer
    first_name = _get_first_name(review.reviewer_name)

    parts = []

    if first_name:
        parts.append(f"Reviewer: {first_name}")
    else:
        parts.append("Reviewer: (anonymous)")

    parts.append(f"Rating: {review.star_rating}/5 stars")

    if review.review_text:
        parts.append(f'Review: "{review.review_text}"')
    else:
        parts.append("Review: (no text — star rating only)")

    parts.append("")
    parts.append("Write a reply.")

    return "\n".join(parts)


def _get_first_name(full_name: str) -> str:
    """Extract first name from a full name string."""
    if not full_name or not full_name.strip():
        return ""
    return full_name.strip().split()[0]
