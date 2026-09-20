"""Poll connected clients' Google Business Profile locations for new reviews,
run each one through the reply engine, and either auto-post the reply or
leave it for the client to approve in the portal.

Run via cron, e.g.:
  */10 * * * * cd /var/www/propos-api && .venv/bin/python scripts/poll_reviews.py >> /var/log/propos/poll_reviews.log 2>&1
"""

import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv

load_dotenv()

from app import create_app
from app.extensions import db
from app.models import Client, Location, Review, Reply
from gbp.auth import get_session_for_client
from gbp.reviews import list_reviews, post_reply, to_review
from reply_engine import BusinessProfile, TonePreference, process_review
from reply_engine.tone_memory import save_to_tone_memory


def _tone_for(client: Client) -> TonePreference:
    try:
        return TonePreference[client.tone_preference] if client.tone_preference else TonePreference.WARM_FRIENDLY
    except KeyError:
        return TonePreference.WARM_FRIENDLY


def poll_location(client: Client, location: Location) -> int:
    """Fetch and process new reviews for one location. Returns count processed."""
    session = get_session_for_client(client, db.session)
    raw_reviews = list_reviews(session, location.gbp_review_path)

    profile = BusinessProfile(
        client_id=client.id,
        name=client.business_name,
        business_type=client.business_type,
        city=client.city,
        tone_preference=_tone_for(client),
        owner_name=client.owner_name or "",
    )

    processed = 0
    for raw in raw_reviews:
        google_review_id = raw.get("name")
        if not google_review_id:
            continue
        if Review.query.filter_by(google_review_id=google_review_id).first():
            continue  # already seen on a previous poll

        engine_review = to_review(raw)
        result = process_review(engine_review, profile, db.session)

        status = "spam" if result.is_spam else ("needs_human" if result.low_confidence else "pending")
        db_review = Review(
            client_id=client.id,
            location_id=location.id,
            google_review_id=google_review_id,
            reviewer_name=engine_review.reviewer_name,
            star_rating=engine_review.star_rating,
            review_text=engine_review.review_text,
            received_at=datetime.now(timezone.utc),
            status=status,
        )
        db.session.add(db_review)
        db.session.flush()

        if result.is_spam:
            db.session.commit()
            processed += 1
            continue

        reply = Reply(
            review_id=db_review.id,
            client_id=client.id,
            reply_text=result.reply_text,
            routing_reason=result.routing_reason,
        )
        db.session.add(reply)

        if result.auto_post:
            post_reply(session, google_review_id, result.reply_text)
            now = datetime.now(timezone.utc)
            reply.auto_posted = True
            reply.posted_at = now
            reply.approved_at = now
            db_review.status = "auto_posted"
            db.session.commit()
            save_to_tone_memory(client.id, result.reply_text, edited=False, db_session=db.session)
        else:
            db.session.commit()

        processed += 1

    return processed


def main():
    app = create_app()
    with app.app_context():
        locations = (
            Location.query.filter_by(active=True)
            .filter(Location.gbp_review_path.isnot(None))
            .all()
        )
        total = 0
        for location in locations:
            client = Client.query.get(location.client_id)
            if not client or not client.gbp_connected:
                continue
            try:
                count = poll_location(client, location)
                total += count
                if count:
                    print(f"[{client.email}] {location.name}: {count} new review(s) processed")
            except Exception as e:
                print(f"[{client.email}] {location.name}: ERROR {e}")
        print(f"Done. {total} new review(s) processed across {len(locations)} location(s).")


if __name__ == "__main__":
    main()
