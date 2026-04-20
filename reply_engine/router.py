"""Routing logic for incoming reviews."""

from .models import Review

AUTO_POST_THRESHOLD = 4  # 4-star and above are candidates for auto-posting


def route_review(review: Review) -> tuple[bool, str]:
    """Determine whether a review should be auto-posted or held for approval.

    Returns (auto_post, reason).
    Note: 4-star reviews need a sentiment check before final routing —
    this function returns the initial routing decision. The engine
    handles the sentiment check for 4-star reviews separately.
    """
    if review.star_rating == 5:
        return True, "5-star review — auto-posted"

    if review.star_rating == 4:
        # Needs sentiment check — engine will handle this
        # Return hold as default, engine overrides if sentiment is positive
        return False, "4-star review — pending sentiment check"

    if review.star_rating == 3:
        return False, "3-star review — held for approval"

    # 1-2 stars
    return False, f"{review.star_rating}-star review — held for approval"
