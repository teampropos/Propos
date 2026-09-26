from datetime import datetime, timezone
from .extensions import db


class Client(db.Model):
    __tablename__ = "clients"

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=True)
    business_name = db.Column(db.String(255), nullable=False)
    business_type = db.Column(db.String(100), nullable=False)
    city = db.Column(db.String(100), nullable=False)
    owner_name = db.Column(db.String(255), nullable=True)
    signoff_style = db.Column(db.String(20), default="NONE", nullable=False)  # NONE, OWNER_NAME, BUSINESS_NAME
    custom_instructions = db.Column(db.Text, nullable=True)
    tone_preference = db.Column(db.String(50), nullable=True)
    reply_cadence = db.Column(db.String(50), nullable=True)
    stripe_customer_id = db.Column(db.String(255), nullable=True)
    stripe_subscription_id = db.Column(db.String(255), nullable=True)
    google_oauth_id = db.Column(db.String(255), nullable=True)
    google_access_token = db.Column(db.Text, nullable=True)
    google_refresh_token = db.Column(db.Text, nullable=True)
    gbp_connected = db.Column(db.Boolean, default=False, nullable=False)
    google_needs_reconnect = db.Column(db.Boolean, default=False, nullable=False)
    google_reconnect_notified_at = db.Column(db.DateTime, nullable=True)
    onboarding_complete = db.Column(db.Boolean, default=False, nullable=False)
    setup_token = db.Column(db.String(255), nullable=True)
    setup_token_expires_at = db.Column(db.DateTime, nullable=True)
    reset_token = db.Column(db.String(255), nullable=True)
    reset_token_expires_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    cancelled_at = db.Column(db.DateTime, nullable=True)
    data_archive_at = db.Column(db.DateTime, nullable=True)
    backlog_requested = db.Column(db.Boolean, default=False, nullable=False)
    backlog_status = db.Column(db.String(20), nullable=True)  # pending, processing, complete, failed
    backlog_review_count = db.Column(db.Integer, nullable=True)
    backlog_charge_id = db.Column(db.String(255), nullable=True)

    locations = db.relationship("Location", back_populates="client", lazy="dynamic")
    reviews = db.relationship("Review", back_populates="client", lazy="dynamic")
    replies = db.relationship("Reply", back_populates="client", lazy="dynamic")
    tone_memories = db.relationship("ToneMemory", back_populates="client", lazy="dynamic")

    @property
    def is_subscribed(self) -> bool:
        """True once Stripe payment has actually gone through and the
        subscription hasn't since been cancelled. An account can exist,
        connect Google, and be browsed before this is true — see the
        connect-before-pay flow in auth/routes.py and api/routes.py."""
        return self.stripe_subscription_id is not None and self.cancelled_at is None


class Location(db.Model):
    __tablename__ = "locations"

    id = db.Column(db.Integer, primary_key=True)
    client_id = db.Column(db.Integer, db.ForeignKey("clients.id"), nullable=False)
    google_location_id = db.Column(db.String(255), nullable=True)
    gbp_review_path = db.Column(db.String(255), nullable=True)
    stripe_subscription_item_id = db.Column(db.String(255), nullable=True)
    name = db.Column(db.String(255), nullable=False)
    city = db.Column(db.String(100), nullable=False)
    tone_preference = db.Column(db.String(50), nullable=True)
    active = db.Column(db.Boolean, default=True, nullable=False)

    client = db.relationship("Client", back_populates="locations")
    reviews = db.relationship("Review", back_populates="location", lazy="dynamic")


class Review(db.Model):
    __tablename__ = "reviews"

    id = db.Column(db.Integer, primary_key=True)
    client_id = db.Column(db.Integer, db.ForeignKey("clients.id"), nullable=False)
    location_id = db.Column(db.Integer, db.ForeignKey("locations.id"), nullable=True)
    google_review_id = db.Column(db.String(255), unique=True, nullable=False)
    reviewer_name = db.Column(db.String(255), nullable=True)
    star_rating = db.Column(db.Integer, nullable=False)
    review_text = db.Column(db.Text, nullable=True)
    received_at = db.Column(db.DateTime, nullable=False)
    status = db.Column(
        db.String(50),
        nullable=False,
        default="pending",
    )

    client = db.relationship("Client", back_populates="reviews")
    location = db.relationship("Location", back_populates="reviews")
    reply = db.relationship("Reply", back_populates="review", uselist=False)


class Reply(db.Model):
    __tablename__ = "replies"

    id = db.Column(db.Integer, primary_key=True)
    review_id = db.Column(db.Integer, db.ForeignKey("reviews.id"), nullable=False)
    client_id = db.Column(db.Integer, db.ForeignKey("clients.id"), nullable=False)
    reply_text = db.Column(db.Text, nullable=False)
    auto_posted = db.Column(db.Boolean, default=False, nullable=False)
    scheduled_post_at = db.Column(db.DateTime, nullable=True)
    posted_at = db.Column(db.DateTime, nullable=True)
    approved_at = db.Column(db.DateTime, nullable=True)
    edited = db.Column(db.Boolean, default=False, nullable=False)
    routing_reason = db.Column(db.Text, nullable=True)

    review = db.relationship("Review", back_populates="reply")
    client = db.relationship("Client", back_populates="replies")


class ToneMemory(db.Model):
    __tablename__ = "tone_memory"

    id = db.Column(db.Integer, primary_key=True)
    client_id = db.Column(db.Integer, db.ForeignKey("clients.id"), nullable=False)
    reply_text = db.Column(db.Text, nullable=False)
    edited = db.Column(db.Boolean, default=False, nullable=False)
    weight = db.Column(db.Integer, default=1, nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    client = db.relationship("Client", back_populates="tone_memories")


class Waitlist(db.Model):
    __tablename__ = "waitlist"

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
