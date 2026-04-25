import os
import secrets
import stripe
from datetime import datetime, timezone, timedelta
from flask import Blueprint, request, jsonify
from ..extensions import db, bcrypt
from ..models import Client, FounderCounter

webhooks_bp = Blueprint("webhooks", __name__)

FOUNDER_TIER_LIMIT = 50


def _get_or_create_founder_counter():
    counter = FounderCounter.query.first()
    if not counter:
        counter = FounderCounter(count=0)
        db.session.add(counter)
        db.session.commit()
    return counter


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
    email = session.customer_email
    if not email and session.customer_details:
        email = session.customer_details.email
    stripe_customer_id = session.customer
    stripe_subscription_id = session.subscription
    metadata = session.metadata

    is_founder = _stripe_get(metadata, "plan") == "founder"

    if not email:
        return

    existing = Client.query.filter_by(email=email).first()
    if existing:
        return

    counter = _get_or_create_founder_counter()
    founder_tier = False
    if is_founder and counter.count < FOUNDER_TIER_LIMIT:
        founder_tier = True
        counter.count += 1

    setup_token = secrets.token_urlsafe(32)
    client = Client(
        email=email.lower(),
        business_name=_stripe_get(metadata, "business_name", ""),
        business_type=_stripe_get(metadata, "business_type", ""),
        city=_stripe_get(metadata, "city", ""),
        stripe_customer_id=stripe_customer_id,
        stripe_subscription_id=stripe_subscription_id,
        founder_tier=founder_tier,
        setup_token=setup_token,
        setup_token_expires_at=datetime.now(timezone.utc) + timedelta(days=7),
    )
    db.session.add(client)
    db.session.commit()
    # TODO: send onboarding email via Resend with setup link


def _handle_payment_failed(invoice):
    stripe_customer_id = invoice.customer
    client = Client.query.filter_by(stripe_customer_id=stripe_customer_id).first()
    if not client:
        return
    # TODO: send failed payment email via Resend


def _handle_subscription_deleted(subscription):
    stripe_customer_id = subscription.customer
    client = Client.query.filter_by(stripe_customer_id=stripe_customer_id).first()
    if not client:
        return
    client.cancelled_at = datetime.now(timezone.utc)
    client.data_archive_at = datetime.now(timezone.utc) + timedelta(days=30)
    db.session.commit()
    # TODO: send cancellation email via Resend


def _handle_subscription_updated(subscription):
    stripe_customer_id = subscription.customer
    stripe_subscription_id = subscription.id
    client = Client.query.filter_by(stripe_customer_id=stripe_customer_id).first()
    if not client:
        return
    client.stripe_subscription_id = stripe_subscription_id
    db.session.commit()
