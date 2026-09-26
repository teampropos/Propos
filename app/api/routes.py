from datetime import datetime, timezone
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from ..extensions import db
from ..models import Client, Review, Reply, Location

api_bp = Blueprint("api", __name__)


@api_bp.route("/checkout", methods=["POST"])
@jwt_required()
def create_checkout():
    """Start a subscription for the logged-in client. Used once they've
    already registered (see /api/auth/register) — connecting Google and
    browsing the product don't require this to have happened first."""
    import os
    import stripe

    client_id = int(get_jwt_identity())
    client = Client.query.get(client_id)
    if not client:
        return jsonify({"error": "Not found"}), 404

    if client.is_subscribed:
        return jsonify({"error": "You already have an active subscription"}), 400

    stripe.api_key = os.environ.get("STRIPE_SECRET_KEY")
    frontend_url = os.environ.get("FRONTEND_URL", "http://localhost:3000")

    session = stripe.checkout.Session.create(
        customer_email=client.email,
        payment_method_types=["card"],
        line_items=[{"price": os.environ.get("STRIPE_PRICE_ID"), "quantity": 1}],
        mode="subscription",
        client_reference_id=str(client.id),
        success_url=f"{frontend_url}/onboarding?subscribed=1",
        cancel_url=f"{frontend_url}/onboarding",
    )

    return jsonify({"url": session.url})


@api_bp.route("/dashboard", methods=["GET"])
@jwt_required()
def dashboard():
    client_id = int(get_jwt_identity())
    client = Client.query.get(client_id)
    if not client:
        return jsonify({"error": "Not found"}), 404

    now = datetime.now(timezone.utc)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    replies_this_month = Reply.query.filter(
        Reply.client_id == client_id,
        Reply.posted_at >= month_start,
    ).count()

    pending_count = Review.query.filter(
        Review.client_id == client_id,
        Review.status.in_(["pending", "needs_human"]),
    ).count()

    recent = (
        Review.query
        .filter_by(client_id=client_id)
        .order_by(Review.received_at.desc())
        .limit(5)
        .all()
    )

    return jsonify({
        "replies_this_month": replies_this_month,
        "pending_count": pending_count,
        "recent_activity": [{
            "id": r.id,
            "reviewer_name": r.reviewer_name,
            "star_rating": r.star_rating,
            "review_text": r.review_text,
            "status": r.status,
            "received_at": r.received_at.isoformat(),
        } for r in recent],
    })


@api_bp.route("/reviews", methods=["GET"])
@jwt_required()
def reviews():
    client_id = int(get_jwt_identity())
    rows = Review.query.filter_by(client_id=client_id).order_by(Review.received_at.desc()).all()

    return jsonify([{
        "id": r.id,
        "reviewer_name": r.reviewer_name,
        "star_rating": r.star_rating,
        "review_text": r.review_text,
        "received_at": r.received_at.isoformat(),
        "status": r.status,
        "reply_text": r.reply.reply_text if r.reply else None,
        "replied_at": r.reply.posted_at.isoformat() if r.reply and r.reply.posted_at else None,
    } for r in rows])


@api_bp.route("/pending", methods=["GET"])
@jwt_required()
def pending():
    client_id = int(get_jwt_identity())

    def fetch(status):
        return Review.query.filter_by(client_id=client_id, status=status).order_by(Review.received_at.desc()).all()

    def serialize(r):
        rep = r.reply
        return {
            "id": r.id,
            "reviewer_name": r.reviewer_name,
            "star_rating": r.star_rating,
            "review_text": r.review_text,
            "received_at": r.received_at.isoformat(),
            "status": r.status,
            "routing_reason": rep.routing_reason if rep else None,
            "reply_text": rep.reply_text if rep else None,
            "reply_id": rep.id if rep else None,
        }

    pending_reviews = fetch("pending")
    return jsonify({
        "negative": [serialize(r) for r in pending_reviews if r.star_rating <= 3],
        "flagged_four_star": [serialize(r) for r in pending_reviews if r.star_rating == 4],
        "spam": [serialize(r) for r in fetch("spam")],
        "needs_human": [serialize(r) for r in fetch("needs_human")],
    })


