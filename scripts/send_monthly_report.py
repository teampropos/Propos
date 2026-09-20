"""Send the monthly win report to every active client, covering the month
that just ended. Intended to run on the 1st of each month.

Run via cron:
  0 8 1 * * cd /var/www/propos-api && .venv/bin/python scripts/send_monthly_report.py >> /var/log/propos/monthly_report.log 2>&1
"""

import os
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv

load_dotenv()

from anthropic import Anthropic

from app import create_app
from app.models import Client, Reply, Review
from app.emails import send_monthly_report

MODEL = "claude-sonnet-4-5-20250929"


def _month_bounds(today: datetime):
    """Return (start, end) of the month before today's month, both UTC."""
    first_of_this_month = today.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    last_month_end = first_of_this_month
    if first_of_this_month.month == 1:
        last_month_start = first_of_this_month.replace(year=first_of_this_month.year - 1, month=12)
    else:
        last_month_start = first_of_this_month.replace(month=first_of_this_month.month - 1)
    return last_month_start, last_month_end


def _extract_themes(review_texts: list[str]) -> list[str]:
    """One Claude call to pull up to 3 recurring themes from this month's reviews."""
    texts = [t for t in review_texts if t and t.strip()]
    if len(texts) < 3:
        return []

    client = Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))
    joined = "\n".join(f"- {t[:200]}" for t in texts[:50])
    message = client.messages.create(
        model=MODEL,
        max_tokens=150,
        system=(
            "You analyse a batch of customer reviews for a hospitality business and identify "
            "up to 3 short recurring themes or standout mentions (e.g. specific dishes, staff "
            "members, or service traits customers repeatedly praised or criticised). "
            "Reply with one theme per line, each under 8 words. No numbering, no preamble. "
            "If there's nothing worth highlighting, reply with an empty response."
        ),
        messages=[{"role": "user", "content": joined}],
    )
    text = message.content[0].text.strip()
    if not text:
        return []
    return [line.strip("-• ").strip() for line in text.split("\n") if line.strip()][:3]


def build_stats(client: Client, start: datetime, end: datetime) -> dict | None:
    reviews_this_month = Review.query.filter(
        Review.client_id == client.id,
        Review.received_at >= start,
        Review.received_at < end,
    ).all()

    if not reviews_this_month:
        return None

    replies_this_month = Reply.query.join(Review).filter(
        Review.client_id == client.id,
        Review.received_at >= start,
        Review.received_at < end,
    ).all()

    positive_count = sum(1 for r in reviews_this_month if r.star_rating >= 4)
    negative_count = sum(1 for r in reviews_this_month if r.star_rating <= 3)
    auto_posted_count = sum(1 for r in replies_this_month if r.auto_posted)
    manual_count = sum(1 for r in replies_this_month if not r.auto_posted)

    total_received = len(reviews_this_month)
    total_replied = len(replies_this_month)
    reply_rate = round((total_replied / total_received) * 100) if total_received else 0

    avg_rating = sum(r.star_rating for r in reviews_this_month) / total_received

    prev_start, prev_end = _month_bounds(start)
    prev_reviews = Review.query.filter(
        Review.client_id == client.id,
        Review.received_at >= prev_start,
        Review.received_at < prev_end,
    ).all()
    avg_rating_prev = (
        sum(r.star_rating for r in prev_reviews) / len(prev_reviews) if prev_reviews else None
    )

    pending_count = Review.query.filter(
        Review.client_id == client.id,
        Review.status.in_(["pending", "needs_human"]),
    ).count()

    themes = _extract_themes([r.review_text for r in reviews_this_month])

    return {
        "total_replied": total_replied,
        "positive_count": positive_count,
        "negative_count": negative_count,
        "auto_posted_count": auto_posted_count,
        "manual_count": manual_count,
        "avg_rating": avg_rating,
        "avg_rating_prev": avg_rating_prev,
        "reply_rate": reply_rate,
        "pending_count": pending_count,
        "themes": themes,
        "month_label": start.strftime("%B"),
    }


def main():
    app = create_app()
    with app.app_context():
        now = datetime.now(timezone.utc)
        start, end = _month_bounds(now)
        clients = Client.query.filter_by(cancelled_at=None).all()

        sent = 0
        for client in clients:
            stats = build_stats(client, start, end)
            if stats is None:
                continue
            send_monthly_report(client, stats)
            sent += 1
            print(f"[{client.email}] monthly report sent for {stats['month_label']}")

        print(f"Done. {sent} report(s) sent out of {len(clients)} active client(s).")


if __name__ == "__main__":
    main()
