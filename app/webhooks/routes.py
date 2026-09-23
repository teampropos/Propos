import os
import secrets
import stripe
from datetime import datetime, timezone, timedelta
from flask import Blueprint, request, jsonify
from ..extensions import db, bcrypt
from ..models import Client

webhooks_bp = Blueprint("webhooks", __name__)


@webhooks_bp.route("/stripe", methods=["POST"])
def stripe_webhook():
    payload = request.get_data()
    sig_header = request.headers.get("Stripe-Signature")
    webhook_secret = os.environ.get("STRIPE_WEBHOOK_SECRET")

    try:
        event = stripe.Webhook.construct_event(payload, sig_header, webhook_secret)
    except (ValueError, stripe.error.SignatureVerificationError):
        return jsonify({"error": "Invalid payload"}), 400

    if event["type"] == "checkout.session.completed":
        _handle_checkout_completed(event["data"]["object"])

    elif event["type"] == "invoice.payment_failed":
        _handle_payment_failed(event["data"]["object"])

    elif event["type"] == "customer.subscription.deleted":
        _handle_subscription_deleted(event["data"]["object"])

    elif event["type"] == "customer.subscription.updated":
        _handle_subscription_updated(event["data"]["object"])

    return jsonify({"status": "ok"})


def _stripe_get(obj, key, default=None):
    """Safe key access for Stripe objects which don't support .get()."""
    try:
        return obj[key]
    except (KeyError, TypeError):
        return default


def _handle_checkout_completed(session):
    stripe_customer_id = session.customer
    stripe_subscription_id = session.subscription
    client_reference_id = _stripe_get(session, "client_reference_id")

    if client_reference_id:
        # The normal path: client registered (POST /api/auth/register),
        # possibly connected Google and browsed the portal, then subscribed
        # via POST /api/checkout, which stamped their client id onto the
        # Stripe session. Activate that same account — no new account, no
        # setup-your-password email, since both already exist.
        client = Client.query.get(int(client_reference_id))
        if not client:
            return
        client.stripe_customer_id = stripe_customer_id
        client.stripe_subscription_id = stripe_subscription_id
        db.session.commit()

        from ..emails import send_subscription_activated_email
        send_subscription_activated_email(client)
        return

    # Fallback path: no client_reference_id, e.g. a payment link created
    # directly in the Stripe dashboard rather than through /api/checkout.
    # Preserve the old pay-first behaviour so a real payment never fails to
    # produce an account.
    email = session.customer_email
    if not email and session.customer_details:
        email = session.customer_details.email
    metadata = session.metadata

    if not email:
        return

    existing = Client.query.filter_by(email=email).first()
    if existing:
        existing.stripe_customer_id = stripe_customer_id
        existing.stripe_subscription_id = stripe_subscription_id
        db.session.commit()
        return

    setup_token = secrets.token_urlsafe(32)
    client = Client(
        email=email.lower(),
        business_name=_stripe_get(metadata, "business_name", ""),
        business_type=_stripe_get(metadata, "business_type", ""),
        city=_stripe_get(metadata, "city", ""),
        stripe_customer_id=stripe_customer_id,
        stripe_subscription_id=stripe_subscription_id,
        setup_token=setup_token,
        setup_token_expires_at=datetime.now(timezone.utc) + timedelta(days=7),
    )
    db.session.add(client)
    db.session.commit()

    from ..emails import send_welcome_email
    send_welcome_email(client)


def _handle_payment_failed(invoice):
    stripe_customer_id = invoice.customer
    client = Client.query.filter_by(stripe_customer_id=stripe_customer_id).first()
    if not client:
        return

    from ..emails import send_failed_payment_email
    send_failed_payment_email(client)


def _handle_subscription_deleted(subscription):
    stripe_customer_id = subscription.customer
    client = Client.query.filter_by(stripe_customer_id=stripe_customer_id).first()
    if not client:
        return
    client.cancelled_at = datetime.now(timezone.utc)
    client.data_archive_at = datetime.now(timezone.utc) + timedelta(days=30)
    db.session.commit()

    from ..emails import send_cancellation_email
    send_cancellation_email(client)


def _handle_subscription_updated(subscription):
    stripe_customer_id = subscription.customer
    stripe_subscription_id = subscription.id
    client = Client.query.filter_by(stripe_customer_id=stripe_customer_id).first()
    if not client:
        return
    client.stripe_subscription_id = stripe_subscription_id
    db.session.commit()