@api_bp.route("/pending/<int:review_id>/approve", methods=["POST"])
@jwt_required()
def approve_reply(review_id):
    client_id = int(get_jwt_identity())
    review = Review.query.filter_by(id=review_id, client_id=client_id).first_or_404()
    client = Client.query.get(client_id)

    if not client.is_subscribed:
        return jsonify({"error": "Subscribe to start posting replies to your reviews"}), 402

    data = request.get_json() or {}
    edited_text = data.get("payload")

    rep = review.reply
    if not rep:
        return jsonify({"error": "No reply found"}), 404

    was_edited = False
    if edited_text and edited_text.strip() and edited_text != rep.reply_text:
        rep.reply_text = edited_text.strip()
        rep.edited = True
        was_edited = True

    if client.gbp_connected and review.google_review_id:
        from google.auth.exceptions import RefreshError
        from gbp.auth import get_session_for_client, flag_needs_reconnect
        from gbp.reviews import post_reply as post_reply_to_google

        try:
            google_session = get_session_for_client(client, db.session)
            post_reply_to_google(google_session, review.google_review_id, rep.reply_text)
        except RefreshError:
            flag_needs_reconnect(client, db.session)
            return jsonify({
                "error": "Your Google connection has stopped working. Reconnect it from the Locations page, then try approving again."
            }), 409
        rep.posted_at = datetime.now(timezone.utc)

    rep.approved_at = datetime.now(timezone.utc)
    review.status = "auto_posted"
    db.session.flush()

    from reply_engine.tone_memory import save_to_tone_memory
    save_to_tone_memory(client_id, rep.reply_text, edited=was_edited, db_session=db.session)

    return jsonify({"status": "approved"})


@api_bp.route("/pending/<int:review_id>/discard", methods=["POST"])
@jwt_required()
def discard_reply(review_id):
    client_id = int(get_jwt_identity())
    review = Review.query.filter_by(id=review_id, client_id=client_id).first_or_404()
    review.status = "discarded"
    db.session.commit()
    return jsonify({"status": "discarded"})


@api_bp.route("/pending/<int:review_id>/regenerate", methods=["POST"])
@jwt_required()
def regenerate_reply(review_id):
    client_id = int(get_jwt_identity())
    db_review = Review.query.filter_by(id=review_id, client_id=client_id).first_or_404()
    client = Client.query.get(client_id)
    data = request.get_json() or {}
    direction = data.get("payload") or ""

    from reply_engine.models import Review as EngineReview, BusinessProfile, TonePreference
    from reply_engine.tone_memory import get_tone_memory
    from reply_engine.prompt_builder import build_system_prompt, build_user_prompt
    from reply_engine.claude_client import generate_reply

    engine_review = EngineReview(
        reviewer_name=db_review.reviewer_name or "",
        star_rating=db_review.star_rating,
        review_text=db_review.review_text or "",
        review_id=db_review.google_review_id,
    )

    try:
        tone = TonePreference[client.tone_preference] if client.tone_preference else TonePreference.WARM_FRIENDLY
    except KeyError:
        tone = TonePreference.WARM_FRIENDLY

    profile = BusinessProfile(
        client_id=client_id,
        name=client.business_name,
        business_type=client.business_type,
        city=client.city,
        tone_preference=tone,
        owner_name=client.owner_name or "",
        signoff_style=client.signoff_style or "NONE",
        custom_instructions=client.custom_instructions,
    )

    tone_examples = get_tone_memory(client_id, db_session=db.session)
    system_prompt = build_system_prompt(profile, tone_examples)
    user_prompt = build_user_prompt(engine_review, direction=direction)
    new_reply_text = generate_reply(system_prompt, user_prompt)

    rep = db_review.reply
    if rep:
        rep.reply_text = new_reply_text
        rep.edited = False
    else:
        rep = Reply(
            review_id=db_review.id,
            client_id=client_id,
            reply_text=new_reply_text,
            auto_posted=False,
        )
        db.session.add(rep)

    db.session.commit()
    return jsonify({"status": "ok", "reply_text": new_reply_text})


@api_bp.route("/locations", methods=["GET"])
@jwt_required()
def locations():
    client_id = int(get_jwt_identity())
    rows = Location.query.filter_by(client_id=client_id).all()

    return jsonify([{
        "id": loc.id,
        "name": loc.name,
        "city": loc.city,
        "tone_preference": loc.tone_preference,
        "active": loc.active,
    } for loc in rows])


@api_bp.route("/locations", methods=["POST"])
@jwt_required()
def create_location():
    import os
    import stripe

    client_id = int(get_jwt_identity())
    client = Client.query.get(client_id)
    if not client:
        return jsonify({"error": "Not found"}), 404

    data = request.get_json() or {}
    name = (data.get("name") or "").strip()
    city = (data.get("city") or "").strip()
    tone_preference = data.get("tone_preference") or client.tone_preference

    if not name or not city:
        return jsonify({"error": "Name and city are required"}), 400

    if not client.is_subscribed:
        return jsonify({"error": "No active subscription found"}), 400

    stripe.api_key = os.environ.get("STRIPE_SECRET_KEY")
    item = stripe.SubscriptionItem.create(
        subscription=client.stripe_subscription_id,
        price=os.environ.get("STRIPE_PRICE_ADDITIONAL_LOCATION"),
        quantity=1,
    )

    location = Location(
        client_id=client_id,
        name=name,
        city=city,
        tone_preference=tone_preference,
        stripe_subscription_item_id=item.id,
        active=True,
    )
    db.session.add(location)
    db.session.commit()

    return jsonify({
        "id": location.id,
        "name": location.name,
        "city": location.city,
        "tone_preference": location.tone_preference,
        "active": location.active,
    }), 201


