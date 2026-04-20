"""
Test the Propos reply engine with sample reviews.
Run with: ANTHROPIC_API_KEY=your_key python3 test_engine.py
"""

from reply_engine import process_review, Review, BusinessProfile, TonePreference


# ─── Sample business profiles (one per tone) ─────────────────────────────────

profiles = [
    BusinessProfile(
        name="The Olive Garden Bistro",
        business_type="restaurant",
        city="Sydney",
        client_id="test-001",
        owner_name="Marco",
        tone_preference=TonePreference.WARM_FRIENDLY,
    ),
    BusinessProfile(
        name="The Langham Hotel",
        business_type="hotel",
        city="Melbourne",
        client_id="test-002",
        owner_name="Victoria Chen",
        tone_preference=TonePreference.PROFESSIONAL,
    ),
    BusinessProfile(
        name="Bean Counter Cafe",
        business_type="cafe",
        city="Brisbane",
        client_id="test-003",
        owner_name="Jake",
        tone_preference=TonePreference.ENTHUSIASTIC,
    ),
    BusinessProfile(
        name="The Local Tap",
        business_type="bar",
        city="Perth",
        client_id="test-004",
        owner_name="Damo",
        tone_preference=TonePreference.RELAXED_CASUAL,
    ),
]

# ─── Sample reviews ──────────────────────────────────────────────────────────

reviews = [
    # 1. Glowing 5-star
    Review(
        reviewer_name="Sarah Mitchell",
        star_rating=5,
        review_text=(
            "Absolutely incredible experience! The wagyu steak was cooked to "
            "perfection and the tiramisu was the best I've ever had. Our waiter "
            "Tom was attentive without being overbearing. We'll definitely be back "
            "for our next anniversary."
        ),
    ),
    # 2. Positive 4-star
    Review(
        reviewer_name="James Liu",
        star_rating=4,
        review_text="Great coffee and friendly staff. Nice spot for a weekend brunch.",
    ),
    # 3. Mediocre 3-star
    Review(
        reviewer_name="Karen Thompson",
        star_rating=3,
        review_text=(
            "Food was okay but nothing special. The pasta was a bit overcooked "
            "and we waited 40 minutes for mains. Service was friendly though."
        ),
    ),
    # 4. Angry 1-star with detailed complaint
    Review(
        reviewer_name="David Brown",
        star_rating=1,
        review_text=(
            "Worst experience I've ever had at a restaurant. We had a booking "
            "for 7pm and weren't seated until 7:45. When the food finally came, "
            "my partner's chicken was raw in the middle. When we complained, the "
            "manager was dismissive and rude. We asked for the meal to be comped "
            "and were told no. Absolutely disgraceful. Will be contacting the "
            "health department."
        ),
    ),
    # 5. 4-star with negative text (edge case)
    Review(
        reviewer_name="Emily Watson",
        star_rating=4,
        review_text=(
            "The food was fine but honestly the service really let it down. "
            "Our server forgot our drinks twice and seemed annoyed when we "
            "asked for the bill. Wouldn't rush back."
        ),
    ),
]


# ─── Run tests ────────────────────────────────────────────────────────────────

def main():
    print("=" * 70)
    print("PROPOS REPLY ENGINE — TEST RUN")
    print("=" * 70)

    for i, review in enumerate(reviews):
        # Cycle through profiles so each tone gets tested
        profile = profiles[i % len(profiles)]

        print(f"\n{'─' * 70}")
        print(f"TEST {i + 1}")
        print(f"{'─' * 70}")
        print(f"Business:  {profile.name} ({profile.tone_preference.value})")
        print(f"Reviewer:  {review.reviewer_name}")
        print(f"Rating:    {'*' * review.star_rating} ({review.star_rating}/5)")

        # Truncate review text for display
        text_display = review.review_text[:100]
        if len(review.review_text) > 100:
            text_display += "..."
        print(f"Review:    {text_display}")

        print()
        print("Processing...")

        result = process_review(review, profile)

        auto_label = "YES" if result.auto_post else "NO"
        print(f"Auto post: {auto_label}")
        print(f"Reason:    {result.routing_reason}")

        if result.is_spam:
            print("STATUS:    SPAM — no reply generated")
        elif result.low_confidence:
            print(f"STATUS:    LOW CONFIDENCE — {result.confidence_reason}")

        print(f"Tone mem:  {result.tone_memory_examples_used} examples used")
        print()
        print(f"REPLY:")
        print(result.reply_text)
        print()


if __name__ == "__main__":
    main()
