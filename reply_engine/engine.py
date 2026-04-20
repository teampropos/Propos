"""Main orchestrator for the Propos reply engine."""

from .models import Review, BusinessProfile, ReplyResult
from .router import route_review
from .sentiment import check_sentiment
from .spam_detector import check_spam
from .confidence import check_confidence
from .tone_memory import get_tone_memory
from .prompt_builder import build_system_prompt, build_user_prompt
from .claude_client import generate_reply


def process_review(
    review: Review,
    profile: BusinessProfile,
    db_session=None,
) -> ReplyResult:
    """Process a single review through the full pipeline.

    Pipeline:
    1. Route based on star rating
    2. Sentiment check (4-star only, skip if no text)
    3. Spam check (skip if no text)
    4. Generate reply
    5. Confidence check (separate Claude call)
    6. Return result
    """
    has_text = bool(review.review_text and review.review_text.strip())

    # Step 1: Initial routing
    auto_post, routing_reason = route_review(review)

    # Step 2: Sentiment check for 4-star reviews (skip if no text)
    if review.star_rating == 4 and has_text:
        sentiment = check_sentiment(review.review_text)
        if sentiment == "positive":
            auto_post = True
            routing_reason = "4-star review with positive sentiment — auto-posted"
        else:
            auto_post = False
            routing_reason = (
                "This review was flagged because the content appears "
                "negative despite the 4-star rating."
            )

    # Step 3: Spam check (skip if no text)
    if has_text:
        is_spam = check_spam(review.review_text)
        if is_spam:
            return ReplyResult(
                reply_text="",
                auto_post=False,
                routing_reason="Flagged as spam — no reply generated",
                review=review,
                tone_used=profile.tone_preference,
                tone_memory_examples_used=0,
                is_spam=True,
            )

    # Step 4: Get tone memory and generate reply
    tone_memory_examples = get_tone_memory(profile.client_id, db_session)

    system_prompt = build_system_prompt(profile, tone_memory_examples)
    user_prompt = build_user_prompt(review)

    reply_text = generate_reply(system_prompt, user_prompt)

    # Step 5: Confidence check (separate call, skip if no text)
    low_confidence = False
    confidence_reason = None
    if has_text:
        low_confidence, confidence_reason = check_confidence(
            review.review_text, reply_text
        )
        if low_confidence:
            auto_post = False
            routing_reason = f"Needs human reply — {confidence_reason or 'AI flagged low confidence'}"

    return ReplyResult(
        reply_text=reply_text,
        auto_post=auto_post,
        routing_reason=routing_reason,
        review=review,
        tone_used=profile.tone_preference,
        tone_memory_examples_used=len(tone_memory_examples),
        low_confidence=low_confidence,
        confidence_reason=confidence_reason,
    )
