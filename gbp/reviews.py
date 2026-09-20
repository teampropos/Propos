"""Review read/reply operations against the legacy mybusiness v4 REST API."""

from reply_engine.models import Review

from .auth import MYBUSINESS_BASE_URL

STAR_RATING_MAP = {
    "ONE": 1,
    "TWO": 2,
    "THREE": 3,
    "FOUR": 4,
    "FIVE": 5,
}


def list_reviews(session, location_name: str) -> list[dict]:
    """List all reviews for a location.

    location_name is the full resource name, e.g.
    "accounts/1234567890/locations/9876543210".
    """
    reviews = []
    page_token = None

    while True:
        params = {"pageToken": page_token} if page_token else {}
        response = session.get(
            f"{MYBUSINESS_BASE_URL}/{location_name}/reviews", params=params
        )
        response.raise_for_status()
        data = response.json()
        reviews.extend(data.get("reviews", []))
        page_token = data.get("nextPageToken")
        if not page_token:
            break

    return reviews


def to_review(raw: dict) -> Review:
    """Map a raw mybusiness v4 review dict into reply_engine.models.Review.

    review_id is set to the review's full resource name (not just the bare
    reviewId) since that's what post_reply/delete_reply/get_review need,
    and it's what should be stored in db Review.google_review_id.
    """
    star_rating = STAR_RATING_MAP.get(raw.get("starRating", ""), 0)
    return Review(
        reviewer_name=raw.get("reviewer", {}).get("displayName", "Anonymous"),
        star_rating=star_rating,
        review_text=raw.get("comment", "") or "",
        review_id=raw.get("name"),
    )


def post_reply(session, review_name: str, reply_text: str) -> dict:
    """Post (or overwrite) a reply on a review.

    review_name is the full resource name, e.g.
    "accounts/.../locations/.../reviews/{reviewId}".
    """
    response = session.put(
        f"{MYBUSINESS_BASE_URL}/{review_name}/reply",
        json={"comment": reply_text},
    )
    response.raise_for_status()
    return response.json()


def delete_reply(session, review_name: str) -> None:
    """Delete the reply on a review."""
    response = session.delete(f"{MYBUSINESS_BASE_URL}/{review_name}/reply")
    response.raise_for_status()


def get_review(session, review_name: str) -> dict:
    """Fetch a single review by its full resource name."""
    response = session.get(f"{MYBUSINESS_BASE_URL}/{review_name}")
    response.raise_for_status()
    return response.json()
