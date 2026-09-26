"""Transactional and lifecycle emails, sent via Resend."""

import os

import resend

FROM_ADDRESS = "Propos <support@getpropos.com>"


def _client():
    resend.api_key = os.environ.get("RESEND_API_KEY")
    return resend


def _send(to: str, subject: str, body_html: str) -> None:
    _client().Emails.send({
        "from": FROM_ADDRESS,
        "to": [to],
        "subject": subject,
        "html": _wrap(body_html),
    })


def _wrap(body_html: str) -> str:
    return f"""
    <div style="font-family: -apple-system, BlinkMacSystemFont, sans-serif; max-width: 560px; margin: 0 auto; color: #141414;">
      <p style="font-weight: 600; font-size: 18px; margin-bottom: 24px;">Propos</p>
      {body_html}
      <p style="color: #999; font-size: 12px; margin-top: 32px; border-top: 1px solid #eee; padding-top: 16px;">
        Propos &middot; <a href="mailto:support@getpropos.com" style="color: #999;">support@getpropos.com</a>
      </p>
    </div>
    """


def send_welcome_email(client) -> None:
    """Sent right after checkout completes — the client's only way into their new account."""
    frontend_url = os.environ.get("FRONTEND_URL", "http://localhost:3000")
    setup_url = f"{frontend_url}/onboarding?token={client.setup_token}"
    body = f"""
    <h2 style="margin-bottom: 4px;">Welcome to Propos</h2>
    <p>Thanks for signing up, {client.business_name}. Let's get your account set up — it only takes a couple of minutes.</p>
    <p>
      <a href="{setup_url}" style="display:inline-block; background:#141414; color:#fff; padding:12px 24px; border-radius:4px; text-decoration:none; margin: 12px 0;">
        Set up your account
      </a>
    </p>
    <p style="color:#666; font-size: 13px;">This link expires in 7 days.</p>
    """
    _send(client.email, "Welcome to Propos — set up your account", body)


def send_subscription_activated_email(client) -> None:
    """Sent when an already-registered client (connected Google, browsed the
    portal) subscribes. They already have a password and an account — this
    just confirms payment went through, unlike send_welcome_email."""
    frontend_url = os.environ.get("FRONTEND_URL", "http://localhost:3000")
    body = f"""
    <h2 style="margin-bottom: 4px;">You&rsquo;re live</h2>
    <p>Payment received &mdash; Propos will start posting replies to {client.business_name}&rsquo;s reviews automatically from here on.</p>
    <p>
      <a href="{frontend_url}/portal/dashboard" style="display:inline-block; background:#141414; color:#fff; padding:12px 24px; border-radius:4px; text-decoration:none; margin: 12px 0;">
        View your dashboard
      </a>
    </p>
    """
    _send(client.email, "You're live on Propos", body)


def send_backlog_complete_email(client, count: int) -> None:
    """Sent once the one-time backlog job has drafted replies for every
    existing review it found. Nothing has posted yet — they're all waiting
    in Pending Approvals."""
    frontend_url = os.environ.get("FRONTEND_URL", "http://localhost:3000")
    body = f"""
    <h2 style="margin-bottom: 4px;">Your backlog is ready for review</h2>
    <p>Propos went through {count} existing review{'s' if count != 1 else ''} for {client.business_name}
    and drafted a reply for each one. Nothing has been posted &mdash; they&rsquo;re all waiting in
    Pending Approvals for you to review, edit, or approve.</p>
    <p>
      <a href="{frontend_url}/portal/pending" style="display:inline-block; background:#141414; color:#fff; padding:12px 24px; border-radius:4px; text-decoration:none; margin: 12px 0;">
        Review pending replies
      </a>
    </p>
    """
    _send(client.email, "Your review backlog is ready", body)


def send_onboarding_confirmation(client) -> None:
    """Sent once the onboarding wizard is completed."""
    body = f"""
    <h2 style="margin-bottom: 4px;">You&rsquo;re all set up</h2>
    <p>Propos is now monitoring your reviews at {client.business_name}. Positive reviews will be replied to automatically.
    We&rsquo;ll be in touch each week with an update.</p>
    """
    _send(client.email, "Propos is now monitoring your reviews", body)


