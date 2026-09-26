"""Backlog processing: pricing tiers and the one-time charge for working
through a client's existing (pre-Propos) reviews. Actual review fetching
and reply generation lives in scripts/poll_reviews.py's process_backlogs(),
since it can involve hundreds of reviews and needs to run in the
background rather than inside a request.
"""

import os

# (max_count_for_this_tier, price_env_var, amount_in_cents) — the last
# tier's max_count is None to mean "no upper bound".
TIERS = [
    (25, "STRIPE_PRICE_BACKLOG_1_25", 4900),
    (100, "STRIPE_PRICE_BACKLOG_26_100", 9900),
    (200, "STRIPE_PRICE_BACKLOG_101_200", 14900),
    (None, "STRIPE_PRICE_BACKLOG_200_PLUS", 19900),
]


def price_for_count(count: int) -> tuple[str, int]:
    """Return (stripe_price_id, amount_in_cents) for a given backlog size."""
    for max_count, env_var, amount in TIERS:
        if max_count is None or count <= max_count:
            return os.environ[env_var], amount
    raise AssertionError("unreachable — last tier has no upper bound")


def charge_backlog_fee(client, amount_cents: int) -> str:
    """Charge the client's saved card (from their subscription checkout)
    off-session for the backlog fee. Returns the PaymentIntent id.
    Raises stripe.error.StripeError on failure, including cards that need
    extra authentication (off_session + requires_action)."""
    import stripe

    stripe.api_key = os.environ.get("STRIPE_SECRET_KEY")

    payment_methods = stripe.PaymentMethod.list(customer=client.stripe_customer_id, type="card")
    if not payment_methods.data:
        raise RuntimeError("No saved card found for this customer")
    payment_method_id = payment_methods.data[0].id

    intent = stripe.PaymentIntent.create(
        amount=amount_cents,
        currency="aud",
        customer=client.stripe_customer_id,
        payment_method=payment_method_id,
        off_session=True,
        confirm=True,
        description=f"Propos review backlog processing — {client.business_name}",
    )
    return intent.id
