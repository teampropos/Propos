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
        "- Use the reviewer's first name naturally in the reply.",
        "- Be specific to what the reviewer actually said. Never use generic filler.",
        "- NEVER attribute feelings, satisfaction, or enjoyment to the reviewer that they did not explicitly express. If they did not say they enjoyed something, do not write or imply that they did — not even with phrases like 'glad you enjoyed' or 'happy you had a good experience'.",
        "- When the reviewer raises a specific concern — price, wait time, a dish, service quality, or anything else — address that concern directly in the reply. Do not skip it or redirect to a generic closing without first acknowledging it.",
        "- For mixed or negative reviews (3 stars or below): be grounded and honest. Do not reframe the review as more positive than it was.",
        '- NEVER use hollow phrases like "We appreciate your feedback", "Thank you for taking the time", "We value your opinion", "Your satisfaction is important to us".',
        "- No promises, no mention of discounts, no mention of refunds or compensation.",
        "- Do not use dashes (em dashes or hyphens) as punctuation or sentence connectors. Use commas, full stops, or rewrite the sentence instead.",
        "- Output the reply text ONLY. No preamble, no quotes, no labels, no explanation.",
        "",
        "REPLY CALIBRATION BY STAR RATING:",
        "- 5 stars: Warm and effusive. Match the reviewer's energy. Genuine, brief thank-you.",
        "- 4 stars: Warm but measured. Acknowledge what they liked. If they flagged anything, address it briefly.",
        "- 3 stars: Grounded and measured. Acknowledge the mixed experience honestly. Do not inflate the positives. Address any specific concern the reviewer raised.",
        "- 1–2 stars: Brief, sincere, non-defensive. Acknowledge the specific issue(s) raised. Short apology. Invite them to contact you directly. Do not over-explain.",
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


def build_user_prompt(review: Review, direction: str | None = None) -> str:
    """Build the user prompt for reply generation."""
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

    if direction and direction.strip():
        parts.append(f"Direction from owner: {direction.strip()}")
        parts.append("")

    parts.append("Write a reply.")

    return "\n".join(parts)


def _get_first_name(full_name: str) -> str:
    """Extract first name from a full name string."""
    if not full_name or not full_name.strip():
        return ""
    return full_name.strip().split()[0]
