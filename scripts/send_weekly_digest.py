"""Send the weekly digest email to every active client. Skips clients with
zero replies sent in the past 7 days.

Run via cron, e.g. every Monday morning:
  0 8 * * 1 cd /var/www/propos-api && .venv/bin/python scripts/send_weekly_digest.py >> /var/log/propos/weekly_digest.log 2>&1
"""

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv

load_dotenv()

from app import create_app
from app.models import Client, Reply, Review
from app.emails import send_weekly_digest


def main():
    app = create_app()
    with app.app_context():
        since = datetime.now(timezone.utc) - timedelta(days=7)
        clients = Client.query.filter_by(cancelled_at=None).all()

        sent = 0
        for client in clients:
            replies_count = Reply.query.filter(
                Reply.client_id == client.id,
                Reply.posted_at >= since,
            ).count()

            if replies_count == 0:
                continue

            pending_count = Review.query.filter(
                Review.client_id == client.id,
                Review.status.in_(["pending", "needs_human"]),
            ).count()

            send_weekly_digest(client, replies_count, pending_count)
            sent += 1
            print(f"[{client.email}] weekly digest sent ({replies_count} replies, {pending_count} pending)")

        print(f"Done. {sent} digest(s) sent out of {len(clients)} active client(s).")


if __name__ == "__main__":
    main()