def send_weekly_digest(client, replies_count: int, pending_count: int) -> None:
    """Sent every Monday to active clients. Caller should skip this when replies_count is 0."""
    frontend_url = os.environ.get("FRONTEND_URL", "http://localhost:3000")
    pending_line = (
        f"<p>You&rsquo;ve got {pending_count} review{'s' if pending_count != 1 else ''} waiting for your approval when you get a chance.</p>"
        if pending_count > 0
        else ""
    )
    body = f"""
    <h2 style="margin-bottom: 4px;">Your week with Propos</h2>
    <p>This week Propos replied to {replies_count} review{'s' if replies_count != 1 else ''} on your behalf.</p>
    {pending_line}
    <p><a href="{frontend_url}/portal/dashboard" style="color:#2B3A67;">View your dashboard &rarr;</a></p>
    """
    _send(client.email, "Your week with Propos", body)


def send_monthly_report(client, stats: dict) -> None:
    """Sent on the 1st of each month.

    stats keys: total_replied, positive_count, negative_count, auto_posted_count,
    manual_count, avg_rating, avg_rating_prev, reply_rate, themes (list, max 3),
    pending_count, month_label
    """
    frontend_url = os.environ.get("FRONTEND_URL", "http://localhost:3000")
    themes_html = ""
    if stats.get("themes"):
        items = "".join(f"<li>{t}</li>" for t in stats["themes"][:3])
        themes_html = f'<p style="margin-bottom:4px;"><strong>What stood out:</strong></p><ul style="margin-top:0;">{items}</ul>'

    rating_trend = ""
    if stats.get("avg_rating") is not None and stats.get("avg_rating_prev") is not None:
        diff = stats["avg_rating"] - stats["avg_rating_prev"]
        arrow = "&uarr;" if diff > 0 else ("&darr;" if diff < 0 else "&rarr;")
        rating_trend = f"<li>Average rating: {stats['avg_rating']:.1f}&#9733; {arrow} (was {stats['avg_rating_prev']:.1f}&#9733;)</li>"

    pending_line = (
        f"<li>{stats['pending_count']} review{'s' if stats['pending_count'] != 1 else ''} still waiting for your approval</li>"
        if stats.get("pending_count")
        else ""
    )

    body = f"""
    <h2 style="margin-bottom: 4px;">Your {stats.get('month_label', 'monthly')} report</h2>
    <p>Here&rsquo;s how {client.business_name} did:</p>
    <ul>
      <li>{stats.get('total_replied', 0)} reviews replied to ({stats.get('positive_count', 0)} positive, {stats.get('negative_count', 0)} negative)</li>
      <li>{stats.get('auto_posted_count', 0)} auto-posted, {stats.get('manual_count', 0)} you approved yourself</li>
      {rating_trend}
      <li>{stats.get('reply_rate', 100)}% reply rate</li>
      {pending_line}
    </ul>
    {themes_html}
    <p><a href="{frontend_url}/portal/dashboard" style="color:#2B3A67;">View your dashboard &rarr;</a></p>
    """
    _send(client.email, f"Your Propos report for {stats.get('month_label', 'this month')}", body)


def send_failed_payment_email(client) -> None:
    frontend_url = os.environ.get("FRONTEND_URL", "http://localhost:3000")
    body = f"""
    <h2 style="margin-bottom: 4px;">Action required &mdash; payment failed</h2>
    <p>We couldn&rsquo;t process your latest payment for Propos. Please update your card to keep your account active.</p>
    <p>
      <a href="{frontend_url}/portal/billing" style="display:inline-block; background:#141414; color:#fff; padding:12px 24px; border-radius:4px; text-decoration:none; margin: 12px 0;">
        Update payment method
      </a>
    </p>
    """
    _send(client.email, "Action required — payment failed", body)


def send_cancellation_email(client) -> None:
    body = """
    <h2 style="margin-bottom: 4px;">Your Propos account has been paused</h2>
    <p>Your subscription has ended and auto-replies are now off. Your data is safe for 30 days if you change your mind
    &mdash; just resubscribe and everything picks back up.</p>
    """
    _send(client.email, "Your Propos account has been paused", body)


def send_password_reset_email(client, reset_token: str) -> None:
    frontend_url = os.environ.get("FRONTEND_URL", "http://localhost:3000")
    reset_url = f"{frontend_url}/reset-password?token={reset_token}"
    body = f"""
    <h2 style="margin-bottom: 4px;">Reset your password</h2>
    <p>
      <a href="{reset_url}" style="display:inline-block; background:#141414; color:#fff; padding:12px 24px; border-radius:4px; text-decoration:none; margin: 12px 0;">
        Reset password
      </a>
    </p>
    <p style="color:#666; font-size: 13px;">This link expires in 1 hour. If you didn&rsquo;t request this, ignore this email.</p>
    """
    _send(client.email, "Reset your Propos password", body)
