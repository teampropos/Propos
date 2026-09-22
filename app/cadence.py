"""Reply cadence: how long to wait before actually posting an auto-approved
reply to Google. Only applies to the auto_post path (positive reviews) —
negative/needs_human reviews always wait for the client's own approval in
the portal regardless of cadence.
"""

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

SYDNEY = ZoneInfo("Australia/Sydney")

CADENCES = {
    "INSTANT": "The moment a review comes in",
    "WITHIN_24H": "Within 24 hours",
    "FEW_DAYS": "Within 3–4 days",
    "WEEKLY": "Weekly",
    "MONTHLY": "Monthly",
}

DEFAULT_CADENCE = "INSTANT"


def compute_scheduled_post_at(cadence: str | None, received_at: datetime) -> datetime:
    """Given when a review was received (UTC), return when its auto-posted
    reply should actually go live."""
    cadence = cadence or DEFAULT_CADENCE

    if cadence == "WITHIN_24H":
        return received_at + timedelta(hours=24)

    if cadence == "FEW_DAYS":
        return received_at + timedelta(days=3)

    if cadence == "WEEKLY":
        return _next_weekday_at(received_at, weekday=0, hour=8)  # next Monday, 8am Sydney

    if cadence == "MONTHLY":
        return _next_month_start_at(received_at, hour=8)  # 1st of next month, 8am Sydney

    return received_at  # INSTANT (or unrecognised — fail open to the current default behaviour)


def _next_weekday_at(received_at: datetime, weekday: int, hour: int) -> datetime:
    local = received_at.astimezone(SYDNEY)
    days_ahead = (weekday - local.weekday()) % 7
    target_date = local.date() + timedelta(days=days_ahead or 7)
    target = datetime(target_date.year, target_date.month, target_date.day, hour, 0, tzinfo=SYDNEY)
    return target.astimezone(received_at.tzinfo)


def _next_month_start_at(received_at: datetime, hour: int) -> datetime:
    local = received_at.astimezone(SYDNEY)
    year, month = local.year, local.month
    month += 1
    if month > 12:
        month = 1
        year += 1
    target = datetime(year, month, 1, hour, 0, tzinfo=SYDNEY)
    return target.astimezone(received_at.tzinfo)
