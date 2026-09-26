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

from google.auth.exceptions import RefreshError

from app import create_app
from app.cadence import compute_scheduled_post_at
from app.extensions import db
from app.models import Client, Location, Review, Reply
from gbp.auth import get_session_for_client, flag_needs_reconnect
from gbp.reviews import list_reviews, post_reply, to_review
from reply_engine import BusinessProfile, TonePreference, process_review
from reply_engine.tone_memory import save_to_tone_memory


def _tone_for(client: Client) -> TonePreference:
    try:
        return TonePreference[client.tone_preference] if client.tone_preference else TonePreference.WARM_FRIENDLY
    except KeyError:
        return TonePreference.WARM_FRIENDLY


def poll_location(client: Client, location: Location) -> int:
    """Fetch and process new reviews for one location. Returns count processed.

    Polling and drafting happen regardless of subscription status — a client
    who's connected Google but hasn't paid yet still sees real reviews and
    draft replies land in their portal, so they can see Propos working
    before committing to pay. Only the live write to Google is gated on
    client.is_subscribed; nothing gets posted to a real business's Google
    listing until they've actually subscribed."""
    is_paid = client.is_subscribed
    session = get_session_for_client(client, db.session)
    raw_reviews = list_reviews(session, location.gbp_review_path)

    profile = BusinessProfile(
        client_id=client.id,
        name=client.business_name,
        business_type=client.business_type,
        city=client.city,
        tone_preference=_tone_for(client),
        owner_name=client.owner_name or "",
        signoff_style=client.signoff_style or "NONE",
        custom_instructions=client.custom_instructions,
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

        if result.auto_post and is_paid:
            scheduled_for = compute_scheduled_post_at(client.reply_cadence, db_review.received_at)
            reply.scheduled_post_at = scheduled_for
            reply.approved_at = datetime.now(timezone.utc)

            if scheduled_for <= datetime.now(timezone.utc):
                # Instant cadence (or the scheduled time already elapsed) — post right away.
                post_reply(session, google_review_id, result.reply_text)
                reply.auto_posted = True
                reply.posted_at = datetime.now(timezone.utc)
                db_review.status = "auto_posted"
                db.session.commit()
                save_to_tone_memory(client.id, result.reply_text, edited=False, db_session=db.session)
            else:
                db_review.status = "scheduled"
                db.session.commit()
        elif result.auto_post and not is_paid:
            # Would auto-post once paid — for now it's a draft the client can
            # see in their portal to show Propos is working, nothing more.
            # No scheduled_post_at is set, so post_due_replies() below can
            # never pick this up and post it late/stale once they do pay.
            db_review.status = "preview"
            db.session.commit()
        else:
            db.session.commit()

        processed += 1

    return processed


def post_due_replies() -> int:
    """Post any auto-approved replies whose scheduled time has arrived —
    covers WITHIN_24H/FEW_DAYS/WEEKLY/MONTHLY cadences, which don't post at
    the moment they're first detected."""
    due = Reply.query.filter(
        Reply.scheduled_post_at.isnot(None),
        Reply.scheduled_post_at <= datetime.now(timezone.utc),
        Reply.posted_at.is_(None),
    ).all()

    posted = 0
    for reply in due:
        review = Review.query.get(reply.review_id)
        client = Client.query.get(reply.client_id)
        if not review or not client or not client.gbp_connected:
            continue
        if not client.is_subscribed:
            # Subscription was cancelled after this reply got scheduled —
            # don't post to their live Google listing.
            continue
        try:
            session = get_session_for_client(client, db.session)
            post_reply(session, review.google_review_id, reply.reply_text)
            now = datetime.now(timezone.utc)
            reply.auto_posted = True
            reply.posted_at = now
            review.status = "auto_posted"
            db.session.commit()
            save_to_tone_memory(client.id, reply.reply_text, edited=False, db_session=db.session)
            posted += 1
        except RefreshError:
            flag_needs_reconnect(client, db.session)
            print(f"[{client.email}] Google connection dead — flagged for reconnect")
        except Exception as e:
            print(f"[{client.email}] failed to post scheduled reply for review {review.id}: {e}")

    return posted


def process_backlogs() -> int:
    """One-time processing of a client's full review history, for anyone
    who paid for backlog processing during onboarding. Runs in the
    background (via this same cron cycle) rather than inside the
    onboarding request, since drafting replies for potentially hundreds of
    reviews would time out an HTTP request.

    Every resulting review is held for approval (spam/needs_human/pending)
    — never auto-posted, regardless of star rating or cadence. These are
    reviews the owner has never seen a Propos draft for; silently mass-
    posting a backlog of replies to their live Google listing without them
    seeing it first would be a bad surprise, not a feature."""
    pending_clients = Client.query.filter_by(backlog_status="pending").all()
    processed_count = 0

    for client in pending_clients:
        client.backlog_status = "processing"
        db.session.commit()

        try:
            location = Location.query.filter_by(client_id=client.id, active=True).first()
            if not location or not location.gbp_review_path:
                client.backlog_status = "failed"
                db.session.commit()
                print(f"[{client.email}] backlog processing failed: no connected location")
                continue

            session = get_session_for_client(client, db.session)
            raw_reviews = list_reviews(session, location.gbp_review_path)

            profile = BusinessProfile(
                client_id=client.id,
                name=client.business_name,
                business_type=client.business_type,
                city=client.city,
                tone_preference=_tone_for(client),
                owner_name=client.owner_name or "",
                signoff_style=client.signoff_style or "NONE",
                custom_instructions=client.custom_instructions,
            )

            client_processed = 0
            for raw in raw_reviews:
                google_review_id = raw.get("name")
                if not google_review_id:
                    continue
                if Review.query.filter_by(google_review_id=google_review_id).first():
                    continue  # already picked up by the regular poller or a prior run

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

                if not result.is_spam:
                    reply = Reply(
                        review_id=db_review.id,
                        client_id=client.id,
                        reply_text=result.reply_text,
                        routing_reason=result.routing_reason or "Backlog review — held for your approval",
                    )
                    db.session.add(reply)

                db.session.commit()
                client_processed += 1
                processed_count += 1

            client.backlog_status = "complete"
            db.session.commit()
            print(f"[{client.email}] backlog complete: {client_processed} review(s) drafted")

            try:
                from app.emails import send_backlog_complete_email
                send_backlog_complete_email(client, client_processed)
            except Exception as e:
                # The backlog itself is genuinely done and already committed
                # as such — an email delivery failure shouldn't reclassify
                # real, successful processing as failed.
                print(f"[{client.email}] backlog complete, but notification email failed: {e}")

        except RefreshError:
            db.session.rollback()
            client.backlog_status = "failed"
            flag_needs_reconnect(client, db.session)
            print(f"[{client.email}] backlog processing failed — Google connection dead, flagged for reconnect")
        except Exception as e:
            db.session.rollback()
            client.backlog_status = "failed"
            db.session.commit()
            print(f"[{client.email}] backlog processing failed: {e}")

    return processed_count


def notify_reconnect_needed() -> int:
    """Email anyone newly flagged with a dead Google connection — once,
    not on every 10-minute cron cycle. get_session_for_client() (called
    from poll_location/post_due_replies/process_backlogs above) is what
    actually sets google_needs_reconnect when a refresh fails; this just
    handles the one-time notification."""
    clients = Client.query.filter_by(
        google_needs_reconnect=True,
        google_reconnect_notified_at=None,
    ).all()

    notified = 0
    for client in clients:
        try:
            from app.emails import send_google_reconnect_email
            send_google_reconnect_email(client)
            client.google_reconnect_notified_at = datetime.now(timezone.utc)
            db.session.commit()
            notified += 1
        except Exception as e:
            print(f"[{client.email}] failed to send reconnect email: {e}")

    return notified


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
            except RefreshError:
                flag_needs_reconnect(client, db.session)
                print(f"[{client.email}] {location.name}: Google connection dead — flagged for reconnect")
            except Exception as e:
                print(f"[{client.email}] {location.name}: ERROR {e}")

        due_posted = post_due_replies()
        backlog_processed = process_backlogs()
        reconnect_notified = notify_reconnect_needed()

        print(f"Done. {total} new review(s) processed across {len(locations)} location(s), {due_posted} scheduled repl(y/ies) posted, {backlog_processed} backlog review(s) drafted, {reconnect_notified} reconnect email(s) sent.")


if __name__ == "__main__":
    main()