@api_bp.route("/locations/<int:location_id>", methods=["DELETE"])
@jwt_required()
def delete_location(location_id):
    import os
    import stripe

    client_id = int(get_jwt_identity())
    location = Location.query.filter_by(id=location_id, client_id=client_id).first_or_404()

    if location.stripe_subscription_item_id:
        stripe.api_key = os.environ.get("STRIPE_SECRET_KEY")
        try:
            stripe.SubscriptionItem.delete(location.stripe_subscription_item_id)
        except stripe.error.InvalidRequestError:
            pass  # already removed on Stripe's side

    location.active = False
    location.stripe_subscription_item_id = None
    db.session.commit()

    return jsonify({"status": "deactivated"})


@api_bp.route("/preferences", methods=["POST"])
@jwt_required()
def save_preferences():
    client_id = int(get_jwt_identity())
    client = Client.query.get(client_id)
    if not client:
        return jsonify({"error": "Not found"}), 404

    data = request.get_json() or {}
    if "tone_preference" in data:
        client.tone_preference = data["tone_preference"]
    if "owner_name" in data:
        client.owner_name = data.get("owner_name") or None
    if "reply_cadence" in data:
        client.reply_cadence = data["reply_cadence"]
    if "signoff_style" in data:
        style = data.get("signoff_style") or "NONE"
        if style not in ("NONE", "OWNER_NAME", "BUSINESS_NAME"):
            return jsonify({"error": "Invalid signoff_style"}), 400
        client.signoff_style = style
    if "custom_instructions" in data:
        instructions = (data.get("custom_instructions") or "").strip()
        if len(instructions) > 1000:
            return jsonify({"error": "Custom instructions must be 1000 characters or fewer"}), 400
        client.custom_instructions = instructions or None

    db.session.commit()
    return jsonify({"status": "saved"})


@api_bp.route("/onboarding/complete", methods=["POST"])
@jwt_required()
def onboarding_complete():
    client_id = int(get_jwt_identity())
    client = Client.query.get(client_id)
    if not client:
        return jsonify({"error": "Not found"}), 404

    data = request.get_json() or {}
    wants_backlog = bool(data.get("backlog"))
    backlog_amount_cents = None

    if wants_backlog:
        if not client.is_subscribed:
            return jsonify({"error": "Subscribe before requesting backlog processing"}), 400

        location = Location.query.filter_by(client_id=client.id, active=True).first()
        if not location or not location.gbp_review_path:
            return jsonify({"error": "Connect Google Business Profile before requesting backlog processing"}), 400

        from google.auth.exceptions import RefreshError
        from gbp.auth import get_session_for_client, flag_needs_reconnect
        from gbp.reviews import list_reviews as gbp_list_reviews

        try:
            gbp_session = get_session_for_client(client, db.session)
            raw_reviews = gbp_list_reviews(gbp_session, location.gbp_review_path)
        except RefreshError:
            flag_needs_reconnect(client, db.session)
            return jsonify({
                "error": "Your Google connection has stopped working. Reconnect it from the Locations page, then try requesting backlog processing again."
            }), 409
        count = len(raw_reviews)

        client.backlog_requested = True
        client.backlog_review_count = count

        if count > 0:
            from ..backlog import price_for_count, charge_backlog_fee

            _price_id, amount_cents = price_for_count(count)
            try:
                charge_id = charge_backlog_fee(client, amount_cents)
            except Exception as e:
                db.session.rollback()
                return jsonify({
                    "error": f"We couldn't charge your card for backlog processing ({e}). "
                             "Check your payment method in Billing and try again from there."
                }), 402

            client.backlog_status = "pending"
            client.backlog_charge_id = charge_id
            backlog_amount_cents = amount_cents
        else:
            # Nothing to process — don't charge for an empty backlog.
            client.backlog_status = "complete"

    client.onboarding_complete = True
    db.session.commit()

    from ..emails import send_onboarding_confirmation
    send_onboarding_confirmation(client)

    return jsonify({
        "status": "ok",
        "backlog_status": client.backlog_status,
        "backlog_review_count": client.backlog_review_count,
        "backlog_amount_cents": backlog_amount_cents,
    })


@api_bp.route("/billing/portal", methods=["POST"])
@jwt_required()
def billing_portal():
    import os
    import stripe
    client_id = int(get_jwt_identity())
    client = Client.query.get(client_id)
    if not client or not client.stripe_customer_id:
        return jsonify({"error": "No billing account found"}), 404

    stripe.api_key = os.environ.get("STRIPE_SECRET_KEY")
    frontend_url = os.environ.get("FRONTEND_URL", "http://localhost:3000")

    session = stripe.billing_portal.Session.create(
        customer=client.stripe_customer_id,
        return_url=f"{frontend_url}/portal/billing",
    )
    return jsonify({"url": session.url})
